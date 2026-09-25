#!/usr/bin/env python3
"""CR-112 three-way qualification-risk gate for Stage 0 extraction fallout.

Every bullet the NLP extractor (`build_stage0_fit_gate._extract_sections_nlp`)
could not confidently bucket -- because no provider was configured, the
provider response failed to parse, or a provider response only partially
mapped the batch -- gets exactly one of:

- ``NON_QUALIFICATION`` -- may bypass review, but is always disclosed.
- ``QUALIFICATION_LIKELY`` -- pauses.
- ``AMBIGUOUS`` -- pauses.

Behavior is binary: NON_QUALIFICATION (bypass) vs. everything else (pause).
The three-way label is receipt annotation for a human reviewer's triage
only -- nothing here treats QUALIFICATION_LIKELY vs. AMBIGUOUS as a
pass/fail distinction (CR-112 v3 design, "binary-behavior" change).

Independence from the failed parser (CR-112 v3, "made testable"):
1. This module decides review-vs-bypass only. It never assigns a real
   required/preferred/responsibilities/culture bucket -- that stays the
   job of ``_extract_sections`` / ``_extract_sections_nlp`` (or a human's
   explicit manual bucket correction, see ``stage0_requirement_extraction_
   review.py``). Nothing here is imported by, or shares a regex/helper
   with, those bucketing functions, and nothing here imports
   ``_looks_like_qualification`` / ``_looks_like_duty`` or touches the
   LogReg classifier.
2. Every NON_QUALIFICATION signal is matched with ``re.search`` (anywhere
   in the line), never ``re.match`` (leading-phrase only). Anchoring at
   the start is exactly the failure mode that let
   ``build_stage0_fit_gate._QUAL_LEADIN_RE`` (a `.match()`-anchored
   pattern) miss "Must pass a Level II fingerprint background check" and
   "Nights and weekends availability required" -- both real eligibility
   statements that do not open with a recognized qualification lead-in
   phrase. This module must not repeat that mistake.
3. The default on no confident NON_QUALIFICATION match is AMBIGUOUS (pause)
   -- the inverse of ``_looks_like_qualification``'s default-False
   (non-qualifying) behavior. Uncertainty pauses; the burden of proof is
   on NON_QUALIFICATION.

The trap this gate must not fall into (CR-112 v3, "jd_05_wideworld"):
"Must pass a Level II fingerprint background check" and "Nights and
weekends availability required" look, on the surface, like they could
hide behind a background-check or schedule-logistics NON_QUALIFICATION
category. They must not: both are explicit, "must"/"required"-worded
eligibility conditions, not informational disclosure. Any line phrased as
an explicit demand ("must pass", "must have", "required", "mandatory")
never bypasses on the strength of a topical NON_QUALIFICATION keyword
match alone -- see ``_ELIGIBILITY_DEMAND_RE`` below.
"""
from __future__ import annotations

import re

NON_QUALIFICATION = "NON_QUALIFICATION"
QUALIFICATION_LIKELY = "QUALIFICATION_LIKELY"
AMBIGUOUS = "AMBIGUOUS"

_VALID_LABELS = {NON_QUALIFICATION, QUALIFICATION_LIKELY, AMBIGUOUS}


def is_bypass(label: str) -> bool:
    """The one behaviorally-meaningful question: does this label bypass review?"""
    return label == NON_QUALIFICATION


# ---------------------------------------------------------------------------
# The trap guard -- checked first, applies to every category below.
# ---------------------------------------------------------------------------
# An explicit "must pass/have/be/meet/maintain/clear" or a bare
# "required"/"mandatory" reads as a pass/fail eligibility condition, not
# disclosure -- category 3 (EEO/background) and category 6 (location/travel)
# below only ever cover *informational* text, never an explicit demand.
_ELIGIBILITY_DEMAND_RE = re.compile(
    r"\bmust\s+(pass|have|be|meet|maintain|clear|hold)\b|\b(required|mandatory)\b",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _norm_title(text: str) -> str:
    """Loose normalization for title-line comparison: strip leading bullet
    marks/punctuation noise so trailing commas ("Product Manager, Platform")
    still compare sanely against the extracted role field."""
    cleaned = (text or "").strip().lstrip("-•*◦▪▸→").strip()
    cleaned = cleaned.rstrip(".").strip()
    return re.sub(r"\s+", " ", cleaned).lower()


# ---------------------------------------------------------------------------
# Category 1: compensation range / pay structure text
# ---------------------------------------------------------------------------
_COMPENSATION_RE = re.compile(
    r"\b(salary|compensation|pay)\s+(range|band|structure)\b|"
    r"\bbase\s+(salary|pay)\b|\b(OTE|on[- ]target\s+earnings)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Category 2: benefits / perks text
# ---------------------------------------------------------------------------
_BENEFITS_RE = re.compile(
    r"\bbenefits?\b|\bperks?\b|\bwellbeing\b|\bwell-being\b|\bretirement\b|"
    r"\bpension\b|\bhealth\s+insurance\b|\b(pto|paid\s+time\s+off)\b|"
    r"\b401\(k\)\b|\bfinancial\s+security\b|\bstipend\b|"
    r"\blearning\s+and\s+development\b|\bprofessional\s+growth\b|"
    r"\bwe\s+invest\s+in\s+your\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Category 3: EEO / accommodation / non-discrimination boilerplate
# ---------------------------------------------------------------------------
_EEO_RE = re.compile(
    r"\bequal\s+opportunity\b|\bdoes?\s+not\s+discriminate\b|"
    r"\bwithout\s+regard\s+to\b|\breasonable\s+accommodations?\b|"
    r"\bprotected\s+(class|status|veteran)\b",
    re.I,
)
# Background-check text only bypasses as *disclosure* ("we may conduct...",
# "as part of our process"), never as an explicit pass/fail demand -- the
# _ELIGIBILITY_DEMAND_RE guard in classify_qualification_risk() below
# already blocks "must pass a background check" from reaching here.
_BACKGROUND_DISCLOSURE_RE = re.compile(
    r"\bbackground\s+check\b|\bbackground\s+screening\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Category 4: recruiting / application-process instructions
# ---------------------------------------------------------------------------
_RECRUITING_RE = re.compile(
    r"\bhow\s+to\s+apply\b|\bapplication\s+process\b|\brecruit(ing|er|ment)\b|"
    r"\bemployer\s+of\s+record\b|\bhired\s+via\b|\bstaffing\s+agenc(y|ies)\b|"
    r"\btalent\s+acquisition\b|\bhiring\s+partner\b|\bfraud\s+(prevention|notice)\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Category 5: company/role marketing description with no candidate-addressed
# expectation.
# ---------------------------------------------------------------------------
_COMPANY_DESC_RE = re.compile(
    r"\b(is|are)\s+an?\s+[\w\s,/&'-]{0,60}\bcompany\b|"
    r"\bour\s+mission\b|\bfounded\s+in\b|\bwe\s+believe\b|\bwe\s+are\s+a\b|"
    r"\bleading\s+provider\s+of\b|\bprovider\s+of\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Category 6: location/travel logistics stated as information, not
# eligibility. Only informational/descriptive phrasing -- the eligibility
# guard above blocks "required"/"must" schedule or travel demands from
# reaching this category.
# ---------------------------------------------------------------------------
_LOCATION_INFO_RE = re.compile(
    r"\bthis\s+role\s+is\s+based\s+in\b|\bwork\s+location\b|\boffice\s+location\b|"
    r"\bbased\s+in\s+our\b|\bwe\s+(are\s+)?(currently\s+)?hiring\s+in\b",
    re.I,
)

# ---------------------------------------------------------------------------
# Category 7: internal posting instructions (never meant for a candidate to
# read at all).
# ---------------------------------------------------------------------------
_INTERNAL_POSTING_RE = re.compile(
    r"\btalent\s+ops\b|\bdelete\s+as\s+necessary\b|\binternal\s+use\s+only\b|"
    r"\bnot\s+for\s+external\s+(candidates|posting)\b|"
    r"\bposting\s+(instructions?|notes?)\b|\bATS\s+note\b",
    re.I,
)


def classify_qualification_risk(
    text: str,
    *,
    header: str = "",
    role_title: str = "",
) -> tuple[str, str]:
    """Classify one unresolved extraction bullet for the CR-112 three-way gate.

    Returns ``(label, reason_code)``. ``label`` is one of NON_QUALIFICATION /
    QUALIFICATION_LIKELY / AMBIGUOUS. Only NON_QUALIFICATION bypasses review
    (see ``is_bypass``); the QUALIFICATION_LIKELY/AMBIGUOUS split is receipt
    annotation only, never asserted as a pass/fail distinction by callers.

    ``header`` is the JD section header the bullet was extracted under (may
    be empty). ``role_title`` is the title Stage 0 already extracted into
    its own ``role`` field -- used only for the category-8 title-line match,
    an affirmative match against a known field, not a heuristic guess.
    """
    clean = (text or "").strip()
    if not clean:
        return AMBIGUOUS, "empty_text"

    lower = _norm(clean)

    # Category 8: the posting's own title line, matched against the title
    # Stage 0 already extracted (CR-112 v3 addition).
    if role_title and _norm_title(clean) == _norm_title(role_title):
        return NON_QUALIFICATION, "posting_title_line"

    eligibility_demand = bool(_ELIGIBILITY_DEMAND_RE.search(lower))

    # Category 7: internal posting instructions. Never header-protected --
    # an affirmative match here bypasses regardless of which section header
    # it happens to sit under (CR-112 v3: a required-section-header line may
    # enter NON_QUALIFICATION only on an affirmative category match, not
    # because the header itself is "safe").
    if _INTERNAL_POSTING_RE.search(lower):
        return NON_QUALIFICATION, "internal_posting_instruction"

    # Category 5: self-referential marketing hook that leaked as its own
    # extracted "header" (structural signal, not fixture-specific wording):
    # the extractor's own current_header equals the bullet text itself.
    if header and _norm(header) == lower:
        return NON_QUALIFICATION, "company_marketing_self_header"

    if not eligibility_demand:
        # Category 1: compensation range / pay structure.
        if _COMPENSATION_RE.search(lower):
            return NON_QUALIFICATION, "compensation_range"

        # Category 2: benefits / perks.
        if _BENEFITS_RE.search(lower):
            return NON_QUALIFICATION, "benefits_perks"

        # Category 3: EEO / accommodation / non-discrimination boilerplate,
        # or background-check text stated as disclosure (never as an
        # explicit demand -- eligibility_demand already gates that out).
        if _EEO_RE.search(lower) or _BACKGROUND_DISCLOSURE_RE.search(lower):
            return NON_QUALIFICATION, "eeo_or_background_disclosure"

        # Category 4: recruiting / application-process / hiring logistics.
        if _RECRUITING_RE.search(lower):
            return NON_QUALIFICATION, "recruiting_or_hiring_logistics"

        # Category 6: location/travel logistics stated as information.
        if _LOCATION_INFO_RE.search(lower):
            return NON_QUALIFICATION, "location_logistics_information"

    # Category 5 (continued): company/role marketing description with no
    # candidate-addressed expectation. Checked after the topical NON_
    # QUALIFICATION categories above (a company-description line is not an
    # eligibility statement, so this one does not need the demand guard),
    # but before the qualification-likely signals below so a marketing
    # sentence that happens to contain an unrelated capability word (e.g.
    # "leading provider of workflow automation, used by teams worldwide")
    # is not pulled the wrong way by an incidental word match.
    if _COMPANY_DESC_RE.search(lower):
        return NON_QUALIFICATION, "company_marketing_description"

    # --- Nothing above matched. Burden of proof failed to establish
    # NON_QUALIFICATION -- decide only the receipt-annotation label between
    # QUALIFICATION_LIKELY and AMBIGUOUS. Neither bypasses (see is_bypass).
    if eligibility_demand:
        return QUALIFICATION_LIKELY, "explicit_eligibility_demand"

    if _QUALIFICATION_SIGNAL_RE.search(lower):
        return QUALIFICATION_LIKELY, "explicit_capability_vocabulary"

    # Default: AMBIGUOUS. Conservative -- absence of a qualification signal
    # is not itself evidence of NON_QUALIFICATION (property 3: this gate
    # defaults to pause on no confident match, the inverse of
    # _looks_like_qualification's default-False/non-qualifying default).
    return AMBIGUOUS, "no_confident_match"


# ---------------------------------------------------------------------------
# Signals that push toward QUALIFICATION_LIKELY (independent of bucket/
# header -- responsibility-header text is NOT auto-exempted, per CR-112 v3).
# ---------------------------------------------------------------------------
_QUALIFICATION_SIGNAL_RE = re.compile(
    r"\bexperience\s+(working\s+)?(with|of|in)\b|\bknowledge\s+of\b|\bfamiliarity\s+with\b|"
    r"\bunderstanding\s+of\b|\bability\s+(to|and/or)\b|\bcomfort(able)?\s+with\b|"
    r"\bwillingness\b|\bskills?\b|\bownership\b|\b(partner|work)\s+with\b|"
    r"\bcross-functional\b|\bsequence\b|\bprioritiz(e|ation)\b|\btranslate\b|"
    r"\bkeep\s+[\w\s]{0,20}\s+(in\s+the\s+loop|aligned|honest)\b|"
    r"\buse\s+metrics\s+to\s+decide\b|\bown\s+(the\s+)?roadmap\b|"
    r"\broadmap\s+ownership\b|\bwrite\s+clear\s+requirements\b|"
    r"\bcut\s+operational\s+waste\b|\bturn\s+audit\s+findings\b",
    re.I,
)
