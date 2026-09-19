#!/usr/bin/env python3
"""
Deterministic Stage 0 fit-gate builder.
# Implements FR-252

Reads Original_JD.txt from a submission folder (or a bare folder path), runs
all zero-token gates (DB cooldown, prefs/exclusions, gap classification), and
writes stage0_fit_gate.json in a shape compatible with the live files at
data/context_pack_validation/*/stage0_fit_gate.json.

Usage:
    python scripts/build_stage0_fit_gate.py data/submissions/{slug}
    python scripts/build_stage0_fit_gate.py data/context_pack_validation/limble

Exit: always 0; read "tier" and "decision" in the JSON to branch.
Prefer ``python scripts/run_submission.py <folder>`` for normal progression
(this script is a worker the orchestrator calls).

Every gate below (DB cooldown, prefs/exclusions, anchor-checking, tier
decision) is still deterministic -- no LLM involved, same as always.

The one exception (2026-08-17, Jason-supplied; id-only rewrite 2026-08-20):
splitting the JD into required/preferred/responsibilities/culture buckets
tries a small structured LLM call first (see _extract_sections_llm), because
the regex-based header matcher (_extract_sections) proved unreliable across
real JD phrasing. Python cleans the JD (HTML entities/tags) and harvests
candidate lines with stable integer ids. Qwen may return only those ids plus
bucket labels -- never JD wording. Resolved text is a lookup into the
harvested list. Copied strings and unknown ids are dropped. The call never
sees or influences the REJECT/PASS decision itself.

Local-only, hard-pinned to Ollama (2026-08-17, Jason-supplied correction):
this stage runs on every incoming JD, so it must never silently reach a paid
cloud provider -- the first live test of this feature quietly billed a
configured Gemini API key before this correction landed. Requirement
extraction is pinned to qwen2.5:7b-instruct-q4_K_M (STAGE0_EXTRACT_MODEL).
If that model cannot load or run, Stage 0 raises Stage0ExtractError and
stops -- no other model, no cloud, no regex extractor. Set
STAGE0_SECTION_MODE=deterministic to skip the LLM attempt entirely (tests
and explicit offline runs only).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable

# Measured 2026-08-17 on the real PracticeTek JD: this tag beat llama3.1:8b
# and every 14B local model on responsibilities completeness. Do not swap
# it for Settings.localModel or a VRAM fallback.
STAGE0_EXTRACT_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class Stage0ExtractError(RuntimeError):
    """Requirement extraction cannot proceed. Do not substitute another path."""

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
class Stage0NeedsInput(RuntimeError):
    """Stage 0 has durable confirmation questions and cannot finalize yet."""

    def __init__(self, opportunity_key: str, pending: list[dict[str, str]]) -> None:
        super().__init__("Stage 0 is waiting for Review Center input")
        self.opportunity_key = opportunity_key
        self.pending = pending


class Stage0RequirementExtractionReviewNeeded(RuntimeError):
    """Extraction's own unresolved bullets include a qualification-risk item.

    Raised by build_stage0_fit_gate (never from inside _extract_sections_nlp,
    PIN 3) when the independent three-way qualification-risk gate
    (stage0_qualification_risk_gate.classify_qualification_risk) finds at
    least one QUALIFICATION_LIKELY or AMBIGUOUS bullet among the items the
    NLP extractor could not confidently bucket. This is a receipt-only pause
    (PIN 1): it fires before run_key/request_hash/start_run exist, so no
    stage0_runs row is created and mark_run_status is never called for it.
    The orchestrator writes WAITING_FOR_INPUT with
    pause_kind=requirement_extraction_review.
    """

    def __init__(self, opportunity_key: str, queue: list[dict]) -> None:
        super().__init__(
            "Stage 0 requirement extraction produced qualification-risk "
            "bullets that need review before a terminal PASS or SKIP."
        )
        self.opportunity_key = opportunity_key
        self.queue = queue


class Stage0CostAuthorizationNeeded(RuntimeError):
    """Stage 0 cannot classify remaining lines without an authorized provider.

    This is a resumable pause, not a terminal extract failure. The orchestrator
    writes WAITING_FOR_INPUT with pause_kind=cost_authorization.
    """

    def __init__(
        self,
        *,
        authorization_mode: str = "unknown",
        ineligible_providers: list[dict] | None = None,
        model_call_occurred: bool = False,
        reason: str = "no_eligible_provider",
        cost_receipt: dict | None = None,
        next_paths: list[str] | None = None,
    ) -> None:
        super().__init__(
            "Stage 0 paused: no eligible classifier. No model API call occurred."
        )
        self.authorization_mode = authorization_mode
        self.ineligible_providers = ineligible_providers or []
        self.model_call_occurred = model_call_occurred
        self.reason = reason
        self.cost_receipt = cost_receipt or {}
        self.next_paths = next_paths or [
            "import_cascade_json",
            "certify_zero_charge",
            "paid_allowlist_budget",
        ]

    def pause_kind(self) -> str:
        if str(self.reason or "").startswith("subscription_review"):
            return "subscription_review"
        return "cost_authorization"


def stage0_cost_pause_from_error(exc: BaseException) -> Stage0CostAuthorizationNeeded:
    """Map a helper CostPauseError onto the Stage 0 pause type. No receipts."""
    receipt = getattr(exc, "receipt", None) or {}
    return Stage0CostAuthorizationNeeded(
        authorization_mode=str(receipt.get("authorization_mode") or "unknown"),
        ineligible_providers=list(receipt.get("ineligible_providers") or []),
        model_call_occurred=False,
        reason=str(receipt.get("reason") or "no_eligible_provider"),
        cost_receipt=dict(receipt),
    )



_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
_CLAIMS_PATH = _REPO_ROOT / "data" / "master_claims_tags_only.json"
_SKILLS_PATH = _REPO_ROOT / "data" / "skills_catalog.json"
_PREFS_PATH = _REPO_ROOT / "data" / "candidate_preferences.json"
_DEFAULT_DB = _REPO_ROOT / "data" / "jobagent.sqlite"

# ---------------------------------------------------------------------------
# Vocabulary loader (Story 2.4 anchor corpus)
# ---------------------------------------------------------------------------

def _load_anchor_vocab() -> set[str]:
    """
    Build the set of all known-true anchor terms (lowercase).

    Sources:
      - All tags from master_claims_tags_only.json
      - All tool names from skills_catalog.json

    Individual words within multi-word tags are also added so partial-phrase
    matching still fires (e.g. tag "Roadmap Prioritization" gives "roadmap"
    and "prioritization").
    """
    vocab: set[str] = set()

    if _CLAIMS_PATH.exists():
        try:
            claims = json.loads(_CLAIMS_PATH.read_text(encoding="utf-8"))
            for claim in claims.values():
                for tag in claim.get("tags") or []:
                    term = tag.strip().lower()
                    vocab.add(term)
                    for word in re.findall(r"[a-z]{3,}", term):
                        vocab.add(word)
        except Exception:
            pass

    if _SKILLS_PATH.exists():
        try:
            catalog = json.loads(_SKILLS_PATH.read_text(encoding="utf-8"))
            for terms in catalog.values():
                for t in terms:
                    term = t.strip().lower()
                    if not term:
                        continue
                    vocab.add(term)
                    # Skill catalog entries are product/tool phrases. Do NOT whitespace-split
                    # them into bare words — "Microsoft Teams" / "Google Suite" previously
                    # added "microsoft" and "suite", which falsely anchored unrelated
                    # "Microsoft Office Suite" requirements as grounded (Central Bank,
                    # 2026-08-11). Keep slash/colon/comma components only (e.g.
                    # "HTML/CSS/JavaScript" → html, css, javascript).
                    for part in re.split(r"[/,:]+", term):
                        part = part.strip()
                        if len(part) < 3:
                            continue
                        vocab.add(part)
                        if " " in part:
                            # Still allow the component phrase; do not add its words.
                            continue
        except Exception:
            pass

    return vocab


# ---------------------------------------------------------------------------
# Hard-blocked tool list (Story 2.4)
# ---------------------------------------------------------------------------

# Single source of truth: scripts/blocked_tools.py (shared with submission_linter
# LR-026). Do not maintain a second copy here.
from blocked_tools import HARD_BLOCKED_TOOLS as _HARD_BLOCKED_TOOLS  # noqa: E402
from blocked_tools import hard_blocked_tool_pattern as _shared_hard_tool_pattern  # noqa: E402
from blocked_tools import load_skills_catalog_terms as _load_skills_catalog_terms_shared  # noqa: E402
from blocked_tools import looks_like_named_tool as _looks_like_named_tool  # noqa: E402
from stage0_confirmations import (  # noqa: E402
    canonical_skill_key,
    create_hard_gate_review,
    create_skill_confirmation,
    get_hard_gate_decision,
    get_skill_memory,
    model_flagged_named_skill,
    named_skill_candidates,
)
from stage0_checkpoint import (  # noqa: E402
    checkpoint_boundary,
    clean_spool,
    complete_judgment,
    get_completed_judgment,
    make_item_key,
    make_run_key,
    mark_run_status,
    start_run,
    update_run_metadata,
    write_spool,
)

# Regex pattern to detect hard-blocked tool names in a requirement string.
# Compiled lazily.
_HARD_TOOL_RE: re.Pattern | None = None


def _get_hard_tool_pattern() -> re.Pattern:
    global _HARD_TOOL_RE
    if _HARD_TOOL_RE is None:
        _HARD_TOOL_RE = _shared_hard_tool_pattern()
    return _HARD_TOOL_RE


# ---------------------------------------------------------------------------
# JD section extraction (Story 2.3)
# ---------------------------------------------------------------------------

# Section heading patterns → (bucket, priority)
# Earlier matches win; we stop scanning a section when the next header appears.
_SECTION_HEADERS: list[tuple[str, re.Pattern]] = [
    ("required", re.compile(
        r"^(?:#+\s*)?"
        r"(?:"
        # Bare "Required" / "Required:" (Deloitte-class, 2026-08-10 batch).
        # Must be its own $-anchored alternative — a trailing \b after the group
        # fails when the line ends in ":" (non-word char), so do not share \b.
        r"required\s*:?\s*$|"
        r"(?:"
        r"requirements?|qualifications?|your\s+qualifications?|"
        # 2026-08-17 batch: the contraction was mandatory ("you'll") with no
        # uncontracted or bare fallback -- real JDs write "What You Will Bring",
        # "What You Will Likely Bring", and bare "What You Bring" just as often
        # as "What You'll Bring", and none of those matched anything at all
        # (confirmed real: Wabash, PracticeTek dropped 5-7 of their real
        # required items this way, header never fired so current_bucket never
        # switched). Modal suffix is now fully optional, not contraction-only.
        r"what\s+you(?:'ll|\s+will(?:\s+likely)?)?\s+(?:need|bring|have)|"
        r"what\s+we(?:'|')re?\s+looking\s+for|"
        r"a\s+few\s+things\s+(?:they|we)(?:'|')re\s+looking\s+for|"
        r"who\s+you\s+are|must\s+have|the\s+ideal\s+candidate|"
        r"minimum\s+qualifications?|required\s+(?:skills?|qualifications?|experience)|"
        r"key\s+requirements?|basic\s+qualifications?|you\s+bring|about\s+you|"
        # Ready-Net informal quals header; Dr Seuss KSA / Experience and Qualifications
        r"a\s+bit\s+about\s+you|"
        r"knowledge\s*,?\s*skills\s*,?\s*(?:and\s+)?abilities|"
        r"experience\s+and\s+qualifications?|"
        r"experience\s+(?:required|needed)|"
        # RealTime eClinical all-caps: "WHAT ARE WE LOOKING FOR?" / "WHAT DO YOU NEED?"
        r"what\s+are\s+we\s+looking\s+for|"
        r"what\s+do\s+you\s+need|"
        # Paylocity / PointClickCare mid-JD quals labels
        r"ideal\s+candidate\s+profile|"
        r"(?:your\s+)?key\s+strengths|"
        r"what\s+you\s+offer"
        r")\b"
        r")",
        re.I,
    )),
    ("preferred", re.compile(
        r"^(?:#+\s*)?"
        r"(?:preferred\s+(?:qualifications?|skills?|experience|requirements?)|"
        r"nice\s+to\s+have|also\s+great\s+to\s+have|great\s+to\s+have|"
        r"bonus\s+(?:points?|if|qualifications?)|"
        r"additional\s+qualifications?|plus(?:es?)?|"
        r"preferred|ideally\s+you|you\s+may\s+also\s+have|"
        # CR-086: Thermo-class preferred lead-in headers ("Key Capabilities for Success:")
        r"key\s+capabilities?(?:\s+for\s+success)?|"
        # 2026-08-17: moved here from "required" -- "what sets/could set/would
        # set you apart" is differentiator language (Epicor: this is the real
        # header introducing its actual preferred/nice-to-have list), not a
        # required-quals header. Widened past bare "sets" at the same time
        # (Epicor's own header is "What Could Set You Apart", which the
        # original required-only, sets-only pattern never matched at all).
        r"what\s+(?:sets|could\s+set|would\s+set)\s+you\s+apart)\b",
        re.I,
    )),
    ("responsibilities", re.compile(
        r"^(?:#+\s*)?"
        r"(?:responsibilities?|what\s+you(?:'|')ll?\s+do|what\s+you\s+will\s+(?:do|be\s+doing|own)|"
        # Deloitte / Greenhouse variants measured 2026-08-10
        r"work\s+you(?:'|')ll?\s+do|"
        r"(?:the\s+)?key\s+responsibilities?|"
        r"roles?\s+and\s+responsibilities?|"
        r"how\s+(?:will\s+you|you(?:'|')ll?\s+)\s*make\s+an?\s+impact|"
        r"the\s+role|the\s+position|in\s+this\s+role|what\s+you(?:'|')ll?\s+(?:be\s+doing|own)|"
        r"your\s+responsibilities?|"
        # Ready-Net informal role header ("About Your Role At Ready")
        r"about\s+(?:your\s+)?role(?:\s+at\s+\S+)?|"
        # CR-086: AMN-class — "Job Responsibilities" mid-JD was captured as a required *item*
        # because the header regex required the line to *start* with "responsibilities".
        r"job\s+responsibilities?|"
        r"day.to.day|primary\s+responsibilities?|core\s+responsibilities?|"
        r"what\s+success\s+looks?\s+like|"
        # CR-090 follow-up: measured 2026-08-10 -- this single header alone was the
        # top blocker in 6 of 10 remaining incomplete real submissions (bled the
        # company-intro paragraph, "You'll report to:", and downstream interview
        # steps all into whatever bucket was active before it).
        r"what\s+the\s+job\s+involves|"
        # RealTime eClinical all-caps: "WHAT WILL YOU BE DOING?"
        r"what\s+will\s+you\s+be\s+doing|"
        r"you\s+will)\b",
        re.I,
    )),
    ("culture", re.compile(
        # CR-089: tolerate a short company-name prefix before the trigger phrase
        # (e.g. "LeafLink Perks & Benefits") -- header regexes anchored strictly at
        # line-start silently fail on this very common real-world JD convention,
        # leaving current_bucket unchanged so every benefits bullet underneath
        # gets miscategorized as a requirement. Bounded to 0-3 short capitalized
        # tokens so this can't drift into matching mid-paragraph.
        # Company-name prefix must stay CASE-SENSITIVE even though the rest of
        # this pattern uses re.I. With IGNORECASE, [A-Z] also matches lowercase,
        # so "Strong opinions about AI" was matching as a fake "About {Company}"
        # culture header (2026-08-10 mixed-bucket recovery) and dumping the
        # trailing Bonus: line into culture.
        r"^(?:#+\s*)?(?-i:(?:[A-Z][\w'&.-]{1,20}\s+){0,3})"
        r"(?:about\s+us|our\s+(?:culture|values?|team|mission|company)|"
        # "More about {Company}" / bare "About {Company}" founder blurbs
        # (Nash / Ready Net, 2026-08-10). Negative lookahead keeps "About you" /
        # "About your role" / "About what you get" on their real buckets.
        r"more\s+about\s+\w+|"
        r"about\s+(?!you\b|your\b|what\b)\w+|"
        # CR-086: "Our Core Values" did not match `our values` (intervening "Core").
        r"(?:our\s+)?core\s+values?|"
        r"why\s+(?:us|join|we|this\s+role)|company\s+overview|who\s+we\s+are|"
        r"who\s+are\s+(?:we|[\w&]+)|"
        # CR-089: "What We Offer" / "Our Perks" were already filtered as orphan
        # *items* (_ORPHAN_HEADER_LABEL_RE) but never redirected current_bucket,
        # so this is the fix that actually stops the leak rather than just hiding
        # the header line itself.
        r"what\s+we(?:'|')ll?\s+offer|what\s+we\s+offer|our\s+perks|"
        r"what\s+you(?:'|')ll?\s+(?:get|receive)|"
        r"what\s+you\s+can\s+expect(?:\s+from\s+us)?|"
        r"about\s+what\s+you\s+get|"
        # CR-090 follow-up: measured 2026-08-10 -- neither a header-redirect trigger
        # nor the orphan-item filter, so this fell straight through as a standalone
        # required/preferred item on its own bucket-inheritance.
        # 2026-08-17: this pair was meant to cover both "what's" (contracted)
        # and "what is" (spelled out), each against "in it" and "in this" --
        # but the contraction only ever got paired with "in this", not "in
        # it", so the single most common real phrasing ("What's in it for
        # you") never matched anything at all (saas_group: its whole "What's
        # in it for you" section, including the closing pitch paragraph,
        # bled into required). Now covers both determiners under both verb
        # forms.
        r"what(?:'s|\s+is)\s+in\s+(?:it|this)\s+for\s+you|"
        r"our\s+commitment\s+to\s+you|"
        r"ready\s+to\s+make\s+an?\s+impact|"
        # "Why This Matters" (auxilius) / "Why This Role Matters" -- another
        # "why work here" pitch header that never matched anything, so its
        # narrative content bled into required.
        r"why\s+this\s+(?:role\s+)?matters|"
        # 2026-08-17: "Employee Value Proposition:" (Lexipol) is "why work
        # here" framing -- real culture content, not a candidate requirement.
        # Never matched anything before, so its content ("The organization is
        # growing, committed to staff growth...") bled into whatever bucket
        # was still active (usually required).
        r"employee\s+value\s+proposition|"
        r"benefits?|perks?|compensation)\b",
        re.I,
    )),
]

# Boilerplate / policy / EEO / logistics headers. Matching one ends the current
# quals bucket and discards following body until another known section header.
# Found 2026-08-07: Pinterest "What we're looking for" bled Relocation /
# Inclusion / salary into required → fake soft gaps + optimization-bar noise.
#
# Anchored to end-of-line (optional colon) so "Remote: prioritizing CT/ET…" or
# "Salary depends on experience and level" do NOT kill a live quals section.
_IGNORE_SECTION_HEADERS = re.compile(
    # CR-089: same company-name-prefix tolerance as the culture header above --
    # "Company Perks & Benefits" style headers were silently defeating this
    # anchored match too. (?-i:...) keeps the prefix case-sensitive under re.I
    # (see culture-header note above).
    r"^(?:#+\s*)?(?-i:(?:[A-Z][\w'&.-]{1,20}\s+){0,3})"
    r"(?:"
    r"relocation(?:\s+statement)?|"
    r"in-?office(?:\s+requirement)?(?:\s+statement)?|"
    r"remote\s+work(?:\s+(?:statement|policy|model))?|"
    r"our\s+commitment\s+to\s+inclusion|"
    r"commitment\s+to\s+(?:diversity|inclusion|equity)|"
    r"equal\s+opportunity(?:\s+employer)?|"
    r"eeo(?:\s+statement)?|"
    r"aap\s*/\s*eeo(?:\s+statement)?|"
    r"diversity(?:\s*,?\s*equity)?,?\s*(?:and\s+)?inclusion|"
    r"salary(?:\s+range)?|"
    r"compensation(?:\s+(?:and|&)\s+benefits)?|"
    r"benefits(?:\s+(?:and|&)\s+perks)?|"
    r"perks(?:\s+and\s+benefits)?|"
    r"additional\s+information|"
    r"legal\s+notices?|"
    r"privacy\s+notice|"
    r"accommodations?(?:\s+statement)?|"
    r"about\s+(?:the\s+)?(?:interview|hiring)\s+process|"
    r"(?:our\s+)?interview\s+process|"
    # 2026-08-17: "Target Outcomes/Success Metrics:" (Lexipol) never matched --
    # the "/"-joined compound header defeats the company-name-prefix tolerance
    # above (a "/" isn't in that prefix's allowed char class), and bare
    # "success metrics" alone doesn't cover the "target outcomes" half. These
    # describe business/company targets (e.g. "8% revenue growth attributable
    # to product-led initiatives"), not candidate requirements -- real content
    # bled into "required" with no boundary to stop it. Widened to tolerate an
    # optional "target outcomes" lead-in joined by "/" or "and".
    r"(?:target\s+outcomes\s*(?:/|and)\s*)?success\s+metrics|"
    r"target\s+outcomes|"
    r"(?:the\s+)?successful\s+(?:\w+\s+){0,4}will\s+be\s+measured\s+on|"
    r"we\s+offer\s+all\s+(?:full-?time\s+)?(?:team\s+members|employees)|"
    r"other\s+duties|"
    # CR-086: physical / work-environment headers end quals collection
    r"work\s+environment(?:\s*/\s*physical\s+requirements?)?|"
    r"physical\s+requirements?|"
    r"working\s+conditions?|"
    # 2026-08-10 batch: logistics / process labels that aren't hire criteria
    r"ways\s+of\s+working|"
    r"anticipated\s+position\s+close\s+date|"
    r"disability\s*,?\s*life\s+insurance(?:\s+and\s+ancillary\s+benefits?)?|"
    r"our\s+commitment\s+to\s+you|"
    r"ready\s+to\s+make\s+an?\s+impact|"
    r"what\s+sets\s+you\s+apart|"
    r"what\s+is\s+in\s+it\s+for\s+you|"
    # 2026-08-17: closing-CTA headers that end a JD's real qualifications
    # section but don't switch to a recognized bucket, so quals collection
    # ran on into trailing boilerplate (PracticeTek: "Ready to Join?" / "The
    # Fine Print (That Really Matters)" / "This job description is not a
    # contract..." all leaked into required once the real "What You Bring"
    # header started matching correctly).
    r"ready\s+to\s+join(?:\s+us)?\s*\?{0,2}|"
    r"the\s+fine\s+print(?:\s*\([^)]*\))?"
    r")"
    r"\s*:?\s*$",
    re.I,
)

_TRACKING_TAG_RE = re.compile(r"^#li-[\w-]*\s*$", re.I)


def classify_jd_header(line: str) -> tuple[str | None, bool]:
    """Return (bucket, is_pure_label) for a JD line.

    bucket is required/preferred/responsibilities/culture/ignore, or None.
    is_pure_label True means the line is only a header (skip as a candidate).
    A header match with real trailing content returns is_pure_label False so
    harvest can keep it as an item instead of treating the sentence as a label.
    """
    clean = (line or "").strip()
    if not clean:
        return None, False
    if _TRACKING_TAG_RE.match(clean) or _IGNORE_SECTION_HEADERS.match(clean):
        return "ignore", True
    for bucket_name, header_re in _SECTION_HEADERS:
        m = header_re.match(clean)
        if not m:
            continue
        trailing = clean[m.end():].strip(" \t:?.-")
        return bucket_name, len(trailing) < 3
    return None, False

_BOILERPLATE_ITEM_RE = re.compile(
    r"(?i)(?:"
    r"relocation\s+assistance|"
    r"not\s+eligible\s+for\s+relocation|"
    r"relocation\s+statement|"
    r"in-?office\s+requirement|"
    r"equal\s+opportunity(?:\s*/\s*affirmative\s+action)?(?:\s+employer)?|"
    r"commitment\s+to\s+inclusion|"
    r"all\s+qualified\s+applicants\s+will\s+receive\s+consideration|"
    r"without\s+regard\s+to\s+race|"
    r"us[\s-]?based\s+applicants\s+only|"
    r"by\s+submitting\s+this\s+application|"
    r"base\s+salary\s+range|"
    r"(?:typical\s+)?hiring\s+range|"
    r"(?:expected\s+)?(?:base\s+)?(?:pay|salary)\s+range|"
    r"target\s+salary\s+range|"
    r"competitive\s+base\s+salary|"
    r"discretionary\s+bonus|"
    r"annual\s+base\s+salary|"
    r"pay\s+rate\s*\$|"
    r"us\s+hiring\s+range|"
    r"position\s+is\s+(?:also\s+)?eligible\s+for\s+(?:total\s+compensation|equity)|"
    r"visit\s+our\s+\w[\w\s-]{0,40}\s+page\s+to\s+learn\s+more|"
    r"information\s+regarding\s+the\s+culture|"
    r"benefits\s+available\s+for\s+this\s+position|"
    r"pinflex|"
    r"#li-|"
    r"\$[\d,]+\.?\d*\s*[—–\-to]+\s*\$[\d,]+\.?\d*|"
    r"rate:\s*~?\$|"
    r"make\s+employment\s+decisions\s+on\s+the\s+basis\s+of\s+merit|"
    r"protected\s+veteran|"
    r"criminal\s+histories,?\s+consistent\s+with\s+legal|"
    r"additional\s+compensation\s+such\s+as\s+bonus|"
    r"dice\s+id\s*:|"
    r"position\s+id\s*:|"
    r"create\s+job\s+alert|"
    r"search\s+all\s+similar\s+jobs|"
    r"never\s+miss\s+an\s+opportunity|"
    r"go\s+to\s+company\s+profile|"
    r"posted\s+\d+\+?\s*days?\s+ago|"
    r"view\s+all\s+(?:jobs|companies)\b|"
    r"top\s+remote\s+companies|"
    r"employers\s+have\s+access\s+to\s+artificial\s+intelligence\s+language\s+tools|"
    r"our\s+interview\s+process|"
    r"gone\s+through\s+the\s+interview\s+process|"
    r"during\s+the\s+interview\s+process|"
    r"hiring\s+and\s+interview\s+process|"
    r"following\s+a\s+completed\s+interview\s+process|"
    r"interview\s+process\s+meets\s+the\s+needs|"
    r"image\s+\(video\s+or\s+screenshot\)\s+during\s+the\s+interview|"
    # CR-086: physical / ADA / residual compensation lines that appear as "items"
    r"work\s+is\s+performed\s+in\s+an\s+(?:office|home\s+office)|"
    r"operate\s+standard\s+office\s+equipment|"
    r"office\s+equipment\s+and\s+keyboards?|"
    r"reasonable\s+accommodations?\s+to\s+qualified\s+individuals|"
    r"individuals\s+with\s+disabilities\s+to\s+perform|"
    r"final\s+pay\s+rate\s+is\s+dependent|"
    r"pay\s+(?:rate|range)\s+is\s+dependent\s+on\s+experience|"
    r"dependent\s+on\s+experience,\s*training,\s*education|"
    # CR-089: content-level safety net for benefits/perks copy that leaked into
    # required/preferred/responsibilities (measured 2026-08-10: dominant noise
    # category across 54 real submissions, ~18.5% of companies affected) --
    # catches it item-by-item regardless of whether the header redirect above
    # actually fired, since no header regex will ever cover every real-world
    # phrasing. Same belt-and-suspenders pattern as the physical/ADA items above.
    r"\b(?:medical|dental|vision)\s*,?\s*(?:and\s+)?(?:dental|vision|coverage|insurance|plans?)\b|"
    r"\b401\(?k\)?\b|"
    r"\bpaid\s+time\s+off\b|\bflexible\s+pto\b|\bgenerous\s+pto\b|\bpto\s+and\s+sick\s+leave\b|"
    r"\bstock\s+options?\b|\bequity\s+(?:grant|package)\b|\b529\s+college\s+savings\b|"
    r"\bparental\s+leave\b|\bcompany\s+match(?:ing)?\b|"
    r"\ball-round\s+benefits\s+package|\bperks\s*&\s*benefits|"
    # CR-089/090: interview-process / application-instruction copy (smaller share
    # of the same measured noise, but real). CR-090 follow-up: the "(?:our|the|a)"
    # requirement missed bare "Interview with recruiter" / "Interview with CTO" --
    # broadened to any word, not just an article.
    r"interview\s+with\s+\w|"
    r"\b(?:bar\s+raiser|phone\s+screen|product\s+deep\s+dive)\b|"
    r"upload\s+your\s+(?:resume|cv)\b|submit\s+your\s+(?:resume|cv|application)\b|"
    r"convinced\?\s*submit\s+your\s+application|"
    r"^start\s+date:?\s*|"
    r"^offer\s*\+\s*prior\s+employment|"
    r"if\s+you\s+don'?t\s+have\s+an?\s+up\s+to\s+date\s+cv|"
    # 2026-08-10 batch: E-Verify / pay-structure / hybrid-policy / close-date noise
    r"\be-?verify\s+participant\b|"
    r"note:\s*starting\s+pay\s+will\s+be\s+based|"
    r"location\s+based\s+compensation\s+structure|"
    r"policy\s+on\s+hybrid\s*/?\s*virtual\s+work|"
    r"anticipated\s+position\s+close\s+date|"
    r"ways\s+of\s+working|"
    r"disability\s*,?\s*life\s+insurance(?:\s+and\s+ancillary\s+benefits?)?|"
    # Zoom / enterprise ATS compensation + apply-window copy (Common Room,
    # 2026-08-11 corpus). Also false-anchored via skills_catalog "Zoom".
    r"total\s+direct\s+compensation|"
    r"base\s+salary\s+and/?\s*or\s+ote|"
    r"\bote\s+listed\b|"
    r"window\s+of\s+at\s+least\s+\d+\s+days?\s+for\s+you\s+to\s+apply|"
    r"we\s+believe\s+in\s+giving\s+you\s+every\s+opportunity\s+to\s+apply|"
    # Soft-skill personality fluff that is not a hire-evidence criterion
    r"navigate\s+ambiguity|"
    r"drive\s+clarity\s+across\s+teams|"
    r"team-?oriented\s+mindset|"
    # Acushnet / Realtime CTA + benefits copy
    r"our\s+commitment\s+to\s+you|"
    r"ready\s+to\s+make\s+an?\s+impact|"
    r"additionally,?\s+you(?:'|')ll?\s+enjoy\s+perks|"
    r"pet\s+insurance|"
    r"what\s+sets\s+you\s+apart|"
    r"what\s+is\s+in\s+it\s+for\s+you|"
    # Soft-skill personality fluff (Acushnet-class) — not hire criteria
    r"^dependable\s*,?\s*accountable|"
    r"^self-?motivated\s+(?:and|,)|"
    r"^passionate\s+about\s+making\s+a\s+difference|"
    # "How to apply" instruction lines. Real miss found 2026-08-13 (Decisiv/pop_up_talent):
    # a mid-JD "To apply for quick consideration:" line followed by the apply-link URL on
    # its own line got swept into `required` (the second inline "REQUIRED:" travel/residency
    # block never closed before this text), then fail-closed the packet build as an
    # unmapped required item since it isn't real hire criteria to begin with.
    r"to\s+apply\s+for\s+(?:quick\s+)?consideration|"
    r"^apply\s+(?:now|here|today|via)\b|"
    # Fix 3 (2026-08-21 Stage 1-3 audit): defense-in-depth twin of the
    # patterns added to stage0_extract._BOILERPLATE_RE, the real default
    # extraction path (this regex only runs when STAGE0_SECTION_MODE=
    # deterministic, or in tests that force it). Confirmed real on Point C,
    # Tm2 Group, and Alfa Laval -- see stage0_extract.py's comment for the
    # exact failing lines this covers.
    r"compensation\s+range\s*:|"
    r"\$[\d,]+(?:\.\d+)?\s*[kKmM]?\s*[-–—]\s*\$?[\d,]+(?:\.\d+)?\s*[kKmM]?|"
    r"[\w.+-]+@[\w-]+\.\w{2,}|"
    r"for more information,?\s+please\s+contact|"
    r"no\s+later\s+than|apply\s+by\s+\w|application\s+deadline|"
    r"general\s+data\s+protection\s+regulation|"
    r"do\s+not\s+accept\s+applications\s+via\s+email|"
    r"continuous\s+review\s+of\s+received\s+applications|"
    r"we\s+look\s+forward\s+to\s+hearing\s+from\s+you|"
    r"background\s+investigation|consent\s+to\s+.{0,30}background\s+check|"
    r"commensurate\s+with\s+the\s+candidate.s\s+experience|"
    r"eligible\s+for\s+additional\s+compensation,?\s+including\s+bonuses|"
    r"sales\s+commission\s+plan|"
    r"offer\s+a\s+competitive\s+salary\s+and\s+comprehensive\s+benefits|"
    r"flexible\s+and\s+balanced\s+environment|"
    r"opportunity\s+to\s+work\s+remotely|"
    r"summary\s+generated\s+by\s+built\s+in|"
    r"generated\s+by\s+built\s+in"
    r")"
)

# A line that, once trimmed, is nothing but a bare URL is never real hire criteria —
# belt-and-suspenders for apply-link lines regardless of the lead-in phrasing above.
_BARE_URL_ITEM_RE = re.compile(r"^https?://\S+$", re.I)

# Used by orphan-header colon fallback and CR-115 chrome drop. A heading with
# a real requirement verb is not chrome.
_REQUIREMENT_VERB_RE = re.compile(
    r"\b(?:own|run|write|develop|lead|partner|build|manage|require|must|"
    r"need|deliver|ship|define|create|ensure|identify)\b",
    re.I,
)

# CR-115: scored-path chrome leftover already junks when confidence is low.
_JOB_BOARD_CHROME_RE = re.compile(
    r"(?i)^(?:#+\s*)?(?:"
    r"mid(?:dle)?\s+and\s+senior\s+level|"
    r"senior\s+level|"
    r"job\s+type|"
    r"employment\s+type|"
    r"experience\s+level|"
    r"job\s+category"
    r")\s*:?\s*$"
)
_SECTION_HEADING_CHROME_RE = re.compile(
    r"(?i)^(?:#+\s*)?(?:"
    r"education(?:\s+and\s+credentials?)?|"
    r"credentials?|"
    r"additional\s+details|"
    r"company\s+summary|"
    r"expectations?\s+of\s+the\s+role"
    r")\s*:?\s*$"
)
_TRUNCATED_FRAGMENT_RE = re.compile(
    r"(?i)^(?:experiences?|skills?|knowledge|background)\s+that\b"
)


# Known orphan section labels that sometimes appear as bullets when header routing
# missed them. Prefer this allowlist over a generic Title-Case heuristic — the latter
# false-positives on short skill/tool list items (e.g. "Agile Product Management Tools").
_ORPHAN_HEADER_LABEL_RE = re.compile(
    r"^(?:#+\s*)?"
    r"(?:"
    r"job\s+responsibilities?|"
    r"(?:our\s+)?core\s+values?|"
    r"work\s+environment(?:\s*/\s*physical\s+requirements?)?|"
    r"physical\s+requirements?|"
    r"key\s+capabilities?(?:\s+for\s+success)?|"
    r"key\s+capabilities?\s+for\s+success|"
    r"about\s+(?:the\s+)?(?:role|company|us)|"
    r"more\s+about\s+\w+|"
    r"what\s+we\s+offer|"
    r"what\s+you\s+can\s+expect(?:\s+from\s+us)?|"
    r"your\s+qualifications?|"
    r"skills?\s*(?:and|&)\s*qualifications?|"
    r"core\s+competencies|"
    r"how\s+(?:will\s+you|you(?:'|')ll?\s+)\s*make\s+an?\s+impact|"
    r"ways\s+of\s+working|"
    r"anticipated\s+position\s+close\s+date|"
    r"disability\s*,?\s*life\s+insurance(?:\s+and\s+ancillary\s+benefits?)?|"
    r"our\s+commitment\s+to\s+you|"
    r"ready\s+to\s+make\s+an?\s+impact|"
    r"what\s+sets\s+you\s+apart|"
    r"what\s+is\s+in\s+it\s+for\s+you|"
    r"benefits?\s+(?:and|&)\s+perks?"
    r")"
    r"\s*:?\s*$",
    re.I,
)


def _is_orphan_header_item(text: str) -> bool:
    """CR-086: section labels wrongly captured as hire-criteria bullets.

    Two cases only (conservative on purpose):
    1. Known header labels (`Job Responsibilities`, `Our Core Values`, …).
    2. Very short trailing-colon lead-ins that somehow bypassed `_is_list_leadin`
       (defense in depth; leadin already skips most of these at extract time).
    """
    clean = (text or "").strip().lstrip("-•*◦▪▸→").strip()
    if not clean:
        return False
    if _ORPHAN_HEADER_LABEL_RE.match(clean):
        return True
    if clean.endswith(":"):
        words = re.findall(r"[A-Za-z0-9']+", clean)
        if 1 <= len(words) <= 8 and not _REQUIREMENT_VERB_RE.search(clean):
            return True
    return False


def _empty_extraction_buckets() -> dict[str, list[str]]:
    """Live leftover buckets, including junk. Implements FR-328 / AC-426."""
    from stage0_classifier_contract import EXTRACTION_BUCKETS

    return {name: [] for name in EXTRACTION_BUCKETS}


def _leftover_bucket(bucket: str, text: str) -> str:
    """Force disposition lines into culture so they are never scored. Implements FR-328."""
    from stage0_classifier_contract import is_disposition_culture_line

    if is_disposition_culture_line(text):
        return "culture"
    return bucket


def _is_boilerplate_item(text: str) -> bool:
    """True when an extracted bullet is ATS/policy boilerplate, not a hire criterion."""
    clean = (text or "").strip()
    if not clean:
        return True
    if _TRACKING_TAG_RE.match(clean):
        return True
    if _BOILERPLATE_ITEM_RE.search(clean):
        return True
    if _BARE_URL_ITEM_RE.match(clean):
        return True
    # Header-only leftovers that snuck into the item list.
    if _IGNORE_SECTION_HEADERS.match(clean):
        return True
    # CR-086: orphan section labels captured as items (e.g. bare "Job Responsibilities"
    # when header routing missed — belt-and-suspenders with expanded header patterns).
    if _is_orphan_header_item(clean):
        return True
    return False


def _is_unscored_chrome_item(text: str) -> bool:
    """True when a required/preferred line is heading, board, or fragment chrome.

    Implements FR-330 / AC-428. Leftover junk semantics are unchanged.
    """
    clean = (text or "").strip().lstrip("-•*◦▪▸→").strip()
    if not clean:
        return False
    if _is_boilerplate_item(clean):
        return True
    if _JOB_BOARD_CHROME_RE.match(clean):
        return True
    if _SECTION_HEADING_CHROME_RE.match(clean):
        return True
    if _TRUNCATED_FRAGMENT_RE.match(clean):
        return True
    return False


def _divert_scored_chrome(sections: dict) -> dict:
    """Move heading/fragment chrome out of required/preferred before scoring.

    Implements FR-330 / AC-428. Does not reclassify leftover junk or culture.
    """
    junk = list(sections.get("junk") or [])
    for key in ("required", "preferred"):
        kept: list[str] = []
        for item in sections.get(key) or []:
            if _is_unscored_chrome_item(item):
                junk.append(item)
            else:
                kept.append(item)
        sections[key] = kept
    sections["junk"] = junk
    return sections


# 2026-08-28 (Jason-supplied): best-effort salary-range capture from the raw JD
# text, for jobs.salary_range. Independent of _BOILERPLATE_ITEM_RE / bucket
# extraction above -- that pipeline exists to DROP salary-shaped lines from the
# requirements buckets so they don't pollute gap classification; this exists to
# KEEP the matched text so it can be shown in the app. A connector's own API
# field (when the source supplies one) always wins over this -- see the
# null-only backfill in server/submissionFolders.ts.
_SALARY_RANGE_CAPTURE_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?\s*[kK]?"
    r"\s*(?:-|–|—|to)\s*"
    r"\$\s?\d[\d,]*(?:\.\d+)?\s*[kK]?"
    r"(?:\s*(?:/|per)?\s*(?:year|yr|hour|hr|annum|annually))?",
)


def extract_salary_range(jd_text: str) -> str | None:
    """First plausible "$X - $Y" range found anywhere in the raw JD text, or
    None. Deliberately a single regex, not a parser: JDs phrase a range many
    ways ("$120K-$150K", "$120,000 - $150,000 / year", "120000 to 150000"
    with no dollar sign at all). This only needs to catch the common,
    unambiguous dollar-sign case well enough to be worth showing in the app
    -- a miss just means no badge, never a wrong one."""
    match = _SALARY_RANGE_CAPTURE_RE.search(jd_text or "")
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(0)).strip()


# Found 2026-08-07 (envision_technology_solutions): sub-list lead-in lines like
# "Experience working on one or more of:" / "Hands-on experience with:" pass the
# item-length filter and get captured as standalone required items even though
# they're just an intro to the bullets below, not a requirement themselves. A
# short line (<=12 words) ending in a bare colon is a lead-in, not an item —
# skip capturing it but do NOT reset current_bucket, so the real items below it
# still get collected normally.
def _is_list_leadin(clean: str) -> bool:
    if not clean.endswith(":"):
        return False
    word_count = len(re.findall(r"\w+", clean))
    return word_count <= 12


# Found 2026-08-07 (envision_technology_solutions: "...CSPO... is preferred."):
# an inline preferred marker on an otherwise-required-looking line should route
# that single item to the preferred bucket, not the required one — the section
# header controls where MOST lines in the section go, but this one line
# self-labels as preferred and the extractor should trust that over the header.
# 2026-08-10 (Seed Health): leading "Bonus: … Braze …" stayed in required, hit a
# hard-blocked tool, and forced Skip — leading Bonus: is also an inline preferred.
_INLINE_PREFERRED_RE = re.compile(
    r"(?:"
    r"^(?:bonus\s*(?:points?)?\s*:|bonus\s+(?:if|qualifications?)\b)|"
    r"(?:\bis\s+(?:strongly\s+)?preferred\b|\(preferred\)|,\s*preferred\b)\s*\.?\s*$"
    r")",
    re.I,
)
_INLINE_REQUIRED_RE = re.compile(r"\bis required\b", re.I)


def _normalize_jd_punctuation(text: str) -> str:
    """Normalize curly/smart quotes so section-header regexes match real JDs.

    Greenhouse/Lever/HTML exports often use U+2018/U+2019 apostrophes in
    headings like \"What you'll do\" / \"What we're looking for\". Without this,
    those sections extract empty and Stage 0 can falsely report a clean Tier 1.
    """
    return (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201b", "'")
        .replace("\u2032", "'")
    )


def _qual_line_items(clean: str) -> list[str]:
    """Split an overlong paragraph bullet so it is not dropped by the 300-char cap.

    LinkedIn-style Required/Preferred blocks are often one paragraph. Silent drop
    of those lines is scored-path line loss on the locked 30. Implements FR-330.
    """
    if not clean:
        return []
    if not (clean[0].isalnum() or clean[0] in "\"'"):
        return []
    if 15 <= len(clean) <= 300:
        return [clean]
    if len(clean) < 15:
        return []
    items: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", clean):
        item = part.strip()
        if 15 <= len(item) <= 300 and (item[0].isalnum() or item[0] in "\"'"):
            items.append(item)
    return items


def _extract_sections(jd_text: str) -> dict[str, list[str]]:
    """
    Extract text buckets by section heading.

    Returns dict with keys: required, preferred, responsibilities, culture, junk.
    Each value is a list of bullet-like strings extracted from that section.

    Trailing ATS boilerplate (relocation / EEO / salary / #LI-…) is excluded:
    matching ignore headers ends the current quals bucket, and any remaining
    boilerplate strings are stripped via `_is_boilerplate_item`.
    """
    buckets: dict[str, list[str]] = _empty_extraction_buckets()

    lines = _normalize_jd_punctuation(jd_text).splitlines()
    current_bucket: str | None = None

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        # Known section header → switch bucket
        matched_bucket: str | None = None
        header_match: re.Match[str] | None = None
        for bucket_name, header_re in _SECTION_HEADERS:
            m = header_re.match(line)
            if m:
                matched_bucket = bucket_name
                header_match = m
                break

        if matched_bucket is not None:
            # Does the header match consume (almost) the whole line, or just
            # its opening words? "Required Qualifications" is a pure label --
            # the match covers the entire line, nothing real trails it.
            # "Must have worked with patients/providers in a Healthcare
            # setting" only matches "must have" (meant to catch a
            # "Must-Haves:" label); everything after it is a real, unrelated
            # sentence. That trailing-content check, not which bucket it
            # would switch to, is what actually distinguishes a header from
            # a bullet that happens to open with header-shaped words.
            #
            # 2026-08-17 batch: the first cut of this fix only suppressed a
            # header match when it changed the active bucket, on the theory
            # that a short repeated label would fail the item-length filter
            # further down anyway. Measured false on a real 397-JD corpus
            # sweep -- "Required Qualifications" (24 chars), "Key
            # Responsibilities" (20 chars), "About Certara Data Sciences
            # Team" (33 chars) all clear the 15-char minimum and leaked
            # through as phantom requirement/responsibility items whenever
            # they re-stated a header for the bucket already active (113 of
            # 397 real JDs affected). Checking the actual trailing content
            # after the match, not line length, is what correctly tells
            # "Must have worked with patients..." (57 real chars trail the
            # match) apart from "Required Qualifications" (0 chars trail
            # it) regardless of bucket.
            trailing = line[header_match.end():].strip(" \t:?.-–—")
            is_pure_label = len(trailing) < 3
            if is_pure_label or matched_bucket != current_bucket:
                current_bucket = matched_bucket
                continue
            # else: same-bucket match with real trailing content -> an
            # ordinary bullet that happens to open like a header. Fall
            # through to normal item extraction below.

        # Boilerplate / policy header → stop collecting into quals buckets
        if _IGNORE_SECTION_HEADERS.match(line) or _TRACKING_TAG_RE.match(line):
            current_bucket = None
            continue

        if current_bucket is None:
            continue

        # Extract meaningful bullet items (15–300 chars, starts with letter or digit)
        clean = line.lstrip("-•*◦▪▸→").strip()
        for item in _qual_line_items(clean):
            if _is_list_leadin(item):
                lead_bucket, _lead_label = classify_jd_header(item)
                if lead_bucket is not None:
                    current_bucket = lead_bucket
                continue
            if not _is_boilerplate_item(item):
                from stage0_classifier_contract import is_disposition_culture_line

                target_bucket = current_bucket
                if is_disposition_culture_line(item):
                    target_bucket = "culture"
                elif current_bucket == "required" and _INLINE_PREFERRED_RE.search(item):
                    target_bucket = "preferred"
                elif current_bucket == "preferred" and _INLINE_REQUIRED_RE.search(item):
                    target_bucket = "required"
                buckets[target_bucket].append(item)

    # Final safety net for items that never rode a header boundary
    for key in buckets:
        buckets[key] = [x for x in buckets[key] if not _is_boilerplate_item(x)]

    # Recovery: mixed duty+qual list landed entirely in responsibilities with
    # required empty (SDL / Shazam / Camunda-class). Only fires when required is
    # empty so well-structured JDs are untouched.
    _recover_mixed_responsibilities(buckets)

    return buckets


# ---------------------------------------------------------------------------
# Requirement-bucket cap (2026-08-28, Jason-supplied): a JD with an unusually
# long requirements list (Schellman-class outlier -- 17 real required items
# vs. the typical 7-12) pushes real per-line evidence work and Stage 1
# packet budget further than a normal JD needs. Keep the highest-value
# subset instead of classifying and carrying every line at full cost.
# ---------------------------------------------------------------------------

MAX_REQUIREMENT_ITEMS_PER_BUCKET = 12

_SPECIFICITY_NUMBER_RE = re.compile(r"\d")
_SPECIFICITY_GENERIC_SOFT_SKILL_RE = re.compile(
    r"^(?:strong|excellent|good|great|solid|proven|demonstrated|effective)\s+"
    r"(?:communication|interpersonal|analytical|problem.solving|organizational|"
    r"written|verbal|leadership|collaboration|time.management)\s+skills?\.?$",
    re.I,
)

# 2026-09-01 Improvement #8: cached anchor vocabulary for specificity scoring.
# Loaded lazily so the cost is paid only when _requirement_specificity_score
# is actually called (i.e. a bucket exceeds the 12-item cap), not on every
# import or every Stage 0 run.
_anchor_vocab_cache: set[str] | None = None


def _get_cached_anchor_vocab() -> set[str]:
    global _anchor_vocab_cache
    if _anchor_vocab_cache is None:
        _anchor_vocab_cache = _load_anchor_vocab()
    return _anchor_vocab_cache


def _requirement_specificity_score(item: str) -> float:
    """Deterministic proxy for how much one requirement line is worth
    keeping when a bucket exceeds MAX_REQUIREMENT_ITEMS_PER_BUCKET. Not a
    judgment of truth, fit, or gate-worthiness -- classify_requirement()
    still makes that call for every line that survives the cap. This only
    decides which lines are the most concrete and decision-bearing ones to
    spend a real classification call and packet-excerpt budget on, versus
    boilerplate-adjacent filler that a JD's requirements section tends to
    accumulate once it runs long.

    Higher score keeps: a digit (years, %, a count -- "5+ years experience",
    "manage a team of 10-15") is the strongest concreteness signal available
    without another LLM call. A pure generic soft-skill line ("Strong
    communication skills.") is the weakest -- it says nothing a JD-specific
    read couldn't already assume. Everything else (the common case) scores
    on length alone, as a mild, cheap proxy for "says something specific"
    over "a stray short fragment."

    2026-09-01 Improvement #8: +1.0 for items containing terms from the anchor
    vocabulary (claims tags + skills catalog). A requirement like "Experience
    with Salesforce Health Cloud" (no digit, not a generic soft skill) now
    scores higher than "Experience working in a collaborative environment",
    prioritizing specific, decision-bearing requirements over generic ones
    when capping. Only affects which items survive the 12-item cap for very
    large JDs.
    """
    text = (item or "").strip()
    if _SPECIFICITY_GENERIC_SOFT_SKILL_RE.match(text):
        return -2.0
    score = 2.0 if _SPECIFICITY_NUMBER_RE.search(text) else 0.0
    words = text.split()
    if len(words) < 4:
        score -= 1.0
    score += min(len(words), 30) * 0.01
    # Anchor-vocabulary boost: +1.0 if any anchor term appears in the item.
    lower = text.lower()
    anchor_vocab = _get_cached_anchor_vocab()
    if any(term in lower for term in anchor_vocab if len(term) >= 4):
        score += 1.0
    return score


def _cap_requirement_bucket(
    items: list[str], limit: int = MAX_REQUIREMENT_ITEMS_PER_BUCKET,
) -> tuple[list[str], int]:
    """Keep the `limit` highest-scoring items (_requirement_specificity_score),
    in their original JD order. Returns (kept_items, dropped_count) --
    dropped_count is 0 for any bucket at or under the limit, which is the
    typical case (7-12 real required items) and leaves it untouched."""
    if len(items) <= limit:
        return list(items), 0
    ranked_indices = sorted(
        range(len(items)), key=lambda i: _requirement_specificity_score(items[i]), reverse=True,
    )
    keep = set(ranked_indices[:limit])
    kept = [item for i, item in enumerate(items) if i in keep]
    return kept, len(items) - len(kept)


# Duty-imperative lead-ins for mixed-bucket recovery. Anchored at start so a
# quals line that merely *mentions* "lead" mid-sentence stays a qual.
_DUTY_LEADIN_RE = re.compile(
    r"^(?:"
    r"own|run|write|work|bring|talk|report|define|develop|lead|partner|"
    r"translate|engage|champion|contribute|leverage|scope|prioritize|build|"
    r"conduct|act|exhibit|manage|keep|gather|collaborate|participate|support|"
    r"optimize|monitor|communicate|maintain|serve|establish|enable|"
    r"standardize|assess|influence|create|identify|ensure|facilitate|"
    r"fully\s+evaluate|continuous(?:ly)?\s+assess|proactively\s+identify"
    r")\b",
    re.I,
)

# Qualification-shaped lead-ins that are not years/degree (those use existing
# helpers) but still belong in required, not responsibilities.
_QUAL_LEADIN_RE = re.compile(
    r"^(?:"
    r"a\s+track\s+record|"
    r"proven\s+(?:ability|experience|track)|"
    r"strong\s+(?:opinions?|understanding|communication|golf|problem)|"
    r"excellent\s+(?:written|verbal|communication|business)|"
    r"exceptional\s+(?:soft\s+skills|problem|communication)|"
    r"comfortable\b|"
    r"clear\s+writer|"
    r"ability\s+(?:to|and)|"
    r"familiarity\s+with|"
    r"experience\s+(?:of|with|working|supporting|in)\b|"
    r"design\s+taste|"
    r"a\s+lot\s+of\s+agency|"
    r"a\s+convincing|"
    r"dependable\b|"
    r"intermediate\s+to\s+advanced|"
    r"operational\s+product\s+management"
    r")",
    re.I,
)


def _looks_like_duty(text: str) -> bool:
    clean = (text or "").strip().lstrip("-•*◦▪▸→").strip()
    return bool(_DUTY_LEADIN_RE.match(clean))


def _looks_like_qualification(text: str) -> bool:
    clean = (text or "").strip().lstrip("-•*◦▪▸→").strip()
    if not clean:
        return False
    lower = clean.lower()
    if _YEARS_EXPERIENCE_LEADIN_RE.match(lower):
        return True
    if _BACHELORS_SATISFIED_RE.search(lower) or re.search(
        r"\b(?:master'?s?|mba|ph\.?d\.?)\s+degree\b", lower
    ):
        return True
    if _QUAL_LEADIN_RE.match(clean):
        return True
    return False


# ---------------------------------------------------------------------------
# LLM-based section extraction (2026-08-17, Jason-supplied; id-only 2026-08-20)
# ---------------------------------------------------------------------------
# Replaces _extract_sections as the default bucket-splitter. See the module
# docstring for why: regex header-matching kept producing new real-world
# failures (7 distinct root causes found and fixed on 2026-08-17 alone across
# a handful of real JDs, on top of the CR-086/089/090 patches already in this
# file). Python harvests candidate lines and assigns integer ids. Qwen only
# labels those ids. Copied wording and unknown ids are dropped. This path
# never touches the REJECT/PASS decision.

def _normalize_ws_for_substring_check(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _is_verbatim_substring(phrase: str, jd_text: str) -> bool:
    """True iff *phrase* appears in *jd_text*, modulo whitespace collapsing.

    Used for internal_terms (short proper nouns). Requirement lines are not
    validated this way -- they come from id lookup into harvested candidates.
    """
    phrase = (phrase or "").strip()
    if not phrase:
        return False
    return _normalize_ws_for_substring_check(phrase) in _normalize_ws_for_substring_check(jd_text)


_SECTION_SPLIT_SYSTEM_PROMPT = (
    "You label candidate lines from a job description. "
    "Return ONLY JSON. Bucket arrays must contain integer ids only -- "
    "never copy, paraphrase, or invent the line text."
)

_SECTION_SPLIT_USER_TEMPLATE = """Each line below is a candidate already extracted from the job description. \
Assign each id to at most one bucket. Do not copy the line text. Do not invent ids. \
Omit ids that are boilerplate, section headers, or not a real item. \
Lines tagged (required) or (preferred) came from those JD sections -- keep them \
in that bucket unless they clearly belong elsewhere, and do not omit those ids.

Buckets:
- "required": what a candidate MUST have (labeled Requirements, Qualifications, \
What You Bring, What You'll Need, Must Have, etc. -- whatever the JD calls it)
- "preferred": nice-to-have / bonus / differentiator items (Preferred \
Qualifications, Nice to Have, What Sets You Apart, Bonus Points, etc.)
- "responsibilities": what the role actually DOES day to day (Responsibilities, \
What You'll Do, duties, success-measurement criteria describing the work, etc.)
- "culture": company description, mission, values, "why work here" / benefits \
framing, and any other content about the COMPANY rather than the candidate or \
the role's duties

Do NOT label: EEO/diversity statements, salary/compensation/benefits \
boilerplate, application-process or interview-process instructions, legal \
notices, or recruiter/fraud-prevention notices.

Also identify "internal_terms": short proper nouns naming THIS employer's OWN \
products, platforms, or internal systems -- not third-party tools, vendors, \
or technologies a candidate needs outside experience with. These may be quoted \
strings (not ids). If nothing like that appears, use an empty list.
{few_shot_block}
Output ONLY this JSON shape, nothing else:
{{"required": [1, 4], "preferred": [8], "responsibilities": [2, 3], "culture": [10], "internal_terms": ["ProductName"]}}

Candidate lines:
{candidate_block}"""


def _extract_unavailable_message(reason: str) -> str:
    return (
        f"Stage 0 requirement extraction needs {STAGE0_EXTRACT_MODEL} "
        f"({reason}). No fallback model and no regex extractor. "
        f"Fix the local model and retry."
    )



def _collect_nlp_section_candidates(
    jd_text: str,
) -> tuple[dict[str, list[str]], list[tuple[str, str, str]]] | None:
    """Return confident NLP buckets and leftover lines without calling a hosted tool.

    Used by production extraction and by the CR-114 Agy archive smoke so leftovers
    can be inspected without Groq/Gemini. Implements FR-328 / AC-426.
    """
    import pipeline_env
    if pipeline_env.stage0_section_mode() == "deterministic":
        return None

    import joblib
    import warnings

    model_path = _REPO_ROOT / "data" / "stage0_classifier.pkl"
    if not model_path.exists():
        print("NLP Model not found, falling back to deterministic extraction.", file=sys.stderr)
        return None

    # Suppress sklearn InconsistentVersionWarning — the classifier was trained on
    # sklearn 1.9.0 and is running on 1.8.0. The model is functionally compatible
    # (TF-IDF + LogReg), the version mismatch is a known-safe pickle format difference.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Trying to unpickle estimator")
        pipeline = joblib.load(model_path)
    classes = list(pipeline.classes_)

    lines = _normalize_jd_punctuation(jd_text).splitlines()

    buckets = _empty_extraction_buckets()

    current_header = ""
    fallback_queue: list[tuple[str, str, str]] = []

    for line in lines:
        clean = line.strip()
        if not clean:
            continue

        # CR-105 fix: the `URL: <url>` first-line convention (see _parse_url_and_jd) is
        # metadata, not a JD bullet. Real callers already strip it before this function
        # ever sees jd_text, but a standalone/direct call (how the original Limble demo
        # was run) can hand this function raw text -- guard here too rather than rely on
        # every caller remembering to strip it first. A real miss: the URL line got sent
        # to the LLM fallback and landed in training_data_feedback.csv labeled "preferred".
        if re.match(r"^url:\s*https?://", clean, re.I):
            continue

        bucket, is_label = classify_jd_header(line)
        if bucket is not None:
            current_header = clean
            if is_label:
                continue

        if _IGNORE_SECTION_HEADERS.match(clean) or _TRACKING_TAG_RE.match(clean):
            current_header = "IGNORE"
            continue

        if current_header == "IGNORE":
            continue

        bullet_clean = clean.lstrip("-•*◦▪▸→").strip()
        for item in _qual_line_items(bullet_clean):
            if _is_list_leadin(item):
                lead_bucket, lead_label = classify_jd_header(item)
                if lead_bucket is not None:
                    current_header = item
                continue
            if not _is_boilerplate_item(item):
                combo_header = current_header or ""
                preferred_header = (
                    (classify_jd_header(combo_header)[0] == "preferred")
                    or "preferred" in combo_header.lower()
                    or "great to have" in combo_header.lower()
                    or "nice to have" in combo_header.lower()
                )
                if preferred_header and _INLINE_REQUIRED_RE.search(item):
                    combo_header = "required"
                combo_text = f"[HEADER] {combo_header}: {item}" if combo_header else item

                if current_header == "required" and _INLINE_PREFERRED_RE.search(item):
                    buckets["preferred"].append(item)
                    continue

                from stage0_classifier_contract import is_disposition_culture_line

                if is_disposition_culture_line(item):
                    buckets["culture"].append(item)
                    continue

                pred = pipeline.predict([combo_text])[0]
                proba = pipeline.predict_proba([combo_text])[0]
                conf = proba[classes.index(pred)]

                if conf < 0.65:
                    fallback_queue.append((combo_text, item, combo_header))
                else:
                    buckets[pred].append(item)

    return buckets, fallback_queue


def _extract_sections_nlp(jd_text: str) -> dict[str, list[str]] | None:
    """NLP (TF-IDF + LogReg) section extraction with a bounded fallback.

    Confident lines stay on the local classifier. Uncertain lines go to Groq/Gemini
    unless APPLYR_STAGE0_SUBSCRIPTION_ADAPTER is on, in which case they go to the
    Stage 0 subscription adapter and never spill into a metered API.
    """
    collected = _collect_nlp_section_candidates(jd_text)
    if collected is None:
        return None
    buckets, fallback_queue = collected
    unresolved_for_review = _resolve_uncertain_extraction(fallback_queue, buckets)  # Implements FR-328 / AC-426
    _recover_mixed_responsibilities(buckets)
    if unresolved_for_review:
        buckets["unresolved_for_review"] = unresolved_for_review
    return buckets


def _subscription_extraction_enabled() -> bool:
    """Return True only when the CR-114 adapter switch is on. Implements FR-328."""
    from stage0_subscription_adapter import AdapterConfig, adapter_enabled
    return adapter_enabled(AdapterConfig())


def _record_unresolved(
    fallback_queue: list[tuple[str, str, str]],
    reason: str,
    *,
    model_call_occurred: bool,
    indexes: list[int] | None = None,
) -> list[dict]:
    """Record unresolved extraction lines without silently bucketing them."""
    selected = range(len(fallback_queue)) if indexes is None else indexes
    return [
        {
            "text": fallback_queue[idx][1],
            "header": fallback_queue[idx][2],
            "reason": reason,
            "model_call_occurred": model_call_occurred,
        }
        for idx in selected
    ]


def _resolve_uncertain_extraction(
    fallback_queue: list[tuple[str, str, str]],
    buckets: dict[str, list[str]],
) -> list[dict]:
    """Classify low-confidence lines or keep them in CR-112 review. Implements FR-328 / AC-426.

    The subscription adapter, when enabled, replaces Groq/Gemini for this batch only.
    It never writes training labels and never silently drops a queued line.
    """
    if not fallback_queue:
        return []
    if _subscription_extraction_enabled():
        return _resolve_uncertain_extraction_subscription(fallback_queue, buckets)
    return _resolve_uncertain_extraction_llm(fallback_queue, buckets)


def _resolve_uncertain_extraction_subscription(
    fallback_queue: list[tuple[str, str, str]],
    buckets: dict[str, list[str]],
) -> list[dict]:
    """Use the bounded Stage 0 adapter. Never fall through to Groq or Gemini."""
    from stage0_subscription_adapter import (
        AdapterConfig,
        AdapterBudget,
        Stage0Item,
        run_stage0_subscription,
    )

    print(
        f"    [NLP] Sending {len(fallback_queue)} ambiguous lines to subscription adapter...",
        file=sys.stderr,
    )
    items = [
        Stage0Item(f"e{idx}", combo_text)
        for idx, (combo_text, _bullet, _header) in enumerate(fallback_queue)
    ]
    config = AdapterConfig(enabled=True)
    result = run_stage0_subscription(
        "extraction", items, config=config, budget=AdapterBudget(config)
    )
    print(
        f"    [NLP] subscription adapter outcome={result.outcome} "
        f"calls={result.calls} minutes={result.subscription_minutes:.4f} "
        f"api_cents={result.api_cents} reason={result.reason}",
        file=sys.stderr,
    )
    called = result.outcome != "exhausted" or result.calls > 0
    resolved: set[int] = set()
    for row in result.results:
        item_id = str(row.get("item_id") or "")
        if not item_id.startswith("e"):
            continue
        try:
            idx = int(item_id[1:])
        except ValueError:
            continue
        bucket = row.get("bucket")
        if idx < 0 or idx >= len(fallback_queue) or bucket not in buckets:
            continue
        resolved.add(idx)
        line = fallback_queue[idx][1]
        buckets[_leftover_bucket(str(bucket), line)].append(line)
    missing = [
        idx for idx, _item in enumerate(fallback_queue) if idx not in resolved
    ]
    if result.outcome in {"ok", "cache_hit"} and not missing:
        return []
    if missing and resolved:
        return _record_unresolved(
            fallback_queue,
            "partial_mapping_unresolved",
            model_call_occurred=True,
            indexes=missing,
        )
    if result.outcome == "exhausted":
        return _record_unresolved(
            fallback_queue, "no_provider", model_call_occurred=bool(result.calls)
        )
    if result.outcome == "disabled":
        return _record_unresolved(
            fallback_queue, "no_provider", model_call_occurred=False
        )
    reason = "parse_failure" if called else "no_provider"
    return _record_unresolved(fallback_queue, reason, model_call_occurred=called)


def _resolve_uncertain_extraction_llm(
    fallback_queue: list[tuple[str, str, str]],
    buckets: dict[str, list[str]],
) -> list[dict]:
    """Hosted-tool uncertainty path for leftover JD lines. Implements CR-112 dump-site rules."""
    from stage0_classifier_contract import (
        EXTRACTION_SYSTEM,
        extraction_user_prompt,
        parse_extraction_mapping,
    )
    from utils import call_llm, extract_json_from_text, resolve_task_providers

    print(f"    [NLP] Sending {len(fallback_queue)} ambiguous lines to LLM fallback...", file=sys.stderr)
    ids = [str(i) for i in range(len(fallback_queue))]
    user_prompt = extraction_user_prompt(
        [(item_id, combo_text) for item_id, (combo_text, _, _) in zip(ids, fallback_queue)]
    )

    result = call_llm(
        system_prompt=EXTRACTION_SYSTEM,
        user_prompt=user_prompt,
        # Tool order is user-configurable. Default list is not Applyr behavior.
        provider_override=resolve_task_providers("stage0_extraction", ["groq", "gemini"]),
    )

    if result:
        json_str = extract_json_from_text(result)
        try:
            import json
            payload = json.loads(json_str)
            mapping = parse_extraction_mapping(payload, ids)
            resolved_indices: set[int] = set()
            # Implements FR-327 / AC-425: runtime fallback answers are not training labels.
            for item_id, bucket in mapping.items():
                try:
                    idx = int(item_id)
                except (TypeError, ValueError):
                    continue
                if idx < 0 or idx >= len(fallback_queue) or bucket not in buckets:
                    continue
                resolved_indices.add(idx)
                _, bullet_clean, _ = fallback_queue[idx]
                buckets[_leftover_bucket(bucket, bullet_clean)].append(bullet_clean)
            unresolved_for_review: list[dict] = []
            for idx, (_combo_text, bullet_clean, header) in enumerate(fallback_queue):
                if idx in resolved_indices:
                    continue
                unresolved_for_review.append({
                    "text": bullet_clean,
                    "header": header,
                    "reason": "partial_mapping_unresolved",
                    "model_call_occurred": True,
                })
            return unresolved_for_review
        except Exception as e:
            print(f"    [NLP Error] Failed to parse LLM fallback: {e}", file=sys.stderr)
            return _record_unresolved(
                fallback_queue, "parse_failure", model_call_occurred=True
            )
    return _record_unresolved(fallback_queue, "no_provider", model_call_occurred=False)

def _extract_sections_llm(jd_text: str) -> dict[str, list[str]] | None:
    """LLM section extraction pinned to STAGE0_EXTRACT_MODEL.

    Python harvests candidate lines; the model returns integer ids only.
    Returns None only when STAGE0_SECTION_MODE=deterministic (caller then
    uses the regex extractor on purpose). Any load/run/parse failure raises
    Stage0ExtractError -- the regex path is not a silent backup.
    """
    import pipeline_env
    if pipeline_env.stage0_section_mode() == "deterministic":
        return None

    from stage0_extract import (
        clean_jd_text,
        harvest_extract_candidates,
        format_candidates_for_prompt,
        resolve_labeled_buckets,
    )

    cleaned_jd = clean_jd_text(jd_text)
    candidates = harvest_extract_candidates(jd_text)
    if not candidates:
        raise Stage0ExtractError(
            f"{STAGE0_EXTRACT_MODEL} cannot extract: no candidate lines after "
            "cleanup. No regex fallback."
        )

    try:
        from utils import call_llm, extract_json_from_text
        from model_manager import LocalModelUnavailable, ensure_local_model_available
    except ImportError as exc:
        raise Stage0ExtractError(_extract_unavailable_message(str(exc))) from exc

    try:
        ensure_local_model_available(STAGE0_EXTRACT_MODEL)
    except LocalModelUnavailable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise Stage0ExtractError(str(exc)) from exc

    # Local-only, hard-pinned (2026-08-17, Jason-supplied correction): this
    # stage runs on every incoming JD in every batch, so a silent cloud
    # fallback here means real per-JD billing outside Jason's Claude
    # subscription -- confirmed real on the first live test, which quietly
    # called the configured Gemini API key. Same "never silently substitute a
    # different provider" contract as llm_stages.py's "rewrite" stage.
    # Model pinned to STAGE0_EXTRACT_MODEL (2026-08-17, measured):
    # call_llm's default local model (llama3.1:8b-instruct-q5_K_M, Jason's
    # general-purpose local default) was tested head to head against every
    # other locally-available model on the real PracticeTek JD and was the
    # clear outlier -- it returned only the 4 top-level category headers plus
    # 2 sub-bullets for "responsibilities" (6 items), silently dropping 10 of
    # 12 real duty statements (Product Quality Assurance, Fluency with Data,
    # Voice of the Customer, User Experience Design, Business Outcome
    # Ownership, Product Vision and Roadmapping, Strategic Impact,
    # Stakeholder Management, Team Leadership, Managing Up all vanished).
    # qwen2.5:7b-instruct-q4_K_M captured all 12 correctly in 23s -- faster
    # than every 14B model tested (qwen2.5-coder:14b, gemma2:9b, qwen3:14b,
    # ministral-3-14b all took 45-65s) and more complete than the 8B default.
    # Every model tested got "required" fully correct with zero invented
    # items (id lookup drops copied wording and unknown ids); the real
    # differentiation was responsibilities/culture completeness, where this
    # model won clearly. phi4:14b crashed the
    # underlying llama-server process outright on this machine (unrelated to
    # this code) and is not usable at all here.
    # Retrieval-augmented few-shot (2026-08-19 self-healing plan, item 3):
    # replaces the single hardcoded Empower/Exchange example that used to
    # live directly in the template with 1-3 examples retrieved from
    # data/fit_rubric_golden_set.json's confirmed-real internal-terms
    # cases, ranked by token overlap with this specific JD. Never raises --
    # an empty bank (or the file missing entirely, e.g. a fresh checkout
    # without the private data/ dir) means an empty few_shot_block, and the
    # prompt still works exactly as it did before this existed.
    few_shot_block = ""
    try:
        from fit_rubric_examples import retrieve_examples, format_examples_for_prompt
        examples = retrieve_examples(cleaned_jd[:4000], "internal_term", k=3)
        rendered = format_examples_for_prompt(examples)
        if rendered:
            few_shot_block = "\n" + rendered + "\n"
    except Exception:
        pass

    prompt = _SECTION_SPLIT_USER_TEMPLATE.format(
        candidate_block=format_candidates_for_prompt(candidates),
        few_shot_block=few_shot_block,
    )
    try:
        raw = call_llm(
            _SECTION_SPLIT_SYSTEM_PROMPT,
            prompt,
            temperature=0.0,
            response_mime_type="application/json",
            provider_override=["local"],
            model=STAGE0_EXTRACT_MODEL,
        )
    except Exception as exc:
        print(f"ERROR: {_extract_unavailable_message(str(exc))}", file=sys.stderr)
        raise Stage0ExtractError(_extract_unavailable_message(str(exc))) from exc

    if not raw:
        raise Stage0ExtractError(
            _extract_unavailable_message(
                "empty response — the model did not load or returned nothing"
            )
        )

    try:
        cleaned = extract_json_from_text(raw)
        data = json.loads(cleaned)
    except Exception:
        try:
            data = json.loads(raw.strip().strip("`").removeprefix("json").strip())
        except Exception as exc:
            raise Stage0ExtractError(
                f"{STAGE0_EXTRACT_MODEL} returned unparseable output for "
                "requirement extraction. No fallback extractor."
            ) from exc

    if not isinstance(data, dict):
        raise Stage0ExtractError(
            f"{STAGE0_EXTRACT_MODEL} returned a non-object JSON payload for "
            "requirement extraction. No fallback extractor."
        )

    result = resolve_labeled_buckets(candidates, data)

    if not any(result.values()):
        raise Stage0ExtractError(
            f"{STAGE0_EXTRACT_MODEL} produced no labeled requirement lines. "
            "No regex fallback."
        )

    # internal_terms (2026-08-19, Jason-supplied): short proper nouns, not
    # harvested lines. Still checked as a real substring of the *cleaned* JD
    # so HTML-entity postings cannot invent a product name. Unknown / copied
    # bucket strings are already dropped by resolve_labeled_buckets.
    internal_terms: list[str] = []
    raw_terms = data.get("internal_terms")
    if isinstance(raw_terms, list):
        for term in raw_terms:
            term = str(term).strip()
            if not term or not (1 <= len(term) <= 60):
                continue
            if not _is_verbatim_substring(term, cleaned_jd):
                continue
            internal_terms.append(term)
    result["internal_terms"] = internal_terms
    return result


def _recover_mixed_responsibilities(buckets: dict[str, list[str]]) -> None:
    """Move qualification-shaped lines out of responsibilities when required is empty.

    Mutates *buckets* in place. No-op when required already has items, or when
    responsibilities is empty. Preferred markers (leading Bonus:) go to preferred.
    Ambiguous non-duty / non-qual lines stay in responsibilities (avoid inventing
    soft-gap noise from culture fluff that leaked into the duty list).
    """
    if buckets.get("required") or not buckets.get("responsibilities"):
        return

    kept_resp: list[str] = []
    from stage0_classifier_contract import is_disposition_culture_line

    for item in buckets["responsibilities"]:
        if _INLINE_PREFERRED_RE.search(item):
            buckets["preferred"].append(item)
            continue
        if is_disposition_culture_line(item):
            buckets["culture"].append(item)
            continue
        if _looks_like_qualification(item) and not _looks_like_duty(item):
            buckets["required"].append(item)
            continue
        if _looks_like_duty(item):
            kept_resp.append(item)
            continue
        # Ambiguous: leave in responsibilities rather than invent soft gaps
        kept_resp.append(item)

    buckets["responsibilities"] = kept_resp


def _required_item_text(item) -> str:
    if isinstance(item, dict):
        return str(item.get("item") or "")
    return str(item or "")


def _count_qualification_required(required_items: list) -> int:
    """Count required lines that look like hire criteria, not culture copy."""
    return sum(
        1
        for item in (required_items or [])
        if _looks_like_qualification(_required_item_text(item))
    )


def _detect_thin_jd(jd_text: str, required_items: list) -> bool:
    """True when the JD is sparse (very short AND/OR almost no structured requirements).

    A JD with ≥2 qualification-shaped required items is never thin regardless of
    raw word count. Culture sentences stuffed into required do not count.
    Otherwise:
    - under 80 words → thin (original threshold)
    - zero qualification-shaped requireds and under 150 words → thin (2026-08-08
      Cluster C item 10: clear_capital-class headerless prose at ~99 words was
      missing the old cutoff and produced a false clean Stage 0 shape)
    """
    if _count_qualification_required(required_items) >= 2:
        return False
    word_count = len(re.findall(r"\w+", jd_text or ""))
    if word_count < 80:
        return True
    if _count_qualification_required(required_items) == 0 and word_count < 150:
        return True
    return False


# 2026-09-01 Improvement #9: reordered by priority (enterprise > public >
# PE-backed > VC-backed > startup > unknown) so a JD mentioning both
# "Fortune 500" and "startup" reports the more specific, higher-priority
# signal. Added patterns for bootstrapped, profitable, hypergrowth,
# scale-up, post-Series-B, and employee-count ranges.
_STAGE_SIGNALS: list[tuple[re.Pattern, str]] = [
    # Priority 1: enterprise / large company
    (re.compile(r"\b(?:fortune\s+\d{3}|enterprise\s+saas|global\s+enterprise|large\s+enterprise)\b", re.I), "enterprise/large company"),
    # Priority 2: public company
    (re.compile(r"\b(?:ipo|publicly\s+traded|nasdaq|nyse|stock\s+exchange\s+listed)\b", re.I), "public company"),
    # Priority 3: pre-IPO
    (re.compile(r"\bpre.ipo\b", re.I), "pre-IPO"),
    # Priority 4: PE-backed
    (re.compile(r"\b(?:private\s+equity|pe.backed)\b", re.I), "PE-backed"),
    # Priority 5: VC-backed (specific series)
    (re.compile(r"\bseries\s+[abcde]\b", re.I), "VC-backed (Series found)"),
    (re.compile(r"\bpost.series.b\b", re.I), "VC-backed (post-Series B)"),
    # Priority 6: bootstrapped / profitable
    (re.compile(r"\bbootstrapped\b", re.I), "bootstrapped"),
    (re.compile(r"\bprofitable\s+(?:company|business|startup)\b", re.I), "profitable company"),
    # Priority 7: hypergrowth / scale-up
    (re.compile(r"\bhypergrowth\b", re.I), "hypergrowth company"),
    (re.compile(r"\bscale.?up\b", re.I), "scale-up"),
    # Priority 8: seed-stage startup
    (re.compile(r"\bseed\s+(?:stage|funded|round)\b", re.I), "seed-stage startup"),
    # Priority 9: generic startup / growth-stage
    (re.compile(r"\b(?:startup|early.stage|growth.stage)\b", re.I), "startup / growth-stage"),
    # Priority 10: employee-count ranges (weaker signal)
    (re.compile(r"\b(?:50|100|200|500|1000|2000|5000|10000)\+?\s+(?:employees|people|team\s+members)\b", re.I), "mid-to-large company (by employee count)"),
]


def _detect_stage_signal(jd_text: str) -> str:
    """Return a human-readable stage signal or the standard unknown string.

    2026-09-01 Improvement #9: patterns are now priority-ordered (enterprise
    > public > PE-backed > VC-backed > startup > unknown) so a JD mentioning
    multiple signals reports the most specific one. First-match wins, so the
    list order above IS the priority order.
    """
    for pat, label in _STAGE_SIGNALS:
        if pat.search(jd_text):
            return label
    return "not stated in JD text -- unknown, not inferred"


# ---------------------------------------------------------------------------
# PO solo-backlog-ownership signal (2026-08-18, Jason-supplied)
# ---------------------------------------------------------------------------
# Product Owner postings vary in flavor: some are collaborative-with-engineering
# (the same shape of work Jason did under the PO title at Cision for 4 years),
# others expect a solo backlog owner writing detailed requirements/acceptance
# criteria upfront with little engineering back-and-forth. Only the second
# flavor is a real fit question. This is a soft, human-in-the-loop signal --
# it never Skips on its own (see _determine_tier: SOFT gaps route to Tier 2,
# not Skip), it just surfaces the read for Jason to confirm at triage.

_PO_TITLE_RE = re.compile(r"\bproduct\s+owner\b", re.I)

# Defaults used when prefs doesn't carry these keys (e.g. older prefs files,
# _PREFS_MINIMAL in tests). candidate_preferences.json carries the live,
# user-editable list -- see PRESERVE_PIPELINE_PREF_KEYS in jobSearchPrefs.ts.
_DEFAULT_PO_SOLO_BACKLOG_FLAGS = [
    "business requirements document",
    "brd",
    "functional specification document",
    "fsd",
    "waterfall",
    "author detailed user stories and acceptance criteria independently",
    "sole owner of the backlog",
    "requirements gathering and documentation",
]
_DEFAULT_PO_SOLO_BACKLOG_MITIGATORS = [
    "partner with engineering",
    "work closely with engineering",
    "pair with developers",
    "collaborate with engineering on requirements",
]


def _detect_po_solo_backlog_signal(role: str, jd_text: str, prefs: dict | None) -> dict | None:
    """Return a SOFT flagged_gaps entry when a PO-titled JD reads as solo
    backlog ownership with no collaborative-with-engineering language, else None.
    """
    if not _PO_TITLE_RE.search(role or ""):
        return None

    prefs = prefs or {}
    flags = prefs.get("po_solo_backlog_flags") or _DEFAULT_PO_SOLO_BACKLOG_FLAGS
    mitigators = prefs.get("po_solo_backlog_mitigators") or _DEFAULT_PO_SOLO_BACKLOG_MITIGATORS
    if not isinstance(flags, list) or not flags:
        return None

    lower = (jd_text or "").lower()
    hit_flags = [f for f in flags if isinstance(f, str) and f.strip().lower() in lower]
    if not hit_flags:
        return None
    if any(isinstance(m, str) and m.strip().lower() in lower for m in mitigators or []):
        return None

    return {
        "item": (
            "Stage 0: PO posting reads as solo backlog ownership "
            f"({', '.join(hit_flags[:3])}) with no collaborative-with-engineering "
            "language found"
        ),
        "gap_class": "SOFT",
        "bridge": (
            "po_solo_backlog_signal -- confirm at triage whether this matches the "
            "collaborative PO work already done at Cision, or the solo-execution "
            "flavor that's the real fit risk"
        ),
    }


def _parse_url_and_jd(raw_text: str) -> tuple[str, str]:
    """
    Parse optional `URL: <url>` first line convention.

    Returns (url_or_empty, jd_body).
    """
    lines = raw_text.splitlines()
    if not lines:
        return "", raw_text
    first = lines[0].strip()
    if first.lower().startswith("url:"):
        url = first[4:].strip()
        body = "\n".join(lines[1:]).lstrip("\n")
        return url, body
    return "", raw_text


# ---------------------------------------------------------------------------
# ATS-platform page-chrome stripping (CR-092, 2026-08-15)
# ---------------------------------------------------------------------------
# Ingestion (CSV import / Sync export) sometimes scrapes a job board's own page
# chrome along with the real posting text -- confirmed real on 3 of 9 flagged
# archived JDs, byte-identical Greenhouse footer in each ("Apply for this Job /
# Powered by / Privacy PolicySecurityVulnerability Disclosure"). This is an
# ingestion-time artifact, not JD content, and should never reach bucketing at
# all -- unlike arbitrary in-JD boilerplate (EEO text, anti-scam paragraphs,
# handled item-by-item in _is_boilerplate_item), ATS platform chrome comes from
# a small, closed, identifiable set of platforms and is cheap to strip as a
# whole trailing block before section extraction ever runs. Deliberately
# narrow and trailing-anchored (matches only at/near the end of the JD text)
# so a real JD sentence that happens to contain "privacy" or "apply" mid-body
# is never touched.
_ATS_CHROME_TRAILERS: list[re.Pattern[str]] = [
    # Greenhouse: "Apply for this Job\nPowered by\n\nPrivacy PolicySecurityVulnerability Disclosure"
    re.compile(
        r"\n\s*Apply for this Job\s*\n\s*Powered by\s*\n+\s*"
        r"Privacy Policy\s*Security\s*Vulnerability Disclosure\s*\Z",
        re.I,
    ),
]


def _strip_ats_chrome(jd_text: str) -> str:
    """Strip a known ATS-platform page-chrome trailer (Greenhouse, etc.) from
    the end of *jd_text*, if present. Returns jd_text unchanged if no known
    trailer matches -- never touches the middle of a JD, only a matched
    trailing block, so this can only ever remove text, never corrupt it."""
    stripped = jd_text
    for pattern in _ATS_CHROME_TRAILERS:
        stripped = pattern.sub("", stripped)
    return stripped.rstrip()


# ---------------------------------------------------------------------------
# Gap classification (CR-093 — evidence-scale engine, replaces the regex
# chain that used to live here: _item_has_anchor, _is_unbridgeable_advanced_
# degree, _unbridgeable_domain_requirement, _get_hard_tool_pattern dispatch,
# _classify_single_clause, _split_compound_item. Jason, 2026-08-19: "regex
# wasn't working and we have been bypassing it completely either way" --
# removed outright rather than kept as a fallback. One LLM judgment call per
# requirement line (scripts/evidence_scale.py) now decides gate class and
# 0-4 evidence level; see docs/spec/05-change-requests/CR-093-evidence-
# scale-fit-engine.md for the full rationale. No local fallback on LLM
# failure here — evidence_scale.EvidenceClassificationError propagates up
# uncaught, by design (a silent fallback to weaker logic is the exact
# failure mode this replaces).
#
# _get_hard_tool_pattern / HARD_BLOCKED_TOOLS and _is_administratively_
# satisfied / _BACHELORS_SATISFIED_RE / _HIGHER_DEGREE_MANDATORY_RE /
# _YEARS_EXPERIENCE_LEADIN_RE below are DELIBERATELY NOT removed —
# build_authoring_packet.py imports them directly for a different purpose
# (excluding claim attachment to a line the candidate can't honestly claim,
# or that's already resolved by a separate deterministic mechanism),
# unrelated to Stage 0 gate/tier classification. See CR-093's "Scope
# boundary" section. No longer used for Stage 0 gap classification itself
# (evidence_scale.classify_requirement's prompt handles the equivalent
# "already satisfied elsewhere" reasoning for that purpose instead).
# ---------------------------------------------------------------------------

# Years-of-experience: already independently parsed and gated by
# seniority_gate.check_years_gate() against candidate_preferences.json's real
# threshold. Bachelor's-degree: Jason has one (workExperience.md Section 7).
# Deliberately does NOT exempt lines that mandate a higher degree as required
# (Master's/MBA/PhD/JD/MD "required") -- those remain real gaps. A mention of a
# higher degree as merely *preferred* alongside a Bachelor's requirement is not a
# gap (the Bachelor's already satisfies the line).
_YEARS_EXPERIENCE_LEADIN_RE = re.compile(
    r"^(?:minimum\s+(?:of\s+)?|approximately\s+)?"
    r"\d{1,2}\s*[-–+]?\s*(?:to\s+|-\s*)?\d{0,2}\+?\s*years?\b",
    re.I,
)
_BACHELORS_SATISFIED_RE = re.compile(
    r"\b(?:bachelor(?:'s|s)?(?:\s+or\s+master'?s?)?\s+degree|undergraduate\s+degree)\b",
    re.I,
)
_HIGHER_DEGREE_MANDATORY_RE = re.compile(
    r"\b(?:master'?s?|mba|ph\.?d\.?|j\.?d\.?|m\.?d\.?)\s+degree\s+required\b|"
    r"\brequires?\s+an?\s+(?:master'?s?|mba|ph\.?d\.?)\b",
    re.I,
)
# CR-112 Story 3.4: eligibility-framed screening / nights-and-weekends lines
# are not product-roadmap claims. Framing is required so "Own the background
# check product roadmap" stays scorable. No drug-test or on-call matchers.
_ADMIN_BACKGROUND_RE = re.compile(
    r"(?:must\s+pass|subject\s+to|(?:is|are)\s+required|(?:^|\b)required\b).{0,80}"
    r"(?:background\s+check|fingerprints?|fingerprinting|"
    r"level\s*(?:ii|2)\s+fingerprint)"
    r"|"
    r"(?:background\s+check|fingerprints?|fingerprinting|"
    r"level\s*(?:ii|2)\s+fingerprint).{0,80}"
    r"(?:must\s+pass|subject\s+to|(?:is|are)\s+required|(?:^|\b)required\b)",
    re.I,
)
_ADMIN_SCHEDULE_RE = re.compile(
    r"\b(?:nights and weekends|weekend availability)\b",
    re.I,
)


def _is_administratively_satisfied(item_lower: str) -> bool:
    """True for items that should never be treated as real gaps needing a
    claim bridge -- consumed by build_authoring_packet.py, not by Stage 0
    classification (CR-093 moved that reasoning into evidence_scale.py's
    prompt instead). Deliberately narrow and conservative:
    citizenship/work-authorization/security-clearance/travel/supervisory-
    responsibility statements are NOT covered here (left for a separate,
    more careful pass -- some are legally sensitive and shouldn't be
    silently resolved without confirming Jason's actual status).
    CR-112 Story 3.4: eligibility-framed fingerprint / background-check and
    nights-and-weekends lines also count so an empty score gets the admin
    bridge instead of the Stage-0-anchored filler. Implements FR-305 / AC-402.
    """
    if _YEARS_EXPERIENCE_LEADIN_RE.match(item_lower.strip()):
        return True
    if _BACHELORS_SATISFIED_RE.search(item_lower) and not _HIGHER_DEGREE_MANDATORY_RE.search(item_lower):
        return True
    if _ADMIN_BACKGROUND_RE.search(item_lower) or _ADMIN_SCHEDULE_RE.search(item_lower):
        return True
    return False


def _classify_one_item(
    item: str,
    work_exp: str,
    is_required: bool = True,
    company: str = "",
    internal_terms: list[str] | None = None,
) -> dict:
    """
    Classify a single required/preferred item string via the evidence-scale
    LLM judgment (CR-093). Returns the same dict shape the old regex-based
    version returned, so classify_gaps()/_determine_tier() and every other
    downstream consumer need no changes:

        {
            "item": str,
            "anchor": str,             # human-readable reasoning, or "none"
            "gap": bool,
            "gap_class": "HARD" | "SOFT" | None,
            "gap_source": "degree" | "domain" | "role_exclusion" | "certification" | "tool" | None,  # only when gap_class == "HARD"
            "domain_soft": bool,
            "evidence_level": int,     # 0-4, new — feeds compute_fit_score()
            "confidence": str,         # "high" | "medium" | "low", new
        }

    Raises evidence_scale.EvidenceClassificationError on any LLM failure --
    callers must not catch this and substitute a weaker heuristic.
    """
    from evidence_scale import classify_requirement

    judgment = classify_requirement(
        item,
        work_exp,
        is_required=is_required,
        company=company,
        internal_terms=internal_terms,
    )
    return judgment.to_legacy_dict()


def _prepare_skill_confirmations(
    items: list[str],
    *,
    folder: Path,
    company: str,
    role: str,
    internal_terms: list[str] | None,
    db_path: Path | str | None = None,
) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Create pending unknown-tool questions and return confirmed presence terms."""
    candidates = named_skill_candidates(
        items,
        known_terms=set(_load_skills_catalog_terms_shared()),
        internal_terms=internal_terms,
    )
    pending: list[dict[str, str]] = []
    confirmed_terms: dict[str, str] = {}
    for candidate in candidates:
        memory = get_skill_memory(candidate.skill_key, db_path)
        if memory:
            if memory.get("decision") == "CONFIRMED_USE":
                confirmed_terms[candidate.skill_key] = candidate.display_name
            continue
        requirement = next(
            (
                line
                for line in items
                if re.search(re.escape(candidate.display_name), line, re.IGNORECASE)
            ),
            candidate.display_name,
        )
        create_skill_confirmation(
            db_path=db_path,
            skill_key=candidate.skill_key,
            display_name=candidate.display_name,
            requirement=requirement,
            opportunity_key=folder.name,
            opportunity_company=company,
            opportunity_title=role,
            evidence_excerpt=(
                "Applyr found this named tool in the job description, but it is not "
                "in verified work history."
            ),
            decision_basis=(
                "Deterministic named-tool scan of the job description. The tool is "
                "not in verified work history, so Stage 0 cannot treat it as known."
            ),
            uncertainty="unknown_named_tool",
        )
        pending.append(
            {
                "review_key": f"skill:{candidate.skill_key}",
                "skill_key": candidate.skill_key,
                "display_name": candidate.display_name,
                "requirement": requirement,
            }
        )
    return pending, confirmed_terms


def _cap_confirmed_presence(
    result: dict,
    item: str,
    confirmed_terms: dict[str, str],
) -> dict:
    """Keep a bare skill attestation at evidence level one during scoring."""
    for display_name in confirmed_terms.values():
        if not re.search(re.escape(display_name), item, re.IGNORECASE):
            continue
        result["evidence_level"] = min(int(result.get("evidence_level") or 0), 1)
        result["gap"] = True
        result["gap_class"] = "SOFT"
        result["domain_soft"] = False
        result["anchor"] = (
            f"User-confirmed use of {display_name}; presence only, with no "
            "source-backed duration, proficiency, scope, ownership, or outcome."
        )
        break
    return result


def _prepare_hard_gate_reviews(
    classified_required: list[dict],
    classified_preferred: list[dict],
    flagged_gaps: list[dict],
    *,
    folder: Path,
    company: str,
    role: str,
    db_path: Path | str | None,
) -> list[dict[str, str]]:
    """Persist model-proposed HARD decisions before allowing a cascade run to skip.

    A HARD result is a high-consequence decision. It may be confirmed or
    rejected in Review Center, but it must never become an automatic Skip
    merely because a provider returned the label. ``KEEP_ELIGIBLE`` removes
    the hard gate while retaining the gap as a visible soft gap. A completed
    ``CONFIRM_HARD`` leaves the original hard result intact.
    """
    candidates: list[tuple[str, str, dict]] = []
    for bucket, results in (
        ("required", classified_required),
        ("preferred", classified_preferred),
    ):
        for ordinal, result in enumerate(results):
            if result.get("gap_class") == "HARD":
                candidates.append(
                    (bucket, make_item_key(bucket, str(result.get("item") or ""), ordinal), result)
                )
    pending: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for bucket, item_key, result in candidates:
        item = str(result.get("item") or "").strip()
        if not item or (bucket, item) in seen:
            continue
        seen.add((bucket, item))
        review_key = f"hard:{folder.name}:{item_key}"
        decision = get_hard_gate_decision(review_key, db_path)
        if decision is None:
            create_hard_gate_review(
                db_path=db_path,
                item_key=item_key,
                requirement=item,
                opportunity_key=folder.name,
                opportunity_company=company,
                opportunity_title=role,
                evidence_excerpt=str(result.get("anchor") or ""),
                decision_basis=(
                    f"Stage 0 proposed a HARD gate ({result.get('gap_source') or 'unspecified source'}) "
                    f"at evidence level {result.get('evidence_level')} with "
                    f"{result.get('confidence') or 'unknown'} confidence."
                ),
                uncertainty=str(result.get("confidence") or "unknown"),
            )
            pending.append(
                {
                    "review_key": review_key,
                    "question_type": "hard_gate_review",
                    "requirement": item,
                    "item_key": item_key,
                }
            )
            continue
        if decision == "KEEP_ELIGIBLE":
            result["gap"] = True
            result["gap_class"] = "SOFT"
            result["gap_source"] = None
            result["domain_soft"] = False
            result["anchor"] = (
                "User chose KEEP_ELIGIBLE; retain this as a visible gap without "
                "using it as an automatic hard disqualification."
            )
            for flagged in flagged_gaps:
                if flagged.get("item") == item and flagged.get("gap_class") == "HARD":
                    flagged["gap_class"] = "SOFT"
                    flagged["gap_source"] = None
                    flagged["anchor"] = result["anchor"]
    return pending


def _sha256_text(value: str) -> str:
    """Return a content hash for a checkpoint input or item."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def classify_gaps(
    required_items: list[str],
    preferred_items: list[str],
    work_exp: str = "",
    vocab: set[str] | None = None,
    company: str = "",
    internal_terms: list[str] | None = None,
    attested_skill_terms: dict[str, str] | None = None,
    cached_results: dict[str, dict] | None = None,
    judgment_callback: Callable[[str, int, str, dict], None] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Classify required and preferred items for gaps via the evidence-scale
    engine (CR-093).

    Returns (classified_required, classified_preferred, flagged_gaps).
    flagged_gaps contains required items where gap=True (HARD or SOFT), plus
    preferred items marked domain_soft or a confirmed HARD gap.

    work_exp: candidate ground-truth text passed to the LLM judgment call.
    Required in practice — omitting it starves every judgment of real
    evidence (found live during CR-093 validation: the wrong evidence-
    context file alone caused a real scoring miss).
    vocab: accepted for call-site backward compatibility, no longer used —
    the anchor-vocabulary tag-matching approach it fed is exactly what this
    engine replaces.
    company / internal_terms: same meaning as before — excludes the
    employer's own name/product names from being misread as an external
    tool requirement.
    attested_skill_terms: user-confirmed skill names that remain capped at
    evidence level 1 until separately promoted.
    cached_results: completed checkpoint results keyed by bucket/item ordinal,
    produced by the CR-108 evidence cascade. Items missing from cached_results
    are a real error (the cascade should have covered them) — raises
    Stage0ExtractError rather than silently falling back.
    judgment_callback: called after each newly computed judgment.
    """
    del vocab  # deprecated, unused — see docstring

    classified_required: list[dict] = []
    for ordinal, item in enumerate(required_items):
        cache_key = make_item_key("required", item, ordinal)
        result = (cached_results or {}).get(cache_key)
        if result is None:
            raise Stage0ExtractError(
                f"Required item {ordinal} missing from cascade cached_results "
                f"({item[:60]!r}) — cascade should have classified it via Groq/Gemini."
            )
        classified_required.append(
            _cap_confirmed_presence(result, item, attested_skill_terms or {})
        )

    classified_preferred: list[dict] = []
    for ordinal, item in enumerate(preferred_items):
        cache_key = make_item_key("preferred", item, ordinal)
        result = (cached_results or {}).get(cache_key)
        if result is None:
            raise Stage0ExtractError(
                f"Preferred item {ordinal} missing from cascade cached_results "
                f"({item[:60]!r}) — cascade should have classified it via Groq/Gemini."
            )
        result = _cap_confirmed_presence(result, item, attested_skill_terms or {})
        if result.get("domain_soft"):
            handling = "soft gap -- transferable-skill bridge required"
        elif result["gap"]:
            handling = "not claimed -- not in ground truth"
        else:
            handling = "addressed -- see resume/cover letter"
        classified_preferred.append({
            "item": result["item"],
            "anchor": result["anchor"],
            "gap": result["gap"],
            "gap_class": result["gap_class"],
            "domain_soft": bool(result.get("domain_soft")),
            "handling": handling,
            "evidence_level": result.get("evidence_level"),
            "confidence": result.get("confidence"),
        })

    flagged_gaps: list[dict] = [
        {
            "item": r["item"],
            "gap_class": r["gap_class"],
            "anchor": r.get("anchor"),
            "gap_source": r.get("gap_source"),
        }
        for r in classified_required
        if r.get("gap")
    ]
    for p in classified_preferred:
        if p.get("domain_soft") and p.get("gap_class") == "SOFT":
            flagged_gaps.append({"item": p["item"], "gap_class": "SOFT"})
        elif p.get("gap_class") == "HARD":
            # A preferred-bucket item can still carry a confirmed HARD gap
            # (role-exclusion category only, post-CR-093 -- tools never gate
            # at all now, spec Sec. 9) -- an ATS keyword filter doesn't care
            # whether a JD labeled something "required" or "preferred" either.
            flagged_gaps.append({
                "item": p["item"], "gap_class": "HARD", "gap_source": p.get("gap_source"),
            })

    return classified_required, classified_preferred, flagged_gaps


# ---------------------------------------------------------------------------
# Responsibilities-bucket exclusion-zone screening (2026-08-21 follow-up to
# CR-096 Fix 1). classify_gaps() above only ever judges required/preferred
# items -- a JD's own role-framing prose in `responsibilities` (e.g. Harbor
# Compliance's "...to own the zero to one build of our Client Communications
# Service...") never reaches evidence_scale.classify_requirement() at all,
# so a real Exclusion Zone hit sitting in that prose is structurally
# invisible to Stage 0, confirmed live: Fix 1's prompt improvement alone did
# not flip Harbor Compliance's real Tier 2 verdict, because the disqualifying
# sentence was never a classified item in the first place.
#
# Running full LLM judgment on every responsibilities line (often 5-10+ per
# JD) to catch this would be a real, ongoing per-JD cost increase. Research
# on cost-effective LLM triage (routing an easy majority to a cheap filter,
# escalating only the rare ambiguous/hit case to the real classifier) is the
# standard mitigation -- applied here as a recall-oriented regex pre-filter
# that only escalates a line to the real evidence_scale judgment when it
# already looks like it might name one of the categories role_exclusion
# covers. A false positive here costs one extra cheap local-model call; a
# false negative is the exact pre-fix gap.
# Tier A: unambiguous enough to gate deterministically, no LLM judgment
# needed. Narrowly anchored to "own/lead/drive THE [zero-to-one/0-to-1]
# build" phrasing describing the role itself, matching the real Harbor
# Compliance wording exactly ("...to own the zero to one build of our
# Client Communications Service..."). Deliberately NOT resolved through
# evidence_scale.classify_requirement(): tested live and found that Jason's
# own real employer name "Zero To Sixty" (workExperience.md) collides
# lexically with "zero to one" often enough to confuse the local
# score model into reading it as a match instead of the
# disqualifier it actually is -- a coincidental collision a regex doesn't
# have, so the unambiguous subset is decided without one.
_DETERMINISTIC_0TO1_BUILD_RE = re.compile(
    r"(?:own|lead|drive|responsible\s+for)\w*\s+(?:the\s+|a\s+|this\s+)?"
    r"(?:zero.to.one|0.to.1)\s+(?:build|launch|creation)|"
    r"(?:zero.to.one|0.to.1)\s+(?:build|launch)\s+of|"
    # 2026-09-01 Improvement #5: common exclusion-zone phrasing that the
    # original regex missed. Each alternative is narrowly anchored to
    # unambiguous 0-to-1 / founding framing, not to any generic mention of
    # "first" or "build" — "first product manager" alone is NOT a match
    # (could be a legitimate non-founding role), but "founding PM" or
    # "first product manager to build from scratch" is.
    r"(?:founding|first)\s+(?:pm|product\s+manager)\b(?=.*(?:build|launch|scratch|ground|nothing|greenfield|zero))|"
    r"(?:build|create|launch)\s+(?:from\s+scratch|from\s+the\s+ground\s+up|from\s+nothing)\b|"
    r"\bgreenfield\s+(?:product|build|launch)\b|"
    r"(?:shaping|maturing)\s+an?\s+early.stage\s+product\s+area\b|"
    r"(?:where|when)\s+none\s+(?:previously\s+)?existed\b",
    re.I,
)

def screen_responsibilities_for_exclusion(
    responsibilities: list[str],
    work_exp: str,
    company: str = "",
    internal_terms: list[str] | None = None,
    *,
    settings: dict | None = None,
) -> list[dict]:
    """Responsibilities-bucket exclusion screen. Returns classify-shaped dicts
    (same shape _classify_one_item() returns for a HARD gap) for confirmed
    hits only, so a caller can extend classified_required with them and get
    correct disqualification through the existing compute_fit_score() path
    -- no separate tier-logic needed.

    2026-08-28 (Jason-supplied, after CR-096's "still not caught automatically"
    finding on Harbor Compliance): every responsibilities line now gets the
    real classifier's judgment, not just lines matching
    _RESPONSIBILITY_EXCLUSION_SIGNAL_RE first. That regex was a cost-saving
    pre-filter -- real, ongoing per-line LLM cost across every future job's
    full responsibilities bucket is the accepted tradeoff for not depending on
    a signal-word list ever staying complete against novel exclusion phrasing.
    The free deterministic 0-to-1 regex stays as a zero-cost fast path ahead
    of it; only lines it doesn't already resolve pay for a real judgment call.

    2026-09-01 Improvement #2: all non-deterministic responsibility lines
    are batched into a single classify_requirements_batch() call instead of
    one sequential classify_requirement() call per line. CR-108 Epic 7.7
    (2026-09-09): the legacy per-line sequential classifier was removed --
    a batch failure no longer falls back to it.

    Fails open per-line on a classification error: this is a bonus
    screening pass on top of the required/preferred judgments classify_gaps()
    already did, not a fail-closed gate -- one line's LLM error should never
    abort a Stage 0 run that would otherwise have completed correctly. A
    batch failure (both providers exhausted, validation error, etc.) is
    caught and this pass returns only whatever Phase 1 already found rather
    than raising -- unlike classify_gaps()'s cached_results miss, which is a
    real error, this bonus pass failing just means one extra check didn't run.
    """
    hits: list[dict] = []
    # Phase 1: deterministic 0-to-1 regex fast path (zero-cost, no LLM call).
    unclassified_lines: list[str] = []
    for line in responsibilities or []:
        if _DETERMINISTIC_0TO1_BUILD_RE.search(line):
            hits.append({
                "item": line,
                "anchor": "Deterministic: role framed as owning a zero-to-one/0-to-1 build (0-to-1 Exclusion Zone).",
                "gap": True,
                "gap_class": "HARD",
                "domain_soft": False,
                "gap_source": "role_exclusion",
            })
        else:
            unclassified_lines.append(line)

    if not unclassified_lines:
        return hits

    # Phase 2: batch all remaining lines through the evidence cascade.
    # CR-108 Epic 7.7 (2026-09-09): the legacy per-line sequential classifier
    # (the old Phase 3 fallback) was removed after the cascade passed its
    # release gate -- a batch failure no longer degrades to it. But this
    # function's own fail-open contract (see docstring) still holds: a batch
    # failure here means this bonus screening pass contributes nothing this
    # run, not that the whole Stage 0 run for this opportunity should abort.
    # Bug found on review (2026-09-09): an earlier version of this cutover
    # let a batch failure propagate uncaught -- worse, as whatever raw
    # exception type the cascade raises (CascadeValidationError, a transport
    # error, ...), not even the Stage0ExtractError the workflow runner knows
    # how to handle, so it also broke that error-type contract on the way out.
    from stage0_evidence_cascade import BatchItem, classify_requirements_batch
    from evidence_scale import build_evidence_context
    from stage0_checkpoint import make_item_key

    batch_items = [
        BatchItem(
            make_item_key("responsibility", line, ordinal),
            "required",  # bucket="required" so HARD gates are allowed
            line,
            evidence_excerpt=build_evidence_context(
                line, work_exp, k=4, max_chars=3000,
            ),
        )
        for ordinal, line in enumerate(unclassified_lines)
    ]
    try:
        batch_results = classify_requirements_batch(
            batch_items,
            settings=settings,
        )
    except Exception:
        return hits
    for batch_item in batch_items:
        result = batch_results.get(batch_item.item_id)
        if result and result.get("gate") == "HARD":
            hits.append(result)
    return hits


# ---------------------------------------------------------------------------
# Tier determination
# ---------------------------------------------------------------------------

def _determine_tier(
    prefs_result: dict,
    flagged_gaps: list[dict],
    db_action: str,
    *,
    thin_incomplete: bool = False,
    required_empty: bool = False,
) -> tuple[str, str]:
    """
    Return (tier, decision) based on gate results.

    tier: "Tier 1" | "Tier 2" | "Skip"
    decision: "PASS" | "SKIP"
    """
    # DB gate forces Skip
    if db_action == "reject":
        return "Skip", "SKIP"

    # Prefs gate hard reject forces Skip
    if not prefs_result.get("passed", True):
        return "Skip", "SKIP"

    # Thin career-page stubs with no extractable hire criteria (Netradyne-class,
    # 2026-08-10): Skip, never a clean Tier 1 / extraction_empty Tier 2 PASS.
    if thin_incomplete:
        return "Skip", "SKIP"

    # A credential-type HARD gap (unbridgeable degree, or a named regulated-
    # domain requirement with its own years threshold -- 2026-08-19) forces
    # Skip regardless of everything else -- a factual yes/no no score can
    # override. A tool-type HARD gap (2026-08-19, Jason-supplied) no longer
    # auto-Skips: a single missing tool on an otherwise strong JD is
    # bridgeable in a real conversation the way a missing degree or a named
    # domain requirement isn't, so it falls through to the SOFT-gap branch
    # below instead -- "not clean," not "reject outright." Real cases:
    # Bamboo Health skipped on "Tableau" alone, sight-unseen on everything
    # else (fixed by the tool exception); OneSource Virtual's "5+ years...
    # payroll tax" scored Tier 1 despite zero real evidence for it (fixed by
    # adding "domain" to this absolute-Skip set, same as "degree").
    if any(
        g.get("gap_class") == "HARD" and g.get("gap_source") in ("degree", "domain", "certification")
        for g in flagged_gaps
    ):
        return "Skip", "SKIP"

    # DB reapply flag, any SOFT gap, or a tool-only HARD gap → Tier 2 (fallback
    # read when no fit score is available -- see Step 5.5 in the caller, which
    # overrides this with the real score-driven tier whenever one exists).
    if (
        db_action == "reapply_flag"
        or any(g.get("gap_class") in ("SOFT", "HARD") for g in flagged_gaps)
    ):
        return "Tier 2", "PASS"

    # Preferred-only / no-required extract must not look like a clean Tier 1
    # (Beyond-class, 2026-08-10 monitor) — force Tier 2 so under-extraction is visible.
    if required_empty:
        return "Tier 2", "PASS"

    return "Tier 1", "PASS"


def _build_exclusion_zone_summary(prefs_result: dict) -> str:
    """Compose a human-readable exclusion zone summary line."""
    exclusion_codes = {
        "exclusion_zone_people_management",
        "exclusion_zone_zero_to_one",
        "exclusion_zone_revenue_billing",
        "exclusion_zone_ai_ml_ownership",
        "solo_pm_trap",
    }
    hits = [r for r in prefs_result.get("rejects", []) if r["code"] in exclusion_codes]
    if not hits:
        return "clear -- no Exclusion Zone patterns detected"
    parts = [r["reason"] for r in hits]
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Main builder (Story 2.5)
# ---------------------------------------------------------------------------

def build_stage0_fit_gate(
    folder_path: str | Path,
    db_gate_result: dict | None = None,
    prefs: dict | None = None,
    vocab: set[str] | None = None,
    *,
    ignore_skip_ledger: bool = False,
    skip_ledger_db: Path | str | None = None,
    confirmation_db_path: Path | str | None = None,
) -> dict:
    """
    Full Stage 0 fit-gate for the submission folder at *folder_path*.

    # Implements FR-252, FR-264

    Parameters
    ----------
    folder_path:
        Path to a submission folder containing Original_JD.txt.
    db_gate_result:
        Inject a pre-built DB gate result dict (used in tests to skip real DB).
        When None, calls evaluate_db_gate() from stage0_db_gate.py.
    prefs:
        Loaded candidate_preferences.json dict.  When None, loads from disk.
    vocab:
        Pre-built anchor vocabulary set.  When None, builds from disk files.
    ignore_skip_ledger:
        When True (--force), re-evaluate even if this posting is already skipped.
    skip_ledger_db:
        Optional sqlite path for the skip ledger (tests). Default is jobagent.sqlite.

    Returns
    -------
    dict matching the live stage0_fit_gate.json shape.
    """
    folder = Path(folder_path)
    jd_file = folder / "Original_JD.txt"

    if not jd_file.exists():
        raise FileNotFoundError(f"Original_JD.txt not found in {folder}")

    # 2026-09-01: clean up any stale spool files from a previous failed run
    # before starting a new Stage 0 evaluation.
    clean_spool(folder)

    raw_text = jd_file.read_text(encoding="utf-8", errors="replace")
    url, jd_text = _parse_url_and_jd(raw_text)
    # Found 2026-08-31 during the Stage 0-3 replay: a JD scraped by the now-removed
    # remotefirstjobs.com/JobsCollider connector saved raw, doubly HTML-entity-encoded markup
    # ("&lt;h3&gt;", "&amp;rsquo;" -- the &amp; itself needs unescaping before &rsquo; becomes
    # visible as its own entity -- "&#xA;" for newlines) instead of plain decoded text. Every
    # downstream check here works on real words -- undecoded entities and raw <h3>/<p>/<li> tags
    # both read as noise, so extraction found no real content (fit_score 0, couldn't even
    # resolve the company name) on a JD a human reads fine. Two independent, safe-on-clean-text
    # passes: unescape entities (looped, bounded, since double-encoding needs two passes -- a
    # no-op once text is already clean), then strip whatever tags that unescaping exposed
    # (utils.py's clean_jd_text() does the same tag-strip for the same reason elsewhere, but
    # isn't imported here to avoid pulling that module's heavier dependency surface into Stage
    # 0's core parse path for a two-line regex).
    for _ in range(3):
        unescaped = html.unescape(jd_text)
        if unescaped == jd_text:
            break
        jd_text = unescaped
    jd_text = re.sub(r"<[^>]+>", " ", jd_text)
    jd_text = re.sub(r"[ \t]{2,}", " ", jd_text)
    jd_text = _strip_ats_chrome(jd_text)

    # Company slug → display name
    company_slug = folder.name
    company_display = company_slug.replace("_", " ").replace("-", " ").title()

    # Role title: first substantive non-URL line of JD body
    from seniority_gate import extract_job_title_line
    role = extract_job_title_line(jd_text) or "Product Manager"

    # Load prefs
    if prefs is None:
        from utils import load_candidate_preferences
        prefs = load_candidate_preferences()

    # Load vocab
    if vocab is None:
        vocab = _load_anchor_vocab()

    # --- Step 0.4: skip ledger (CR-091) — URL then company+title, no folder crawl ---
    if not ignore_skip_ledger:
        from stage0_skip_ledger import lookup_skip
        prior = lookup_skip(
            url=url or None,
            company=company_display,
            title=role,
            db_path=skip_ledger_db,
        )
        if prior:
            prior_reason = prior.get("skip_reason") or "prior Stage 0 Skip"
            decided = prior.get("decided_at") or ""
            note = f"Skip ledger: previously skipped ({prior_reason})"
            if decided:
                note = f"{note} on {decided}"
            return {
                "company": company_display,
                "role": role,
                "url": url or None,
                "decision": "SKIP",
                "tier": "Skip",
                "reach_out": False,
                "skip_reason": note,
                "skip_reason_code": "skip_ledger",
                "stage_signal": _detect_stage_signal(jd_text),
                "thin_jd": _detect_thin_jd(jd_text, []),
                "required": [],
                "preferred": [],
                "responsibilities": [],
                "culture": [],
                "flagged_gaps": [],
                "exclusion_zone_check": "n/a (skipped at skip ledger)",
                "notes": note,
            }

    # --- Step 1: DB gate ---
    if db_gate_result is None:
        from stage0_db_gate import evaluate_db_gate
        # jd_text passed through (CR-092) so a job-board-mirror mismatch
        # between the CSV company and the JD's own self-identified employer
        # (e.g. "AdaMarie" carrying a Pinterest posting) gets checked under
        # both names, not just whatever the CSV happened to say.
        db_gate_result = evaluate_db_gate(company_display, role=role, db_path=_DEFAULT_DB, jd_text=jd_text)

    db_action = db_gate_result.get("action", "clear")

    # If DB says reject → write a Skip gate early, no further extraction needed
    if db_action == "reject":
        output = {
            "company": company_display,
            "role": role,
            "url": url or None,
            "decision": "SKIP",
            "tier": "Skip",
            "reach_out": False,
            "skip_reason": db_gate_result.get("reason", "DB gate reject"),
            "skip_reason_code": db_gate_result.get("reason_code", "db_reject"),
            "stage_signal": _detect_stage_signal(jd_text),
            "thin_jd": _detect_thin_jd(jd_text, []),
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "flagged_gaps": [],
            "exclusion_zone_check": "n/a (skipped at DB gate)",
            "notes": db_gate_result.get("reason", "DB gate reject"),
        }
        return output

    # --- Step 2: Prefs / exclusion gate ---
    prefs_result = run_prefs_gate_safe(company_display, jd_text, prefs)
    # Deterministic hard exclusions must short-circuit all model-dependent
    # work. A batch should still be able to classify obvious no-go roles when
    # the local extraction or evidence model is unavailable. This is not a
    # fit fallback: the preference gate has already made the factual decision.
    if not prefs_result.get("passed", True):
        first_reject = (prefs_result.get("rejects") or [{}])[0]
        reason = first_reject.get("reason") or "Stage 0 preference exclusion"
        code = first_reject.get("code") or "prefs_gate_reject"
        return {
            "company": company_display,
            "role": role,
            "url": url or None,
            "decision": "SKIP",
            "tier": "Skip",
            "reach_out": False,
            "skip_reason": reason,
            "skip_reason_code": code,
            "stage_signal": _detect_stage_signal(jd_text),
            "thin_jd": _detect_thin_jd(jd_text, []),
            "required": [],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
            "flagged_gaps": [],
            "exclusion_zone_check": _build_exclusion_zone_summary(prefs_result),
            "notes": reason,
            "extraction_source": "not_run",
        }

    # --- Step 3: Extract JD buckets ---
    # NLP extraction is the default (2026-08-30, CR-105, Jason-supplied): TF-IDF/LogReg
    # classifier with a Groq/Gemini fallback for low-confidence bullets only, replacing
    # the local-model-pinned "llm" path as the default. "llm" stays available (rollback /
    # comparison) via STAGE0_SECTION_MODE=llm. Regex is used only when STAGE0_SECTION_MODE
    # is explicitly deterministic (tests / offline). A load or run failure raises
    # Stage0ExtractError instead of silently swapping extractors.
    _release_stage0_vram("before-extract")
    import pipeline_env
    if pipeline_env.stage0_section_mode() == "llm":
        sections = _extract_sections_llm(jd_text)
        extraction_source = "llm"
    else:
        sections = _extract_sections_nlp(jd_text)
        extraction_source = "nlp"
    if sections is None:
        sections = _extract_sections(jd_text)
        extraction_source = "deterministic"
    for name in _empty_extraction_buckets():
        sections.setdefault(name, [])

    # --- Step 3.5: three-way qualification-risk gate (CR-112) ---
    # PIN 4: spliced in right after sections = ..., before
    # _count_qualification_required / _detect_thin_jd / _cap_requirement_bucket
    # read required_raw below. PIN 1: everything in this block runs before
    # run_key/request_hash/start_run exist (built further below) -- a pause
    # raised here is receipt-only: no stage0_runs row, no mark_run_status
    # call. Only the NLP extractor's own unresolved queue is in scope here
    # (_extract_sections_llm already fails closed with no fallback queue; the
    # deterministic regex path has no such concept) -- see the CR-112 design
    # doc's Scope section.
    requirement_extraction_review: dict = {"bypassed_non_qualification": []}
    unresolved_queue = list(sections.get("unresolved_for_review") or []) if extraction_source == "nlp" else []
    if unresolved_queue:
        from stage0_qualification_risk_gate import classify_qualification_risk, NON_QUALIFICATION
        from stage0_requirement_extraction_review import (
            RequirementExtractionReviewValidationError,
            consume_review_import,
            try_load_review_import,
            write_review_template,
        )

        gate_items: list[dict] = []
        for entry in unresolved_queue:
            item_text = entry.get("text", "")
            item_header = entry.get("header", "")
            label, reason_code = classify_qualification_risk(
                item_text, header=item_header, role_title=role
            )
            gate_items.append(
                {
                    "text": item_text,
                    "header": item_header,
                    "label": label,
                    "reason_code": reason_code,
                    "extraction_reason": entry.get("reason"),
                    "model_call_occurred": bool(entry.get("model_call_occurred", False)),
                }
            )
        needs_review = any(item["label"] != NON_QUALIFICATION for item in gate_items)

        if needs_review:
            _review_jd_hash = _sha256_text(jd_text)
            try:
                resolved_buckets = try_load_review_import(
                    folder,
                    gate_items,
                    submission_slug=folder.name,
                    jd_sha256=_review_jd_hash,
                )
            except RequirementExtractionReviewValidationError as exc:
                # Unreadable consumed review fails closed. Invalid live, or a
                # consumed file bound to a different JD/queue, re-pauses so a
                # new review can be answered. Print the reason so a Vanta-style
                # restart is not mistaken for a first-time pause.
                if getattr(exc, "fail_closed", False):
                    raise
                print(f"[Stage 0] requirement-extraction-review rejected: {exc}")
                resolved_buckets = None
            if resolved_buckets is None:
                write_review_template(
                    folder,
                    submission_slug=folder.name,
                    jd_sha256=_review_jd_hash,
                    queue=gate_items,
                )
                raise Stage0RequirementExtractionReviewNeeded(folder.name, gate_items)
            # A human (or a harness answering on a human's behalf) supplied an
            # explicit, exact-text-bound bucket for every queued item --
            # apply it. "exclude" means confirmed non-requirement content,
            # same disposition a NON_QUALIFICATION bypass gets automatically.
            consume_review_import(folder)
            for idx, item in enumerate(gate_items):
                bucket = resolved_buckets[idx]
                item["resolved_bucket"] = bucket
                if bucket == "exclude":
                    continue
                sections.setdefault(bucket, []).append(item["text"])

        requirement_extraction_review["bypassed_non_qualification"] = [
            item for item in gate_items if item["label"] == NON_QUALIFICATION
        ]
        requirement_extraction_review["queue"] = gate_items

    sections = _divert_scored_chrome(sections)
    required_raw = sections["required"]
    preferred_raw = sections["preferred"]
    responsibilities = sections["responsibilities"]
    culture = [
        line for line in sections.get("culture", [])
        if line and not _is_boilerplate_item(line)
    ]
    junk = [line for line in sections.get("junk", []) if line]
    # Only present when extraction_source == "llm" -- the regex fallback
    # path (_extract_sections) has no model reading the whole JD to notice
    # a company's own product/platform names, so it never populates this.
    internal_terms = sections.get("internal_terms") or []
    qual_required_n = _count_qualification_required(required_raw)

    thin_jd = _detect_thin_jd(jd_text, required_raw)
    stage_signal = _detect_stage_signal(jd_text)

    # Cap after thin-JD/qual-count detection (which must see the real,
    # uncapped extraction) and before classification (the expensive step
    # this cap exists to bound) -- see _cap_requirement_bucket() above.
    required_raw, required_dropped_n = _cap_requirement_bucket(required_raw)
    preferred_raw, preferred_dropped_n = _cap_requirement_bucket(preferred_raw)

    # Resolved once, up front, so every Review Center write in this function --
    # skill confirmations included -- honors the same override. Previously this
    # was computed after _prepare_skill_confirmations() already ran with the
    # raw (unresolved) confirmation_db_path param, so APPLYR_STAGE0_REVIEW_DB
    # silently never reached skill confirmations and they always landed in the
    # real production DB regardless of the override (found 2026-09-01, testing
    # archived opportunities against an isolated review DB: 12 skill-confirmation
    # rows landed in data/jobagent.sqlite instead of the intended test DB).
    checkpoint_db_path = confirmation_db_path or os.environ.get("APPLYR_STAGE0_REVIEW_DB")
    checkpoint_db_path = checkpoint_db_path or _DEFAULT_DB

    # Implements FR-283: pause only this opportunity for an unknown named tool.
    # Do this before any evidence-model calls so a pending answer is durable
    # even when the score model is unavailable.
    pending_confirmations, attested_skill_terms = _prepare_skill_confirmations(
        required_raw + preferred_raw,
        folder=folder,
        company=company_display,
        role=role,
        internal_terms=internal_terms,
        db_path=checkpoint_db_path,
    )
    # work_exp is the exact source text used to build the evidence context.
    # Its hash participates in the run key so a changed source invalidates reuse.
    from utils import load_file, WORK_EXP_FILE
    work_exp = load_file(WORK_EXP_FILE) or ""
    jd_hash = _sha256_text(jd_text)
    evidence_index_hash = _sha256_text(work_exp)
    prompt_version = "evidence-scale-v1"
    from utils import load_llm_settings
    stage0_settings: dict = load_llm_settings()
    # CR-108 Epic 7.2: model-flagged named tools (needs_user_confirmation +
    # canonical_skill from the batch response) accumulate here so the fit gate
    # can create the same durable pending items the deterministic extractor
    # path creates, after the provider call that flagged them.
    model_flagged_skills: list[dict[str, str]] = []
    provider_policy_hash = _sha256_text(
        json.dumps(
            (stage0_settings.get("stage0_evidence_classification") or {}),
            sort_keys=True,
            ensure_ascii=False,
        )
    )
    run_key = make_run_key(
        folder.name,
        jd_hash,
        prompt_version,
        provider_policy_hash,
        evidence_index_hash,
    )
    request_hash = _sha256_text(
        json.dumps(
            {
                "run_key": run_key,
                "required": required_raw,
                "preferred": preferred_raw,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )
    request_spool_path: str | None = None
    checkpoint_boundary("before_request_spool")
    request_spool_path, request_hash = write_spool(
        folder,
        "request",
        run_key,
        {
            "run_key": run_key,
            "required": required_raw,
            "preferred": preferred_raw,
        },
    )
    checkpoint_boundary("after_request_spool")
    start_run(
        checkpoint_db_path,
        run_key=run_key,
        opportunity_key=folder.name,
        jd_hash=jd_hash,
        prompt_version=prompt_version,
        provider_policy_hash=provider_policy_hash,
        evidence_index_hash=evidence_index_hash,
        request_hash=request_hash,
        request_spool_path=request_spool_path,
    )
    checkpoint_boundary("after_run_requested")
    mark_run_status(checkpoint_db_path, run_key, "RUNNING")
    if pending_confirmations:
        mark_run_status(checkpoint_db_path, run_key, "WAITING_FOR_INPUT")
        checkpoint_boundary("after_pending_confirmation_commit")
        raise Stage0NeedsInput(folder.name, pending_confirmations)

    # --- Step 4: Gap classification (CR-093 evidence-scale engine) ---
    # Extract and score now use the same model (qwen2.5:7b-instruct-q4_K_M).
    # No VRAM handoff needed -- the model stays loaded from extraction.
    # The unload/prepare path is retained for the case where FIT_MODEL
    # overrides the score model to something different.
    if extraction_source == "llm":
        from evidence_scale import _score_model
        actual_score_model = _score_model()
        if STAGE0_EXTRACT_MODEL != actual_score_model:
            _release_stage0_vram("before-score", required=True)
        _prepare_stage0_score_model()
    # work_exp loaded here (moved up from the old Step 5.5) -- every item's
    # LLM judgment needs real candidate ground truth, not just the tier-
    # deciding fit-score call that used to be the only consumer of this file.
    # WORK_EXP_SUMMARY_FILE is a meta-description of the document's own
    # structure, not real accomplishment content -- confirmed useless as
    # evidence context during CR-093 validation (silently under-scored a
    # real clean match). Full, untruncated text passed here --
    # evidence_scale.classify_requirement() retrieves the relevant excerpt
    # per requirement line internally (build_evidence_context(), CR-093
    # Epic 2 Story 2.1) rather than this caller blind-truncating up front;
    # a blind 8000-char prefix was confirmed live to miss real evidence
    # (Pendo/Amplitude, ~char 27800 of the real document).
    # The evidence index hash above is computed from the exact source text
    # supplied to the classifier.
    cached_results: dict[str, dict] = {}
    for bucket, items in (("required", required_raw), ("preferred", preferred_raw)):
        for ordinal, item in enumerate(items):
            item_key = make_item_key(bucket, item, ordinal)
            cached = get_completed_judgment(
                checkpoint_db_path,
                run_key=run_key,
                item_key=item_key,
                request_hash=request_hash,
                content_hash=_sha256_text(item),
                evidence_index_hash=evidence_index_hash,
            )
            if cached and isinstance(cached.get("judgment"), dict):
                cached_results[item_key] = cached["judgment"]

    def _persist_judgment(bucket: str, ordinal: int, item: str, judgment: dict) -> None:
        """Persist a newly computed Stage 0 item judgment for safe resume."""
        item_key = make_item_key(bucket, item, ordinal)
        complete_judgment(
            checkpoint_db_path,
            judgment_key=f"{run_key}:{item_key}",
            run_key=run_key,
            opportunity_key=folder.name,
            item_key=item_key,
            item_text=item,
            bucket=bucket,
            request_hash=request_hash,
            content_hash=_sha256_text(item),
            evidence_index_hash=evidence_index_hash,
            judgment=judgment,
            provider="local",
            model="evidence_scale",
        )
        checkpoint_boundary("after_judgment_commit")

    import pipeline_env
    cascade_import_meta: dict | None = None
    uncached_items = [
        (bucket, ordinal, item)
        for bucket, items in (("required", required_raw), ("preferred", preferred_raw))
        for ordinal, item in enumerate(items)
        if make_item_key(bucket, item, ordinal) not in cached_results
    ]
    if uncached_items:
        from stage0_evidence_cascade import (
            BatchItem,
            CascadeReviewNeeded,
            CascadeValidationError,
            CASCADE_IMPORT_NAME,
            CASCADE_IMPORT_TEMPLATE_NAME,
            classify_requirements_batch,
            try_load_cascade_import,
            write_cascade_import_template,
        )
        from evidence_scale import build_evidence_context
        from cost_eligibility import (
            CostPauseError,
            budget_ledger_from_settings,
            overlay_persisted_budget,
        )
        from stage0_checkpoint import get_run_metadata

        batch_items = [
            BatchItem(
                make_item_key(bucket, item, ordinal),
                bucket,
                item,
                # 2026-09-01: reduced from 6000 to 3000 to stay under Groq's
                # 8000 TPM free-tier limit. With 9 items (a large JD), 6000 chars
                # per item produced ~13500 tokens — well over the limit. At 3000
                # chars per item, 9 items produce ~6750 tokens, safely under 8000.
                evidence_excerpt=build_evidence_context(
                    item,
                    work_exp,
                    k=4,
                    max_chars=3000,
                ),
            )
            for bucket, ordinal, item in uncached_items
        ]
        cascade_telemetry = {
            "stage0_cascade_batches": 1,
            "stage0_cascade_provider_calls": 0,
            "stage0_cascade_fallbacks": 0,
            "stage0_cascade_items": len(batch_items),
        }

        def _record_provider_event(provider: str, event: str) -> None:
            """Record provider names and aggregate cascade events without payload text."""
            del provider
            if event == "call":
                cascade_telemetry["stage0_cascade_provider_calls"] += 1
            elif event == "fallback":
                cascade_telemetry["stage0_cascade_fallbacks"] += 1

        try:
            checkpoint_boundary("before_provider_call")

            def _spool_response(raw_response: str) -> None:
                """Persist the provider response before validation or judgment writes."""
                response_path, response_hash = write_spool(
                    folder,
                    "response",
                    run_key,
                    {"raw_response": raw_response},
                )
                mark_run_status(
                    checkpoint_db_path,
                    run_key,
                    "RUNNING",
                    response_spool_path=response_path,
                    response_hash=response_hash,
                )
                checkpoint_boundary("after_response_spool")

            ledger = budget_ledger_from_settings(stage0_settings)
            overlay_persisted_budget(ledger, get_run_metadata(checkpoint_db_path, run_key))

            def _persist_ledger(current) -> None:
                update_run_metadata(
                    checkpoint_db_path,
                    run_key,
                    {
                        "paid_remaining_cents": current.remaining_cents,
                        "paid_batch_remaining_cents": current.batch_remaining_cents,
                    },
                )

            ledger.persist = _persist_ledger

            def _pause_for_cost(exc: BaseException) -> Stage0CostAuthorizationNeeded:
                write_cascade_import_template(
                    folder,
                    submission_slug=folder.name,
                    jd_sha256=jd_hash,
                    items=batch_items,
                )
                mark_run_status(checkpoint_db_path, run_key, "WAITING_FOR_INPUT")
                pause = (
                    stage0_cost_pause_from_error(exc)
                    if isinstance(exc, CostPauseError)
                    else Stage0CostAuthorizationNeeded(
                        reason=getattr(exc, "args", ("invalid_cascade_import",))[0]
                        if not isinstance(exc, Stage0CostAuthorizationNeeded)
                        else exc.reason,
                        authorization_mode="manual_paste",
                        model_call_occurred=False,
                        next_paths=["import_cascade_json"],
                    )
                )
                if isinstance(exc, Stage0CostAuthorizationNeeded):
                    pause = exc
                pause.next_paths = [
                    f"write {CASCADE_IMPORT_NAME} in this folder (template: {CASCADE_IMPORT_TEMPLATE_NAME})",
                    "certify_zero_charge",
                    "paid_allowlist_budget",
                ]
                return pause

            imported = try_load_cascade_import(
                folder,
                batch_items,
                submission_slug=folder.name,
                jd_sha256=jd_hash,
            )
            if imported is not None:
                batch_results = imported["results"]
                cascade_import_meta = {
                    "used": True,
                    "import_source": "manual",
                    "import_sha256": imported["import_sha256"],
                    "schema_version": imported["schema_version"],
                    "validation": imported["validation"],
                    "model_call_occurred": False,
                    "cost_applicable": False,
                }
            else:
                batch_results = classify_requirements_batch(
                    batch_items,
                    settings=stage0_settings,
                    raw_response_callback=_spool_response,
                    provider_event_callback=_record_provider_event,
                    folder=folder,
                    cost_ledger=ledger,
                    allow_import=False,
                )
            cascade_telemetry["paid_remaining_cents"] = ledger.remaining_cents
            if ledger.batch_remaining_cents is not None:
                cascade_telemetry["paid_batch_remaining_cents"] = ledger.batch_remaining_cents
        except CostPauseError as exc:
            clean_spool(folder)
            raise _pause_for_cost(exc) from exc
        except CascadeReviewNeeded as exc:
            clean_spool(folder)
            raise _pause_for_cost(
                Stage0CostAuthorizationNeeded(
                    reason=f"subscription_review:{exc}",
                    authorization_mode="manual_paste",
                    model_call_occurred=True,
                )
            ) from exc
        except CascadeValidationError as exc:
            import_path = folder / CASCADE_IMPORT_NAME
            if import_path.is_file():
                clean_spool(folder)
                raise _pause_for_cost(
                    Stage0CostAuthorizationNeeded(
                        reason="invalid_cascade_import",
                        authorization_mode="manual_paste",
                        model_call_occurred=False,
                    )
                ) from exc
            mark_run_status(checkpoint_db_path, run_key, "FAILED")
            clean_spool(folder)
            raise Stage0ExtractError(
                f"Stage 0 evidence cascade could not produce a valid batch: {exc}"
            ) from exc
        except UnicodeDecodeError as exc:
            import_path = folder / CASCADE_IMPORT_NAME
            if import_path.is_file():
                clean_spool(folder)
                raise _pause_for_cost(
                    Stage0CostAuthorizationNeeded(
                        reason="invalid_cascade_import",
                        authorization_mode="manual_paste",
                        model_call_occurred=False,
                    )
                ) from exc
            mark_run_status(checkpoint_db_path, run_key, "FAILED")
            clean_spool(folder)
            raise Stage0ExtractError(
                f"Stage 0 evidence cascade could not produce a valid batch: {exc}"
            ) from exc
        except Stage0CostAuthorizationNeeded:
            raise
        except Exception as exc:
            mark_run_status(checkpoint_db_path, run_key, "FAILED")
            clean_spool(folder)
            raise Stage0ExtractError(
                f"Stage 0 evidence cascade could not produce a valid batch: {exc}"
            ) from exc
        finally:
            update_run_metadata(checkpoint_db_path, run_key, cascade_telemetry)
        for batch_item in batch_items:
            result = batch_results[batch_item.item_id]
            _persist_judgment(
                batch_item.bucket,
                int(batch_item.item_id.split(":", 2)[1]),
                batch_item.requirement,
                result,
            )
            cached_results[batch_item.item_id] = result
            if (
                result.get("needs_user_confirmation")
                and result.get("skill_kind") == "tool"
                and result.get("canonical_skill")
            ):
                model_flagged_skills.append(
                    {
                        "skill_key": str(result["canonical_skill"]),
                        "requirement": batch_item.requirement,
                    }
                )

    classified_required, classified_preferred, flagged_gaps = classify_gaps(
        required_raw, preferred_raw, work_exp=work_exp, company=company_display,
        internal_terms=internal_terms, attested_skill_terms=attested_skill_terms,
        cached_results=cached_results, judgment_callback=_persist_judgment,
    )

    # 2026-08-21 follow-up to Fix 1: the JD's own role-framing prose lives in
    # `responsibilities`, which classify_gaps() never sees. Cheap pre-filter,
    # real classifier only on a hit -- see screen_responsibilities_for_exclusion().
    resp_exclusion_hits = screen_responsibilities_for_exclusion(
        responsibilities, work_exp, company=company_display, internal_terms=internal_terms,
        settings=stage0_settings,
    )
    if resp_exclusion_hits:
        classified_required.extend(resp_exclusion_hits)
        flagged_gaps.extend(
            {
                "item": h["item"],
                "gap_class": h["gap_class"],
                "anchor": h.get("anchor"),
                "gap_source": h.get("gap_source"),
            }
            for h in resp_exclusion_hits
        )

    # CR-108 Epic 7.7 (2026-09-09): the cascade is now the only classification
    # path — the legacy per-line local classifier was removed after the cascade
    # passed its release gate (7.3/7.4/7.5). Model-proposed HARD decisions are
    # always reviewable, and model-flagged named tools always create durable
    # pending items.
    pending_hard_reviews = _prepare_hard_gate_reviews(
        classified_required,
        classified_preferred,
        flagged_gaps,
        folder=folder,
        company=company_display,
        role=role,
        db_path=checkpoint_db_path,
    )
    # CR-108 Epic 7.2: model-flagged named tools create the same durable
    # pending item the deterministic extractor path creates -- reuse the
    # skill-memory rules so an already-decided skill is never re-asked.
    pending_skill_reviews: list[dict[str, str]] = []
    for flagged in model_flagged_skills:
        skill_key = canonical_skill_key(flagged["skill_key"])
        if not model_flagged_named_skill(flagged["skill_key"], flagged["requirement"]):
            continue  # Implements CR-114: generic traits are not named-tool cards.
        if get_skill_memory(skill_key, checkpoint_db_path):
            continue
        display_name = " ".join(
            word.capitalize() for word in skill_key.split("_")
        )
        create_skill_confirmation(
            db_path=checkpoint_db_path,
            skill_key=skill_key,
            display_name=display_name,
            requirement=flagged["requirement"],
            opportunity_key=folder.name,
            opportunity_company=company_display,
            opportunity_title=role,
            evidence_excerpt=(
                "The Stage 0 model identified this named tool in the job "
                "description, but it is not in verified work history."
            ),
            decision_basis=(
                "A Stage 0 evidence model flagged this as a named tool present in "
                "the job description. It is not in verified work history."
            ),
            uncertainty="model_flagged_named_tool",
        )
        pending_skill_reviews.append(
            {
                "review_key": f"skill:{skill_key}",
                "skill_key": skill_key,
                "display_name": display_name,
                "requirement": flagged["requirement"],
            }
        )
    all_pending = pending_hard_reviews + pending_skill_reviews
    if all_pending:
        mark_run_status(checkpoint_db_path, run_key, "WAITING_FOR_INPUT")
        raise Stage0NeedsInput(folder.name, all_pending)

    # Empty buckets on a non-thin JD → fail closed to Tier 2 (never fake clean Tier 1)
    word_count = len(re.findall(r"\w+", jd_text or ""))
    extraction_empty = (
        not required_raw
        and not preferred_raw
        and not responsibilities
        and word_count >= 80
    )
    # Thin stub with nothing extractable (career-page / demo CTA, not a real JD)
    thin_incomplete = bool(
        thin_jd
        and not required_raw
        and not preferred_raw
        and not responsibilities
    )
    if thin_incomplete:
        flagged_gaps.append({
            "item": "Stage 0: thin JD stub with no extractable requirements/responsibilities",
            "gap_class": "HARD",
            "bridge": "thin_incomplete — posting is not a real JD; Skip rather than draft",
        })
    elif extraction_empty:
        flagged_gaps.append({
            "item": "Stage 0 extraction returned empty buckets on a non-thin JD",
            "gap_class": "SOFT",
            "bridge": "extraction_empty — re-check JD section headers before drafting",
        })
    elif qual_required_n == 0 and (preferred_raw or responsibilities):
        # Preferred-only (or duties-only) extract — surface so Tier 1 can't fake clean.
        # Culture sentences stuffed into required do not count as required items.
        flagged_gaps.append({
            "item": "Stage 0: no required items extracted (preferred/responsibilities only)",
            "gap_class": "SOFT",
            "bridge": "required_empty — confirm quals headers before treating as clean pass",
        })
    elif qual_required_n <= 1 and word_count >= 200:
        # Non-empty but suspiciously thin: a JD this long should rarely
        # produce 0-1 qualification-shaped required items. This is a tripwire, not a fix — the
        # 2026-08-17 header/item-boundary bugs above cover the specific real
        # cases found so far (PracticeTek: 1 of 5 real required items
        # captured), but this stays in place against whatever real-world JD
        # phrasing shows up next that neither of those anticipated. Surfacing
        # it turns a silent wrong answer into a visible one that a human
        # re-checks against the raw JD text before trusting Tier 1/2.
        flagged_gaps.append({
            "item": (
                f"Stage 0: only {qual_required_n} qualification-shaped required "
                f"item(s) extracted from a {word_count}-word JD — verify against "
                "the raw JD text before trusting this as a complete list"
            ),
            "gap_class": "SOFT",
            "bridge": "required_thin — re-check JD required-section extraction manually before drafting",
        })

    po_signal = _detect_po_solo_backlog_signal(role, jd_text, prefs)
    if po_signal:
        flagged_gaps.append(po_signal)

    # --- Step 5: Determine tier ---
    tier, decision = _determine_tier(
        prefs_result,
        flagged_gaps,
        db_action,
        thin_incomplete=thin_incomplete,
        required_empty=qual_required_n == 0,
    )

    # --- Step 5.5: Weighted evidence-scale score decides the final tier
    # (CR-093, replacing structured_fit.evaluate_structured_fit()'s separate
    # 5-criterion holistic call). Moved up from after notes-building so the
    # score can finalize tier/decision BEFORE skip_reason/notes get built
    # from them. Only reached when Step 5 didn't already force Skip (DB
    # reject, prefs reject, thin stub) -- those stay absolute, no score
    # undoes them. A credential/domain/role-exclusion HARD gate now shows up
    # as compute_fit_score()'s own `disqualified` result (it scans
    # classified_required directly), so it's naturally covered by the same
    # code path rather than a separate pre-check -- no fallback branch here:
    # classify_gaps() already ran the LLM judgment for every item at Step 4,
    # so this is pure arithmetic over results already in hand, nothing that
    # can itself fail independently of Step 4.
    from evidence_scale import compute_fit_score, load_score_bands

    score_result = compute_fit_score(classified_required, classified_preferred)
    fit_score: int = score_result["fit_score"]
    confidence_score: int = score_result["confidence_score"]

    # Tier/Skip floor reads from data/fit_rubric_calibration.json (CR-093
    # Epic 4), NOT candidate_preferences.json -- this branch previously
    # hardcoded 80/70 literally, then briefly lived in candidate_preferences
    # .json before Jason correctly flagged that a scoring-engine calibration
    # constant isn't a personal job-search preference and belongs somewhere
    # else. See load_score_bands()'s docstring for the full reasoning.
    skip_floor, tier1_floor = load_score_bands()

    if score_result["disqualified"]:
        tier = "Skip"
        decision = "SKIP"
    elif decision == "PASS":
        if fit_score >= tier1_floor:
            tier = "Tier 1"
        elif fit_score >= skip_floor:
            tier = "Tier 2"
        else:
            tier = "Skip"
            decision = "SKIP"
        # Score must not wash out an empty-required extract (Beyond-class,
        # 2026-08-10). Step 5 already forced Tier 2 for required_empty;
        # Step 5.5 then overwrote it whenever preferred items scored >= 65
        # (confirmed live 2026-08-20: a Jira/Confluence preferred-only
        # fixture landed Tier 1). Empty required stays visible as Tier 2.
        if qual_required_n == 0 and decision == "PASS" and tier == "Tier 1":
            tier = "Tier 2"

    # --- Step 6: Build skip_reason if needed ---
    skip_reason: str | None = None
    skip_reason_code: str | None = None
    if tier == "Skip":
        if thin_incomplete:
            skip_reason = "Thin JD stub with no extractable hire criteria"
            skip_reason_code = "thin_incomplete"
        elif not prefs_result.get("passed"):
            first_reject = prefs_result["rejects"][0]
            skip_reason = first_reject["reason"]
            skip_reason_code = first_reject["code"]
        elif score_result["disqualified"]:
            # CR-093: compute_fit_score() already found the disqualifying
            # HARD-gate item (degree/domain/role_exclusion -- tool can no
            # longer produce gate=="HARD" at all, spec Sec. 9) -- cite it
            # directly instead of re-deriving from flagged_gaps, so the
            # message can never drift from what actually disqualified this
            # JD (2026-08-19 bug this replaces: a tool gap that merely
            # co-existed alongside a real score-driven Skip used to produce
            # a misleading "Hard gap(s)" message on Bamboo Health).
            skip_reason = f"Hard gap: {score_result['disqualifying_item']}"
            skip_reason_code = "hard_gap"
        elif fit_score < skip_floor:
            skip_reason = f"Fit score {fit_score} is below the {skip_floor} floor"
            skip_reason_code = "fit_score_below_floor"

    # --- Build output ---
    exclusion_check = _build_exclusion_zone_summary(prefs_result)

    notes_parts: list[str] = []
    if db_action == "reapply_flag":
        # Use the DB gate's own reason text rather than a hardcoded phrase --
        # "reapply_eligible" really means cooldowns expired, but
        # "different_role_at_company" means cooldown was never evaluated
        # (the prior row's title didn't match this role), and the old fixed
        # string "all cooldowns expired" was false for that second case.
        db_reason_code = db_gate_result.get("reason_code", "") if db_gate_result else ""
        if db_reason_code == "different_role_at_company":
            notes_parts.append(f"Reapply flag from DB ({db_gate_result.get('reason', 'different role on file at this company')}).")
        else:
            notes_parts.append("Reapply flag from DB (prior rejections, all cooldowns expired).")
    if tier == "Tier 1":
        notes_parts.append("Clean Tier 1 pass. No flagged gaps.")
    elif tier == "Tier 2":
        if extraction_empty:
            notes_parts.append(
                "Tier 2: extraction_empty — non-thin JD produced empty required/preferred/responsibilities."
            )
        soft_items = [g["item"][:60] for g in flagged_gaps if g.get("gap_class") == "SOFT"]
        if soft_items and not extraction_empty:
            notes_parts.append(f"Tier 2: soft gap(s) — {'; '.join(soft_items[:2])}.")
        elif soft_items and extraction_empty:
            # already noted extraction_empty; still surface other soft gaps briefly
            other = [g["item"][:60] for g in flagged_gaps if g.get("gap_class") == "SOFT"
                     and "empty buckets" not in g.get("item", "")]
            if other:
                notes_parts.append(f"Also soft gap(s) — {'; '.join(other[:2])}.")
    elif tier == "Skip":
        if skip_reason:
            notes_parts.append(f"Skip: {skip_reason}.")

    # Zero-anchor required items are not auto-escalated to HARD here --
    # "zero anchor" only means the crude tag/keyword matcher in this module
    # found nothing; Stage 1's honest-bridge search is semantic/creative and
    # genuinely does find real bridges for many zero-anchor items (several
    # of the 6 real drafts this session started zero-anchor at Stage 0).
    # Auto-Skipping on this signal alone would wrongly kill bridgeable
    # Tier 2s. What this DOES fix (2026-08-18, confirmed real on Oddball):
    # a zero-anchor required item currently surfaces identically to a
    # partial-anchor one in the batch table's "soft gap(s)" note, so the
    # highest-risk case looks no different from a routine one until Stage 1
    # burns a full packet-build discovering there was never a bridge.
    # Surface it distinctly instead, so a reviewer can sanity-check it before
    # spending that effort, without blocking the cases that DO bridge.
    zero_anchor_required = [
        g["item"] for g in flagged_gaps
        if g.get("gap_class") == "SOFT" and g.get("anchor") == "none"
    ]
    if tier == "Tier 2" and zero_anchor_required:
        preview = "; ".join(item[:70] for item in zero_anchor_required[:2])
        notes_parts.append(
            f"HIGH SKIP RISK -- {len(zero_anchor_required)} required item(s) "
            f"with zero anchor anywhere (no tag/tool match at all, not even "
            f"partial): {preview}. Verify a real bridge exists in "
            "workExperience.md before drafting -- do not assume Tier 2 means "
            "a bridge will be found."
        )

    # fit_score was already computed in Step 5.5 above, and already decided
    # tier/decision -- nothing left to do here but include it in the output.

    output: dict = {
        "company": company_display,
        "role": role,
        "url": url or None,
        "decision": decision,
        "tier": tier,
        "reach_out": False,
        "fit_score": fit_score,
        "confidence_score": confidence_score,
        "stage_signal": stage_signal,
        "thin_jd": thin_jd,
        "extraction_source": extraction_source,
        "salary_range": extract_salary_range(jd_text),
        "requirements_capped": {
            "limit": MAX_REQUIREMENT_ITEMS_PER_BUCKET,
            "required_dropped": required_dropped_n,
            "preferred_dropped": preferred_dropped_n,
        },
        "required": classified_required,
        "preferred": classified_preferred,
        "responsibilities": responsibilities[:8],
        "culture": culture[:4],
        "junk": junk[:20],
        "flagged_gaps": flagged_gaps,
        "zero_anchor_required_items": zero_anchor_required,
        "exclusion_zone_check": exclusion_check,
        "prefs_gate_rejects": [r["code"] for r in prefs_result.get("rejects", [])],
        "prefs_gate_flags": [f["code"] for f in prefs_result.get("flags", [])],
        "notes": " ".join(notes_parts) or tier,
        # CR-112 test 10: NON_QUALIFICATION bypasses from the three-way gate
        # are always visible here with their reason code, never silent, even
        # when nothing paused (every item bypassed).
        "requirement_extraction_review": requirement_extraction_review,
    }

    if skip_reason:
        output["skip_reason"] = skip_reason
        output["skip_reason_code"] = skip_reason_code

    # Reapply flag annotation
    if db_action == "reapply_flag":
        output["db_reapply_flag"] = True
        output["db_reapply_note"] = db_gate_result.get("reason", "")

    # CR-092 (2026-08-15): surface a CSV-vs-JD-self-identified company name
    # mismatch in the batch table, not just buried in the raw DB-gate JSON --
    # visible even when neither name has DB history, since "this posting is
    # a job-board mirror" is worth knowing regardless of dedup outcome.
    company_mismatch = db_gate_result.get("company_mismatch")
    if company_mismatch:
        output["company_mismatch"] = company_mismatch

    # CR-092 follow-up (2026-08-15, Jason-supplied): an already-in-progress
    # (non-terminal) application at this company/role is a real duplicate
    # signal -- flagged for a human look (Tier 2), never an automatic Skip,
    # since an active row could be a stale/abandoned entry as easily as a
    # genuine live application (same "Kroll-style... belongs in Tier 2, not
    # its own category" reasoning generate-submission/SKILL.md already
    # applies to same-title active-row duplicates).
    active_application = db_gate_result.get("active_application")
    if active_application and output.get("decision") != "SKIP":
        output["active_application"] = active_application
        flag_note = f"DB shows an active (non-terminal) application already on file: {active_application[0].get('status')} -- verify this isn't a duplicate before sending."
        output["notes"] = (output.get("notes") or "") + " " + flag_note

    if cascade_import_meta:
        output["cascade_import"] = cascade_import_meta

    mark_run_status(checkpoint_db_path, run_key, "COMPLETE")
    checkpoint_boundary("after_run_complete")

    # Free VRAM once Stage 0 is done. Targeted /api/ps unload, not a sweep
    # of every installed tag. In a batch, the next role's before-extract
    # boundary performs the required purge before loading Qwen, so purging
    # here would create a redundant unload/reload cycle between roles.
    # STAGE0_BATCH_KEEP_ALIVE is an explicit batch-only optimization; the
    # default remains the original single-role safety behavior.
    if os.environ.get("STAGE0_BATCH_KEEP_ALIVE", "").strip().lower() not in {
        "1", "true", "yes", "on"
    }:
        _release_stage0_vram("after-stage0")

    return output


def _release_stage0_vram(reason: str, *, required: bool = False) -> None:
    """Unload resident local models before the next Stage 0 LLM step.

    Extract and score both use Qwen 7B (2026-08-22), so the before-score
    unload is skipped when the models match. The unload is still needed
    before-extract (clear any prior batch's models) and after-stage0
    (free VRAM for Stage 1). When FIT_MODEL overrides the score model to
    a different tag, the before-score unload fires as before.
    """
    import pipeline_env
    if pipeline_env.stage0_section_mode() == "deterministic":
        return
    try:
        from evidence_scale import STAGE0_SCORE_MODEL
        from model_manager import (
            _tag_matches,
            list_resident_models,
            unload_resident_models,
        )
        print(
            f"    [Stage 0] Unloading local models ({reason}) so the next "
            "step has free VRAM.",
            file=sys.stderr,
        )
        unload_resident_models(also=(STAGE0_EXTRACT_MODEL, STAGE0_SCORE_MODEL))
        if required:
            still = list_resident_models()
            if any(_tag_matches(STAGE0_EXTRACT_MODEL, name) for name in still):
                raise Stage0ExtractError(
                    f"Could not unload {STAGE0_EXTRACT_MODEL} before scoring "
                    f"({reason}). Refusing to load {STAGE0_SCORE_MODEL} while "
                    "Qwen may still be in VRAM."
                )
    except Stage0ExtractError:
        raise
    except Exception as exc:
        message = (
            f"Could not unload local models before the next Stage 0 step "
            f"({reason}): {exc}."
        )
        if required:
            raise Stage0ExtractError(message) from exc
        print(f"    [Stage 0] {message}", file=sys.stderr)


def _prepare_stage0_score_model() -> None:
    """Confirm the score model is installed and ready."""
    import pipeline_env
    if pipeline_env.stage0_section_mode() == "deterministic":
        return
    from evidence_scale import STAGE0_SCORE_MODEL, _ensure_score_model_ready, _score_model
    model = _score_model()
    print(
        f"    [Stage 0] Score model {model} (default {STAGE0_SCORE_MODEL}).",
        file=sys.stderr,
    )
    _ensure_score_model_ready(model)


def run_prefs_gate_safe(company: str, jd_text: str, prefs: dict) -> dict:
    """Fail-loud wrapper: runs the prefs gate and surfaces errors visibly.

    Previously this caught ALL exceptions and returned ``passed: True``
    silently, which meant every deterministic gate (industry, title, years,
    exclusion zones, solo PM) was skipped with no trace in the output.
    Found 2026-09-03: this was not the direct cause of the gate escapes
    (the gates ran without exceptions but had logic bugs), but it is the
    highest-risk pattern for future drift — if any import inside
    ``run_prefs_gate`` fails, all gates silently pass.

    Now: logs the error to stderr and includes it in the result flags, but
    still passes (fail-open with compensating controls) because the
    evidence-scale fit scoring still runs and can catch bad fits. The error
    is also stored in the stage0 output via ``prefs_gate_error`` so it is
    visible in the JSON artifact, not just stderr.
    """
    try:
        from stage0_prefs_gate import run_prefs_gate
        return run_prefs_gate(company, jd_text, prefs)
    except Exception as exc:
        print(f"WARNING: prefs gate failed to run: {exc}", file=sys.stderr)
        return {
            "passed": True,
            "rejects": [],
            "flags": [{"code": "prefs_gate_error", "note": str(exc)}],
            "_gate_failed": True,
        }


# ---------------------------------------------------------------------------
# CLI (Story 2.5)
# ---------------------------------------------------------------------------

def _one_line(result: dict, folder: Path) -> str:
    """Format the Tier one-liner for a single Stage 0 result."""
    tier = result.get("tier", "?")
    company = result.get("company", folder.name)
    skip_reason = result.get("skip_reason", "")
    notes = result.get("notes", "")
    gap_count = len(result.get("flagged_gaps", []))
    if skip_reason:
        line = f"{tier} — {company}: {skip_reason}"
    elif gap_count:
        line = f"{tier} — {company}: {gap_count} gap(s) — {notes}"
    else:
        line = f"{tier} — {company}: {notes}"
    return line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
        sys.stdout.encoding or "utf-8", errors="replace"
    )


def _has_extraction_override(out_path: Path) -> bool:
    """True when an existing stage0_fit_gate.json was hand-corrected and flagged
    extraction_override: true — a fresh re-run must not silently clobber it.

    Found 2026-08-08: build_stage0_fit_gate.py had zero awareness of this flag
    (set by the hand-reconstruct workaround agreed in session-005 R10 when the
    extractor demonstrably mis-parses a JD), so a bare re-run would overwrite a
    verified-correct gate with a fresh, possibly still-buggy one. See R14.
    """
    if not out_path.exists():
        return False
    try:
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return existing.get("extraction_override") is True


def _resolve_folder(raw: str) -> Path:
    """Resolve a slug or path to a submission-like folder with Original_JD.txt."""
    p = Path(raw)
    if p.is_dir() and (p / "Original_JD.txt").exists():
        return p
    for base in (_REPO_ROOT / "data" / "submissions", _REPO_ROOT / "data" / "pending_review"):
        cand = base / raw
        if cand.is_dir() and (cand / "Original_JD.txt").exists():
            return cand
    return p


def _has_stage0_receipt(folder: Path) -> bool:
    """True once run_submission.py has minted a real Stage 0 receipt for this folder.

    Found 2026-08-30/31 during the Stage 0-3 replay: this CLI's own write path has zero
    awareness of stage_receipts/ — writing stage0_fit_gate.json here silently orphaned the
    receipt chain on 7 already-COMPLETE submissions (the file changed under receipts that
    still recorded its old hash, and stage1's prior_receipt_id kept pointing at the old
    stage0 receipt). warn_worker_cli only prints a note; nothing actually stopped the write.
    This makes that a hard refusal instead, since a stderr note evidently wasn't enough.
    """
    return (folder / "stage_receipts" / "stage0.json").exists()


def batch_report(folders: list[Path], write: bool = True, force: bool = False, bypass_receipt_guard: bool = False) -> str:
    """Story 2.6 — run Stage 0 on many folders; return Markdown Tier 1/2/Skip table.

    # Implements FR-252 (batch triage without a cloud agent), FR-264 (placement)
    """
    from stage0_placement import apply_stage0_placement

    buckets: dict[str, list[str]] = {"Tier 1": [], "Tier 2": [], "Skip": []}
    for folder in folders:
        try:
            result = build_stage0_fit_gate(folder, ignore_skip_ledger=force)
        except FileNotFoundError as e:
            buckets["Skip"].append(f"| {folder.name} | ERROR: {e} |")
            continue
        except Stage0ExtractError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            raise
        out_path = folder / "stage0_fit_gate.json"
        protected = (not force) and _has_extraction_override(out_path)
        has_receipt = (not bypass_receipt_guard) and _has_stage0_receipt(folder)
        if write and not protected and not has_receipt:
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            apply_stage0_placement(folder, result)
        tier = result.get("tier", "Skip")
        if tier not in buckets:
            tier = "Skip"
        reason = result.get("skip_reason") or result.get("notes") or ""
        # Avoid Windows cp1252 crashes on arrows/dashes in reason strings
        reason = reason.replace("\u2192", "->").replace("\u2014", "-").replace("\u2013", "-")
        if protected:
            reason = f"{reason} [NOT WRITTEN -- extraction_override protected, use --force]"
        elif has_receipt:
            reason = (
                f"{reason} [NOT WRITTEN -- stage_receipts/stage0.json already exists; this "
                "folder is owned by run_submission.py. Use that (--resume/--force), or pass "
                "--bypass-receipt-guard if you really mean to write here directly.]"
            )
        company = result.get("company", folder.name)
        buckets[tier].append(f"| {company} | {reason} |")

    parts: list[str] = []
    for header in ("Tier 1", "Tier 2", "Skip"):
        parts.append(f"### {header}")
        parts.append("")
        parts.append("| Company | Reason |")
        parts.append("|---|---|")
        if buckets[header]:
            parts.extend(buckets[header])
        else:
            parts.append("| - | none |")
        parts.append("")
    text = "\n".join(parts)
    enc = sys.stdout.encoding or "utf-8"
    return text.encode(enc, errors="replace").decode(enc, errors="replace")


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Build stage0_fit_gate.json for a submission folder (no LLM)."
    )
    parser.add_argument(
        "folder",
        nargs="*",
        help="Path(s) or slug(s) to folders containing Original_JD.txt",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Print results without writing stage0_fit_gate.json",
    )
    parser.add_argument(
        "--batch-table",
        action="store_true",
        help="Print a Markdown Tier 1 / Tier 2 / Skip table for all folders (Story 2.6)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing stage0_fit_gate.json even if it's hand-corrected "
        "(extraction_override: true). Without this flag such a file is never touched.",
    )
    parser.add_argument(
        "--bypass-receipt-guard",
        action="store_true",
        help="Write stage0_fit_gate.json even when stage_receipts/stage0.json already exists "
        "for this folder. Doing so orphans the receipt chain (run_submission.py will report "
        "check_workflow_complete: NO afterward) -- only pass this if you're about to --resume "
        "that folder right after to re-mint the chain.",
    )
    args = parser.parse_args()

    if not args.folder:
        parser.error("at least one folder or slug is required")

    folders = [_resolve_folder(f) for f in args.folder]
    write = not args.no_write

    if args.batch_table or len(folders) > 1:
        print(batch_report(folders, write=write, force=args.force, bypass_receipt_guard=args.bypass_receipt_guard))
        sys.exit(0)

    folder = folders[0]
    if not folder.is_dir():
        print(f"ERROR: '{folder}' is not a directory.", file=sys.stderr)
        sys.exit(0)

    try:
        result = build_stage0_fit_gate(folder, ignore_skip_ledger=args.force)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(0)
    except Stage0ExtractError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = folder / "stage0_fit_gate.json"
    protected = (not args.force) and _has_extraction_override(out_path)
    has_receipt = (not args.bypass_receipt_guard) and _has_stage0_receipt(folder)
    if write and not protected and not has_receipt:
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        from stage0_placement import apply_stage0_placement
        folder = apply_stage0_placement(folder, result)
    elif protected:
        print(
            f"NOTE: '{out_path}' has extraction_override: true — not overwritten. "
            "Pass --force to override.",
            file=sys.stderr,
        )
    elif has_receipt:
        print(
            f"REFUSED: '{out_path}' already has a Stage 0 receipt "
            f"(stage_receipts/stage0.json) -- this folder is owned by run_submission.py. "
            "Use `python scripts/run_submission.py <folder> --resume` (or --force) instead, "
            "or pass --bypass-receipt-guard if you really mean to write here directly.",
            file=sys.stderr,
        )

    print(_one_line(result, folder))
    sys.exit(0)


if __name__ == "__main__":
    from workflow.entry_warning import warn_worker_cli
    warn_worker_cli("build_stage0_fit_gate.py")
    _main()
