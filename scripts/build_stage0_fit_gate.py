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

No LLM / no Ollama required.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

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
                    vocab.add(term)
                    # Split "Technical Literacy: HTML/CSS/JavaScript" at delimiters
                    for word in re.findall(r"[a-z]{3,}", term):
                        vocab.add(word)
        except Exception:
            pass

    return vocab


# ---------------------------------------------------------------------------
# Hard-blocked tool list (Story 2.4)
# ---------------------------------------------------------------------------

# Tools that Jason definitively does not have experience with.
# Drawn from AGENTS.md hard anti-hallucination rules and common industry tools.
# NOT a comprehensive list — add to it; err on SOFT when uncertain.
_HARD_BLOCKED_TOOLS: frozenset[str] = frozenset({
    # Healthcare data standards
    "fhir", "hl7", "epic", "cerner", "meditech", "athenahealth",
    "redox", "mirth", "smartonfhir", "dicom",
    # Data warehouse / analytics infrastructure
    "snowflake", "databricks", "dbt", "fivetran", "airbyte",
    "tableau", "looker", "power bi", "powerbi", "qlik", "sisense",
    # Infrastructure / cloud infra
    "docker", "kubernetes", "k8s", "terraform", "helm",
    "ansible", "puppet", "chef",
    # Cloud platforms (PM roles that require cloud certification / ownership)
    # Note: general cloud-aware is NOT a gap; only direct ownership
    # ML / AI frameworks (engineering, not tooling)
    "tensorflow", "pytorch", "keras", "scikit-learn", "huggingface",
    "mlflow", "kubeflow", "sagemaker",
    # Specific tools from blocked list
    "mixpanel",         # analytics (Pendo is in catalog; mixpanel is not)
    "braze",            # marketing automation
    "zendesk", "freshdesk",  # support tooling (not in resume)
    "intercom",         # support/chat
    # Finance/payments/billing tools
    "stripe", "braintree", "adyen", "recurly", "chargebee",
    "netsuite", "workday", "sap",
    # Legal/contract
    "ironclad", "docusign",
    # Domain-specific
    "coupa",            # procurement
    "veeva",            # pharma CRM
})

# Regex pattern to detect hard-blocked tool names in a requirement string.
# Compiled lazily.
_HARD_TOOL_RE: re.Pattern | None = None


def _get_hard_tool_pattern() -> re.Pattern:
    global _HARD_TOOL_RE
    if _HARD_TOOL_RE is None:
        escaped = sorted(_HARD_BLOCKED_TOOLS, key=len, reverse=True)
        pattern = r"\b(?:" + "|".join(re.escape(t) for t in escaped) + r")\b"
        _HARD_TOOL_RE = re.compile(pattern, re.I)
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
        r"what\s+you(?:'|')ll?\s+(?:need|bring|have)|"
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
        r"what\s+sets\s+you\s+apart|"
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
        r"key\s+capabilities?(?:\s+for\s+success)?)\b",
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
        r"what'?s?\s+in\s+this\s+for\s+you|"
        r"what\s+is\s+in\s+it\s+for\s+you|"
        r"our\s+commitment\s+to\s+you|"
        r"ready\s+to\s+make\s+an?\s+impact|"
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
    r"success\s+metrics|"
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
    r"what\s+is\s+in\s+it\s+for\s+you"
    r")"
    r"\s*:?\s*$",
    re.I,
)

_TRACKING_TAG_RE = re.compile(r"^#li-[\w-]*\s*$", re.I)

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
    r"^passionate\s+about\s+making\s+a\s+difference"
    r")"
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
    # Header-only leftovers that snuck into the item list.
    if _IGNORE_SECTION_HEADERS.match(clean):
        return True
    # CR-086: orphan section labels captured as items (e.g. bare "Job Responsibilities"
    # when header routing missed — belt-and-suspenders with expanded header patterns).
    if _is_orphan_header_item(clean):
        return True
    return False


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
        for bucket_name, header_re in _SECTION_HEADERS:
            if header_re.match(line):
                matched_bucket = bucket_name
                break

        if matched_bucket is not None:
            current_bucket = matched_bucket
            continue

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


def _detect_thin_jd(jd_text: str, required_items: list) -> bool:
    """True when the JD is sparse (very short AND/OR almost no structured requirements).

    A JD with ≥2 extracted required items is never thin regardless of raw word count.
    Otherwise:
    - under 80 words → thin (original threshold)
    - zero extractable requireds and under 150 words → thin (2026-08-08 Cluster C item 10:
      clear_capital-class headerless prose at ~99 words was missing the old cutoff and
      produced a false clean Stage 0 shape)
    """
    if len(required_items) >= 2:
        return False
    word_count = len(re.findall(r"\w+", jd_text or ""))
    if word_count < 80:
        return True
    if len(required_items) == 0 and word_count < 150:
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
# Gap classification (Story 2.4)
# ---------------------------------------------------------------------------

# Generic terms that should never count as an "anchor" for a hard-skill requirement.
# Without this guard, broad tags like "compliance" could mask a gap for e.g. "HIPAA/HL7".
_GENERIC_TAG_WORDS: frozenset[str] = frozenset({
    "experience", "management", "work", "ability", "skills",
    "knowledge", "understanding", "background", "team", "product",
    "cross", "functional", "strong", "proven", "excellent",
    "ability", "deliver", "drive", "build", "lead", "grow",
})

# Domain/industry qualifiers that must themselves be anchored. A capability tag
# match (e.g. "compliance") does NOT clear a soft gap when the item also names
# an unanchored domain (e.g. "banking") — Round 4 hard/soft split.
_DOMAIN_QUALIFIER_RE = re.compile(
    r"\b("
    r"banking|bank|insurance|healthcare|health\s*care|fintech|"
    r"pharma(?:ceutical)?s?|clinical|mortgage|lending|"
    r"wealth\s+management|payments?|crypto(?:currency)?|"
    r"biotech|medtech|telehealth"
    r")\b",
    re.I,
)


def _unanchored_domain_qualifiers(
    item_lower: str, vocab: set[str], anchors: list[str]
) -> list[str]:
    """Return domain tokens in the item that have no vocab/anchor hit."""
    found: list[str] = []
    for match in _DOMAIN_QUALIFIER_RE.finditer(item_lower):
        compact = re.sub(r"\s+", " ", match.group(0).lower()).strip()
        anchored = any(
            compact in a.lower() or a.lower() in compact for a in anchors
        ) or any(
            compact == v or compact in v or v in compact
            for v in vocab
            if len(v) >= 4
        )
        if not anchored and compact not in found:
            found.append(compact)
    return found


# CR-090: items that will never anchor against a claim tag (no skill/tool vocabulary
# to match) but also aren't real transferable-skill gaps -- they're binary eligibility
# facts already resolved elsewhere or genuinely satisfied by Jason's real profile.
# Measured 2026-08-10 across 54 real submissions: 106 SOFT gaps total, with years-of-
# experience and Bachelor's-degree lines the two largest clean-cut categories (~20+
# combined). Falling through to the generic "no anchor -> soft gap needing a bridge"
# path for these produces an unbridgeable gap (nothing in master_claims.json is a
# claim about "having a bachelor's degree"), which then hard-blocks the packet via
# the fail-closed gate -- even though these aren't real gaps at all.
#
# Years-of-experience: already independently parsed and gated by
# seniority_gate.check_years_gate() against candidate_preferences.json's real
# threshold. Flagging the same line again here as an unbridgeable soft gap is not
# just redundant, it's actively wrong -- either it duplicates a signal that already
# exists correctly elsewhere, or it conflicts with it.
_YEARS_EXPERIENCE_LEADIN_RE = re.compile(
    r"^(?:minimum\s+(?:of\s+)?|approximately\s+)?"
    r"\d{1,2}\s*[-–+]?\s*(?:to\s+|-\s*)?\d{0,2}\+?\s*years?\b",
    re.I,
)

# Bachelor's-degree requirements: Jason has one (workExperience.md Section 7).
# Deliberately does NOT exempt lines that mandate a higher degree as required
# (Master's/MBA/PhD/JD/MD "required") -- those remain real gaps. A mention of a
# higher degree as merely *preferred* alongside a Bachelor's requirement is not a
# gap (the Bachelor's already satisfies the line).
_BACHELORS_SATISFIED_RE = re.compile(
    r"\b(?:bachelor(?:'s|s)?\s+degree|undergraduate\s+degree)\b",
    re.I,
)
_HIGHER_DEGREE_MANDATORY_RE = re.compile(
    r"\b(?:master'?s?|mba|ph\.?d\.?|j\.?d\.?|m\.?d\.?)\s+degree\s+required\b|"
    r"\brequires?\s+an?\s+(?:master'?s?|mba|ph\.?d\.?)\b",
    re.I,
)

# Soft familiarity hedges on hard-blocked tools → Tier 2 SOFT, not Skip.
# Intensifiers (deep/strong/hands-on) keep HARD so "Deep familiarity with Snowflake"
# still Skips. Plain "Familiarity with Docker/K8s" stays draftable as soft.
_SOFT_FAMILIARITY_HEDGE_RE = re.compile(
    r"\b(?:familiarity\s+with|familiar\s+with|exposure\s+to|awareness\s+of|"
    r"working\s+knowledge\s+of|basic\s+(?:understanding|knowledge)\s+of)\b",
    re.I,
)
_FAMILIARITY_INTENSIFIER_RE = re.compile(
    r"\b(?:deep|strong|extensive|expert|hands-?on)\b",
    re.I,
)


def _is_soft_familiarity_hedge(item_lower: str) -> bool:
    if not _SOFT_FAMILIARITY_HEDGE_RE.search(item_lower):
        return False
    if _FAMILIARITY_INTENSIFIER_RE.search(item_lower):
        return False
    return True


def _is_administratively_satisfied(item_lower: str) -> bool:
    """True for items that should never enter the generic soft-gap-needs-a-claim-
    bridge path -- see module comment above for why. Deliberately narrow and
    conservative: citizenship/work-authorization/security-clearance/travel/
    supervisory-responsibility statements are NOT covered here (left for a
    separate, more careful pass -- some are legally sensitive and shouldn't be
    silently resolved without confirming Jason's actual status)."""
    if _YEARS_EXPERIENCE_LEADIN_RE.match(item_lower.strip()):
        return True
    if _BACHELORS_SATISFIED_RE.search(item_lower) and not _HIGHER_DEGREE_MANDATORY_RE.search(item_lower):
        return True
    return False


def _item_has_anchor(item_lower: str, vocab: set[str]) -> list[str]:
    """
    Return list of matched anchor terms for *item_lower*.
    Empty list means no anchor found.
    """
    matched: list[str] = []
    for term in vocab:
        if len(term) < 4:
            continue
        if term in _GENERIC_TAG_WORDS:
            continue
        # Word-boundary match: term must appear as a complete word sequence
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, item_lower, re.I):
            matched.append(term)
    return matched


def _classify_one_item(
    item: str,
    vocab: set[str],
) -> dict:
    """
    Classify a single required/preferred item string.

    Returns::
        {
            "item": str,
            "anchor": str,    # matched tag names or "none"
            "gap": bool,
            "gap_class": "HARD" | "SOFT" | None,
            "domain_soft": bool,
        }
    """
    item_lower = item.lower()

    # Check for hard-blocked tools first. Plain familiarity/exposure hedges stay
    # SOFT (Tier 2) so an unconfirmed tool mention does not Skip the JD; intensified
    # phrasing (deep/strong/hands-on) still HARD-Skips.
    hard_match = _get_hard_tool_pattern().search(item_lower)
    if hard_match:
        if _is_soft_familiarity_hedge(item_lower):
            return {
                "item": item,
                "anchor": "none",
                "gap": True,
                "gap_class": "SOFT",
                "domain_soft": False,
            }
        return {
            "item": item,
            "anchor": "none",
            "gap": True,
            "gap_class": "HARD",
            "domain_soft": False,
        }

    anchors = _item_has_anchor(item_lower, vocab)
    unanchored_domains = _unanchored_domain_qualifiers(item_lower, vocab, anchors)

    # Domain qualifier with no domain anchor → SOFT even if capability tags matched
    if unanchored_domains:
        display = ", ".join(sorted(set(anchors))[:3]) if anchors else "none"
        anchor_str = (
            f"tags: {display}; domain soft-gap: {', '.join(unanchored_domains)}"
            if anchors
            else f"none; domain soft-gap: {', '.join(unanchored_domains)}"
        )
        return {
            "item": item,
            "anchor": anchor_str,
            "gap": True,
            "gap_class": "SOFT",
            "domain_soft": True,
        }

    if anchors:
        display = ", ".join(sorted(set(anchors))[:3])
        return {
            "item": item,
            "anchor": f"tags: {display}",
            "gap": False,
            "gap_class": None,
            "domain_soft": False,
        }

    # CR-090: eligibility facts that are already resolved elsewhere (years-of-
    # experience) or genuinely satisfied (Bachelor's degree) -- never claim-
    # bridgeable, so don't route them into the soft-gap-needs-a-bridge path.
    if _is_administratively_satisfied(item_lower):
        return {
            "item": item,
            "anchor": "satisfied: administrative (years-of-experience / education)",
            "gap": False,
            "gap_class": None,
            "domain_soft": False,
        }

    # No hard tool, no anchor → soft gap (domain/methodology bridgeable)
    return {
        "item": item,
        "anchor": "none",
        "gap": True,
        "gap_class": "SOFT",
        "domain_soft": False,
    }


def classify_gaps(
    required_items: list[str],
    preferred_items: list[str],
    vocab: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Classify required and preferred items for gaps.

    Returns (classified_required, classified_preferred, flagged_gaps).
    flagged_gaps contains required items where gap=True (HARD or SOFT), plus
    preferred items marked domain_soft (Round 4 domain-qualifier soft gaps).
    """
    if vocab is None:
        vocab = _load_anchor_vocab()

    classified_required: list[dict] = []
    for item in required_items:
        classified_required.append(_classify_one_item(item, vocab))

    classified_preferred: list[dict] = []
    for item in preferred_items:
        result = _classify_one_item(item, vocab)
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
        })

    flagged_gaps: list[dict] = [
        {"item": r["item"], "gap_class": r["gap_class"]}
        for r in classified_required
        if r.get("gap")
    ]
    for p in classified_preferred:
        if p.get("domain_soft") and p.get("gap_class") == "SOFT":
            flagged_gaps.append({"item": p["item"], "gap_class": "SOFT"})

    return classified_required, classified_preferred, flagged_gaps


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

    # Any HARD gap forces Skip
    if any(g.get("gap_class") == "HARD" for g in flagged_gaps):
        return "Skip", "SKIP"

    # DB reapply flag or any SOFT gap → Tier 2
    if db_action == "reapply_flag" or any(g.get("gap_class") == "SOFT" for g in flagged_gaps):
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
) -> dict:
    """
    Full Stage 0 fit-gate for the submission folder at *folder_path*.

    # Implements FR-252

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

    # --- Step 1: DB gate ---
    if db_gate_result is None:
        from stage0_db_gate import evaluate_db_gate
        db_gate_result = evaluate_db_gate(company_display, role=role, db_path=_DEFAULT_DB)

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

    # --- Step 3: Extract JD buckets ---
    sections = _extract_sections(jd_text)
    required_raw = sections["required"]
    preferred_raw = sections["preferred"]
    responsibilities = sections["responsibilities"]
    culture = sections["culture"]

    thin_jd = _detect_thin_jd(jd_text, required_raw)
    stage_signal = _detect_stage_signal(jd_text)

    # --- Step 4: Gap classification ---
    classified_required, classified_preferred, flagged_gaps = classify_gaps(
        required_raw, preferred_raw, vocab=vocab
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
    elif not required_raw and (preferred_raw or responsibilities):
        # Preferred-only (or duties-only) extract — surface so Tier 1 can't fake clean
        flagged_gaps.append({
            "item": "Stage 0: no required items extracted (preferred/responsibilities only)",
            "gap_class": "SOFT",
            "bridge": "required_empty — confirm quals headers before treating as clean pass",
        })

    # --- Step 5: Determine tier ---
    tier, decision = _determine_tier(
        prefs_result,
        flagged_gaps,
        db_action,
        thin_incomplete=thin_incomplete,
        required_empty=not required_raw,
    )

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
        elif any(g.get("gap_class") == "HARD" for g in flagged_gaps):
            hard_gaps = [g["item"] for g in flagged_gaps if g.get("gap_class") == "HARD"]
            skip_reason = f"Hard gap(s): {'; '.join(hard_gaps[:3])}"
            skip_reason_code = "hard_gap"

    # --- Build output ---
    exclusion_check = _build_exclusion_zone_summary(prefs_result)

    notes_parts: list[str] = []
    if db_action == "reapply_flag":
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

    output: dict = {
        "company": company_display,
        "role": role,
        "url": url or None,
        "decision": decision,
        "tier": tier,
        "reach_out": False,
        "stage_signal": stage_signal,
        "thin_jd": thin_jd,
        "required": classified_required,
        "preferred": classified_preferred,
        "responsibilities": responsibilities[:8],
        "culture": culture[:4],
        "flagged_gaps": flagged_gaps,
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

    return output


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

    # Implements FR-252 (batch triage without a cloud agent)
    """
    buckets: dict[str, list[str]] = {"Tier 1": [], "Tier 2": [], "Skip": []}
    for folder in folders:
        try:
            result = build_stage0_fit_gate(folder)
        except FileNotFoundError as e:
            buckets["Skip"].append(f"| {folder.name} | ERROR: {e} |")
            continue
        out_path = folder / "stage0_fit_gate.json"
        protected = (not force) and _has_extraction_override(out_path)
        if write and not protected:
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
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
        result = build_stage0_fit_gate(folder)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(0)

    out_path = folder / "stage0_fit_gate.json"
    protected = (not args.force) and _has_extraction_override(out_path)
    if write and not protected:
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
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
