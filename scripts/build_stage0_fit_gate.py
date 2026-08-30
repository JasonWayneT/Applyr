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
import json
import os
import re
import sys
from pathlib import Path

# Measured 2026-08-17 on the real PracticeTek JD: this tag beat llama3.1:8b
# and every 14B local model on responsibilities completeness. Do not swap
# it for Settings.localModel or a VRAM fallback.
STAGE0_EXTRACT_MODEL = "qwen2.5:7b-instruct-q4_K_M"


class Stage0ExtractError(RuntimeError):
    """Requirement extraction cannot proceed. Do not substitute another path."""

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
        r"nice\s+to\s+have|bonus\s+(?:points?|if|qualifications?)|"
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
    r"opportunity\s+to\s+work\s+remotely"
    r")"
)

# A line that, once trimmed, is nothing but a bare URL is never real hire criteria —
# belt-and-suspenders for apply-link lines regardless of the lead-in phrasing above.
_BARE_URL_ITEM_RE = re.compile(r"^https?://\S+$", re.I)


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


def _extract_sections(jd_text: str) -> dict[str, list[str]]:
    """
    Extract text buckets by section heading.

    Returns dict with keys: required, preferred, responsibilities, culture.
    Each value is a list of bullet-like strings extracted from that section.

    Trailing ATS boilerplate (relocation / EEO / salary / #LI-…) is excluded:
    matching ignore headers ends the current quals bucket, and any remaining
    boilerplate strings are stripped via `_is_boilerplate_item`.
    """
    buckets: dict[str, list[str]] = {
        "required": [],
        "preferred": [],
        "responsibilities": [],
        "culture": [],
    }

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

        # Extract meaningful bullet items (20–300 chars, starts with letter or digit)
        clean = line.lstrip("-•*◦▪▸→").strip()
        if 15 <= len(clean) <= 300 and (clean[0].isalnum() or clean[0] in '"\''):
            if _is_list_leadin(clean):
                continue
            if not _is_boilerplate_item(clean):
                target_bucket = current_bucket
                if current_bucket == "required" and _INLINE_PREFERRED_RE.search(clean):
                    target_bucket = "preferred"
                buckets[target_bucket].append(clean)

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
    """
    text = (item or "").strip()
    if _SPECIFICITY_GENERIC_SOFT_SKILL_RE.match(text):
        return -2.0
    score = 2.0 if _SPECIFICITY_NUMBER_RE.search(text) else 0.0
    words = text.split()
    if len(words) < 4:
        score -= 1.0
    score += min(len(words), 30) * 0.01
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



def _extract_sections_nlp(jd_text: str) -> dict[str, list[str]]:
    import joblib
    import csv
    from utils import call_llm, extract_json_from_text
    
    model_path = _REPO_ROOT / "data" / "stage0_classifier.pkl"
    if not model_path.exists():
        print("NLP Model not found, falling back to deterministic extraction.", file=sys.stderr)
        return _extract_sections(jd_text)
        
    pipeline = joblib.load(model_path)
    classes = list(pipeline.classes_)
    
    lines = _normalize_jd_punctuation(jd_text).splitlines()
    
    buckets = {
        "required": [],
        "preferred": [],
        "responsibilities": [],
        "culture": [],
    }
    
    current_header = ""
    fallback_queue = []
    
    for line in lines:
        clean = line.strip()
        if not clean:
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
        if 15 <= len(bullet_clean) <= 300 and (bullet_clean[0].isalnum() or bullet_clean[0] in '"\'\''):
            if _is_list_leadin(bullet_clean):
                continue
            if not _is_boilerplate_item(bullet_clean):
                combo_text = f"[HEADER] {current_header}: {bullet_clean}" if current_header else bullet_clean
                
                if current_header == "required" and _INLINE_PREFERRED_RE.search(bullet_clean):
                    buckets["preferred"].append(bullet_clean)
                    continue
                    
                pred = pipeline.predict([combo_text])[0]
                proba = pipeline.predict_proba([combo_text])[0]
                conf = proba[classes.index(pred)]
                
                if conf < 0.65:
                    fallback_queue.append((combo_text, bullet_clean, current_header))
                else:
                    buckets[pred].append(bullet_clean)
                    
    # Active Learning Fallback Loop
    if fallback_queue:
        print(f"    [NLP] Sending {len(fallback_queue)} ambiguous lines to LLM fallback...", file=sys.stderr)
        prompt = "Classify these job description bullet points into one of four buckets: 'required', 'preferred', 'responsibilities', or 'culture'. Return ONLY valid JSON as a mapping from the index to the bucket string.\n\n"
        for i, (combo_text, _, _) in enumerate(fallback_queue):
            prompt += f"[{i}] {combo_text}\n"
            
        result = call_llm(
            system_prompt="You are an expert NLP data labeler. Output only JSON format: { \"0\": \"required\", \"1\": \"preferred\" }",
            user_prompt=prompt,
            provider_override="gemini"
        )
        
        if result:
            json_str = extract_json_from_text(result)
            try:
                import json
                mapping = json.loads(json_str)
                feedback_csv = _REPO_ROOT / "data" / "training_data_feedback.csv"
                write_header = not feedback_csv.exists()
                
                with open(feedback_csv, "a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["text", "label", "company", "source_file"])
                    if write_header:
                        writer.writeheader()
                        
                    for i_str, bucket in mapping.items():
                        idx = int(i_str)
                        if bucket not in buckets:
                            continue
                        combo_text, bullet_clean, _ = fallback_queue[idx]
                        buckets[bucket].append(bullet_clean)
                        
                        writer.writerow({
                            "text": bullet_clean,
                            "label": bucket,
                            "company": "FeedbackLoop",
                            "source_file": "fallback_api"
                        })
            except Exception as e:
                print(f"    [NLP Error] Failed to parse LLM fallback: {e}", file=sys.stderr)
                # default to responsibilities
                for _, bullet_clean, _ in fallback_queue:
                    buckets["responsibilities"].append(bullet_clean)
        else:
            for _, bullet_clean, _ in fallback_queue:
                buckets["responsibilities"].append(bullet_clean)
    
    _recover_mixed_responsibilities(buckets)
    return buckets

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
    for item in buckets["responsibilities"]:
        if _INLINE_PREFERRED_RE.search(item):
            buckets["preferred"].append(item)
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


_STAGE_SIGNALS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bseries\s+[abcde]\b", re.I), "VC-backed (Series found)"),
    (re.compile(r"\bseed\s+(?:stage|funded|round)\b", re.I), "seed-stage startup"),
    (re.compile(r"\bpre.ipo\b", re.I), "pre-IPO"),
    (re.compile(r"\b(?:ipo|publicly\s+traded|nasdaq|nyse)\b", re.I), "public company"),
    (re.compile(r"\b(?:fortune\s+\d{3}|enterprise\s+saas|global\s+enterprise)\b", re.I), "enterprise/large company"),
    (re.compile(r"\b(?:startup|early.stage|growth.stage)\b", re.I), "startup / growth-stage"),
    (re.compile(r"\b(?:private\s+equity|pe.backed)\b", re.I), "PE-backed"),
]


def _detect_stage_signal(jd_text: str) -> str:
    """Return a human-readable stage signal or the standard unknown string."""
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


def _is_administratively_satisfied(item_lower: str) -> bool:
    """True for items that should never be treated as real gaps needing a
    claim bridge -- consumed by build_authoring_packet.py, not by Stage 0
    classification (CR-093 moved that reasoning into evidence_scale.py's
    prompt instead). Deliberately narrow and conservative:
    citizenship/work-authorization/security-clearance/travel/supervisory-
    responsibility statements are NOT covered here (left for a separate,
    more careful pass -- some are legally sensitive and shouldn't be
    silently resolved without confirming Jason's actual status)."""
    if _YEARS_EXPERIENCE_LEADIN_RE.match(item_lower.strip()):
        return True
    if _BACHELORS_SATISFIED_RE.search(item_lower) and not _HIGHER_DEGREE_MANDATORY_RE.search(item_lower):
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


def classify_gaps(
    required_items: list[str],
    preferred_items: list[str],
    work_exp: str = "",
    vocab: set[str] | None = None,
    company: str = "",
    internal_terms: list[str] | None = None,
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
    """
    del vocab  # deprecated, unused — see docstring

    classified_required: list[dict] = []
    for item in required_items:
        classified_required.append(
            _classify_one_item(item, work_exp, company=company, internal_terms=internal_terms)
        )

    classified_preferred: list[dict] = []
    for item in preferred_items:
        result = _classify_one_item(
            item, work_exp, is_required=False, company=company, internal_terms=internal_terms
        )
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
    r"(?:zero.to.one|0.to.1)\s+(?:build|launch)\s+of",
    re.I,
)

def screen_responsibilities_for_exclusion(
    responsibilities: list[str],
    work_exp: str,
    company: str = "",
    internal_terms: list[str] | None = None,
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

    Fails open per-line on a classification error: this is a bonus
    screening pass on top of the required/preferred judgments classify_gaps()
    already did, not a fail-closed gate -- one line's LLM error should never
    abort a Stage 0 run that would otherwise have completed correctly.
    """
    from evidence_scale import classify_requirement, EvidenceClassificationError

    hits: list[dict] = []
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
            continue
        try:
            judgment = classify_requirement(
                line, work_exp, is_required=True, company=company, internal_terms=internal_terms,
            )
        except EvidenceClassificationError:
            continue
        if judgment.gate == "HARD":
            hits.append(judgment.to_legacy_dict())
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

    raw_text = jd_file.read_text(encoding="utf-8", errors="replace")
    url, jd_text = _parse_url_and_jd(raw_text)
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
    # LLM extraction is the default (2026-08-17, Jason-supplied), pinned to
    # STAGE0_EXTRACT_MODEL. Regex is used only when STAGE0_SECTION_MODE is
    # explicitly deterministic (tests / offline). A load or run failure
    # raises Stage0ExtractError instead of silently swapping extractors.
    _release_stage0_vram("before-extract")
    sections = _extract_sections_llm(jd_text)
    extraction_source = "llm"
    if sections is None:
        sections = _extract_sections(jd_text)
        extraction_source = "deterministic"
    required_raw = sections["required"]
    preferred_raw = sections["preferred"]
    responsibilities = sections["responsibilities"]
    culture = sections["culture"]
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
    from utils import load_file, WORK_EXP_FILE
    work_exp = load_file(WORK_EXP_FILE) or ""
    classified_required, classified_preferred, flagged_gaps = classify_gaps(
        required_raw, preferred_raw, work_exp=work_exp, company=company_display,
        internal_terms=internal_terms,
    )

    # 2026-08-21 follow-up to Fix 1: the JD's own role-framing prose lives in
    # `responsibilities`, which classify_gaps() never sees. Cheap pre-filter,
    # real classifier only on a hit -- see screen_responsibilities_for_exclusion().
    resp_exclusion_hits = screen_responsibilities_for_exclusion(
        responsibilities, work_exp, company=company_display, internal_terms=internal_terms,
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
        "flagged_gaps": flagged_gaps,
        "zero_anchor_required_items": zero_anchor_required,
        "exclusion_zone_check": exclusion_check,
        "notes": " ".join(notes_parts) or tier,
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
    """Thin wrapper that catches import errors during tests."""
    try:
        from stage0_prefs_gate import run_prefs_gate
        return run_prefs_gate(company, jd_text, prefs)
    except Exception as exc:
        return {
            "passed": True,
            "rejects": [],
            "flags": [{"code": "prefs_gate_error", "note": str(exc)}],
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


def batch_report(folders: list[Path], write: bool = True, force: bool = False) -> str:
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
        if write and not protected:
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
    args = parser.parse_args()

    if not args.folder:
        parser.error("at least one folder or slug is required")

    folders = [_resolve_folder(f) for f in args.folder]
    write = not args.no_write

    if args.batch_table or len(folders) > 1:
        print(batch_report(folders, write=write, force=args.force))
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
    if write and not protected:
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        from stage0_placement import apply_stage0_placement
        folder = apply_stage0_placement(folder, result)
    elif protected:
        print(
            f"NOTE: '{out_path}' has extraction_override: true — not overwritten. "
            "Pass --force to override.",
            file=sys.stderr,
        )

    print(_one_line(result, folder))
    sys.exit(0)


if __name__ == "__main__":
    from workflow.entry_warning import warn_worker_cli
    warn_worker_cli("build_stage0_fit_gate.py")
    _main()
