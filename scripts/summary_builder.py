"""
JD-Adaptive Professional Summary Builder (Epic 4).

Replaces LLM-generated summary with deterministic string assembly.
Output always contains B2B SaaS legibility signals without locking Jason
into a "B2B SaaS" label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SummaryContext:
    years_experience: int
    environment_type: str           # "enterprise SaaS" | "SaaS platforms" | "software products"
    focus_areas: List[str]          # top 3 from JD skill match, max 3
    company_name: str               # most recent employer display name
    scope_description: str          # what was owned
    scale_metric: str               # e.g. "~3,500 enterprise and mid-market accounts"
    partners: List[str]             # JD-relevant subset of verified partners
    outcome_1: str                  # strongest metric phrase
    outcome_2: str                  # second metric phrase


# ---------------------------------------------------------------------------
# Verified data (from workExperience.md; do not change without updating source)
# ---------------------------------------------------------------------------

# Set to 7 on 2026-07-18 (Jason's call). Was 6, which undersold him and contradicted
# the resume's own date range (Zero To Sixty starts June 2017). Derivation lives in
# data/workExperience.md Section 1.0: first PM/PO title Feb 2019 -> Jan 2026 = 6.9 yrs.
_YEARS_EXPERIENCE = 7

_SCALE_ENTERPRISE = "~3,500 enterprise and mid-market accounts"  # MET-02
_SCALE_CONSUMER = "~25,000 active users"                         # MET-03
# Used when the run's selected bullets don't happen to include the MET-02/MET-03
# figure — introducing an ungrounded number here gets the whole summary discarded
# by audit_text_against_bullet_corpus() downstream, so fall back to a scope
# description with no number at all rather than risk that.
_SCALE_ENTERPRISE_UNGROUNDED = "a large enterprise and mid-market customer base"
_SCALE_CONSUMER_UNGROUNDED = "a large active user base"

_SCOPE_DESCRIPTION = (
    "a $40M ARR B2B media monitoring and contact database platform"
)

_COMPANY_DISPLAY = "Cision"

_OUTCOME_1 = "eliminated a 40% data drop-off across the customer contact pipeline"
_OUTCOME_2_SECURITY = "resolved 90% of a 300-item security backlog while maintaining core roadmap delivery"
# ATTRIBUTION (corrected 2026-07-18, Jason-confirmed): the prior wording here was
# "sustained retention near 7% annually THROUGH a capacity model...", which welded
# two separate facts into a false causal chain and shipped in 4 of 4 resumes before
# it was caught. Ground truth: the ~7% churn rate (MET-04) was the collective result
# of reliability, security, and migration work; the capacity model's actual job was
# quarterly prioritization and roadmap creation, not churn reduction. The owned verb
# is "prioritized" - Jason prioritized the work; the work held the number. Do not
# reintroduce a causal connective ("through", "by", "driving") between a capacity/
# planning artifact and a business-outcome metric.
_OUTCOME_2_DEFAULT = "prioritized the reliability, security, and migration work that held annual churn near 7%"

_VERIFIED_PARTNERS_ALL = [
    "Engineering", "DBA", "DevOps", "Customer Experience",
    "Customer Support", "Sales", "Account Management",
    "Legal", "InfoSec", "Product Marketing", "Executive Leadership",
]

# JD keyword → partner(s) most relevant to surface
_PARTNER_SIGNALS: List[tuple] = [
    ("security", ["InfoSec", "Legal"]),
    ("compliance", ["Legal", "InfoSec"]),
    ("data", ["DBA", "Engineering"]),
    ("infrastructure", ["DevOps", "Engineering"]),
    ("customer", ["Customer Experience", "Account Management"]),
    ("churn", ["Customer Experience", "Account Management", "Sales"]),
    ("migration", ["Engineering", "DevOps", "Customer Experience"]),
    ("api", ["Engineering"]),
    ("roadmap", ["Engineering", "Sales", "Product Marketing"]),
    ("analytics", ["DBA", "Engineering"]),
    ("saas", ["Sales", "Account Management"]),
    ("enterprise", ["Sales", "Account Management", "Executive Leadership"]),
    ("onboarding", ["Customer Experience", "Sales"]),
    ("revenue", ["Sales", "Account Management", "Executive Leadership"]),
]

# ---------------------------------------------------------------------------
# JD context classifier (Story 4.2)
# ---------------------------------------------------------------------------

_ENTERPRISE_SIGNALS = frozenset({
    "enterprise", "b2b", "accounts", "arr", "account management",
    "sales-led", "sales led", "crm", "mid-market", "midmarket",
    "contract", "renewal", "churn",
})

_CONSUMER_SIGNALS = frozenset({
    "users", "growth", "b2c", "dau", "mau", "consumer",
    "subscriber", "viral", "product-led", "plg",
    "self-serve", "freemium",
})
# "retention" deliberately excluded — data/conversion_rubric.md R8 treats retention/
# churn as a B2B SaaS legibility signal, not a consumer one. Including it here caused
# B2B JDs that mention retention (e.g. a nonprofit donor-CRM platform) to misclassify
# as "consumer," pulling in an ungrounded scale metric the resume's actual bullets
# never support and getting the whole adaptive summary rejected by the bullet-corpus
# audit downstream.


def classify_jd_context(jd_profile) -> Literal["enterprise", "consumer", "neutral"]:
    """Classify JD as enterprise, consumer, or neutral (Story 4.2)."""
    keywords = set(getattr(jd_profile, "keywords", []))
    themes_text = " ".join(getattr(jd_profile, "priority_themes", [])).lower()
    reqs_text = " ".join(getattr(jd_profile, "requirements", [])).lower()
    all_text = " ".join(keywords).lower() + " " + themes_text + " " + reqs_text

    enterprise_hits = sum(1 for s in _ENTERPRISE_SIGNALS if s in all_text)
    consumer_hits = sum(1 for s in _CONSUMER_SIGNALS if s in all_text)

    if enterprise_hits > consumer_hits:
        return "enterprise"
    if consumer_hits > enterprise_hits:
        return "consumer"
    return "neutral"


# ---------------------------------------------------------------------------
# Context extraction (Story 4.1)
# ---------------------------------------------------------------------------

def _select_partners(jd_profile, max_partners: int = 3) -> List[str]:
    """Return JD-relevant verified partners."""
    keywords = set(getattr(jd_profile, "keywords", []))
    themes_text = " ".join(getattr(jd_profile, "priority_themes", [])).lower()
    reqs_text = " ".join(getattr(jd_profile, "requirements", [])).lower()
    all_text = " ".join(keywords).lower() + " " + themes_text + " " + reqs_text

    selected: List[str] = []
    seen: set = set()
    for signal, partners in _PARTNER_SIGNALS:
        if signal in all_text:
            for p in partners:
                if p not in seen and len(selected) < max_partners:
                    selected.append(p)
                    seen.add(p)

    # Fill with defaults if not enough
    for p in ("Engineering", "Customer Experience", "Sales"):
        if p not in seen and len(selected) < max_partners:
            selected.append(p)
            seen.add(p)

    return selected[:max_partners]


def _select_focus_areas(jd_profile, max_areas: int = 3) -> List[str]:
    """Pull top focus areas from JD themes/keywords."""
    themes = getattr(jd_profile, "priority_themes", [])
    if themes:
        # Shorten themes to 3–4 words
        areas = []
        for t in themes[:max_areas]:
            words = t.split()
            areas.append(" ".join(words[:4]))
        return areas[:max_areas]
    keywords = getattr(jd_profile, "keywords", [])
    return keywords[:max_areas]


def _grounded(number_bearing_phrase: str, bullet_corpus: str) -> bool:
    """True if the digits in `number_bearing_phrase` appear in `bullet_corpus`."""
    if not bullet_corpus:
        return True
    digits = re.sub(r"[^\d]", "", number_bearing_phrase)
    if not digits:
        return True
    return digits in re.sub(r"[^\d]", "", bullet_corpus)


def extract_summary_context(
    jd_profile, candidate_profile: dict = None, jd_text: str = "", bullet_corpus: str = ""
) -> SummaryContext:
    """Build SummaryContext from JdProfile and candidate data (Story 4.1)."""
    jd_context = classify_jd_context(jd_profile)

    if jd_context == "consumer":
        scale_metric = _SCALE_CONSUMER if _grounded(_SCALE_CONSUMER, bullet_corpus) else _SCALE_CONSUMER_UNGROUNDED
        environment_type = "SaaS platforms"
    elif jd_context == "enterprise":
        scale_metric = _SCALE_ENTERPRISE if _grounded(_SCALE_ENTERPRISE, bullet_corpus) else _SCALE_ENTERPRISE_UNGROUNDED
        environment_type = "enterprise SaaS"
    else:
        scale_metric = _SCALE_ENTERPRISE if _grounded(_SCALE_ENTERPRISE, bullet_corpus) else _SCALE_ENTERPRISE_UNGROUNDED
        environment_type = "software products"

    from conversion_framing import has_security_jd_signal

    outcome_2 = _OUTCOME_2_SECURITY if has_security_jd_signal(jd_text) else _OUTCOME_2_DEFAULT

    return SummaryContext(
        years_experience=_YEARS_EXPERIENCE,
        environment_type=environment_type,
        focus_areas=_select_focus_areas(jd_profile),
        company_name=_COMPANY_DISPLAY,
        scope_description=_SCOPE_DESCRIPTION,
        scale_metric=scale_metric,
        partners=_select_partners(jd_profile),
        outcome_1=_OUTCOME_1,
        outcome_2=outcome_2,
    )


# ---------------------------------------------------------------------------
# Template variants (Story 4.3)
# ---------------------------------------------------------------------------

# Note: "B2B SaaS" is NEVER used as a direct label (rule enforced in Story 4.5 test).

_TEMPLATE_ENTERPRISE = (
    "Product Manager with {years} years owning {environment_type}, "
    "most recently at {company} where I managed {scope} supporting {scale}. "
    "I partner with {partner_1} and {partner_2} to drive roadmap decisions grounded in "
    "customer trust and measurable outcomes, including {outcome_1} and {outcome_2}. "
    "I'm strongest in technically complex environments where platform reliability "
    "and cross-functional alignment are competitive differentiators."
)

_TEMPLATE_CONSUMER = (
    "Product Manager with {years} years working across {environment_type}, "
    "most recently at {company} where I owned {scope} used by {scale}. "
    "I work at the boundary of Engineering and {partner_1} "
    "to convert customer-visible failures into measurable product improvements, "
    "including {outcome_1}. "
    "My background bridges enterprise platform discipline and user-behavior thinking."
)

_TEMPLATE_NEUTRAL = (
    "Product Manager with {years} years across {environment_type}, "
    "most recently at {company} owning {scope}. "
    "I partner with {partner_1}, {partner_2}, and {partner_3} "
    "to deliver platform improvements with clear business outcomes. "
    "Recent wins include {outcome_1}, and {outcome_2}."
)


def assemble_summary(context: SummaryContext, jd_context: str) -> str:
    """Fill the appropriate template with SummaryContext (Story 4.3).

    Returns a single paragraph under 80 words.
    """
    partners = context.partners + ["Engineering", "Product Marketing", "Sales"]

    if jd_context == "enterprise":
        text = _TEMPLATE_ENTERPRISE.format(
            years=context.years_experience,
            environment_type=context.environment_type,
            company=context.company_name,
            scope=context.scope_description,
            scale=context.scale_metric,
            partner_1=partners[0] if len(partners) > 0 else "Engineering",
            partner_2=partners[1] if len(partners) > 1 else "Sales",
            outcome_1=context.outcome_1,
            outcome_2=context.outcome_2,
        )
    elif jd_context == "consumer":
        text = _TEMPLATE_CONSUMER.format(
            years=context.years_experience,
            environment_type=context.environment_type,
            company=context.company_name,
            scope=context.scope_description,
            scale=context.scale_metric,
            partner_1=partners[0] if partners else "Engineering",
            outcome_1=context.outcome_1,
        )
    else:
        text = _TEMPLATE_NEUTRAL.format(
            years=context.years_experience,
            environment_type=context.environment_type,
            company=context.company_name,
            scope=context.scope_description,
            partner_1=partners[0] if len(partners) > 0 else "Engineering",
            partner_2=partners[1] if len(partners) > 1 else "Customer Experience",
            partner_3=partners[2] if len(partners) > 2 else "Sales",
            outcome_1=context.outcome_1,
            outcome_2=context.outcome_2,
        )

    # Collapse any double spaces
    text = re.sub(r"  +", " ", text).strip()
    return text


def build_jd_adaptive_summary(
    jd_profile, candidate_profile: dict = None, jd_text: str = "", bullet_corpus: str = ""
) -> Optional[str]:
    """Main entry point (Story 4.4).

    Returns assembled summary string, or None if required fields are missing
    (caller should fall back to LLM generation and log a WARN).
    """
    try:
        context = extract_summary_context(
            jd_profile, candidate_profile, jd_text=jd_text, bullet_corpus=bullet_corpus
        )
        # Verify required fields are populated
        if not context.scope_description or not context.scale_metric or not context.years_experience:
            return None
        jd_context = classify_jd_context(jd_profile)
        return assemble_summary(context, jd_context)
    except Exception:
        return None
