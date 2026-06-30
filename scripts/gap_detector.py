"""
Gap acknowledgment injection (Epic 9).

Detects soft domain gaps from a JD profile and assembles an honest,
non-apologetic gap acknowledgment paragraph using a locked template.
No LLM calls — all output is deterministic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SoftGap:
    requirement_text: str       # The JD requirement that scored low
    relevance_score: float      # Score against candidate profile (< 0.40)
    gap_area: str               # Human-readable label: "fintech/payments", etc.
    transfer_skill: str         # What Jason has that's adjacent


# ---------------------------------------------------------------------------
# Gap-type classifier (Story 9.2)
# ---------------------------------------------------------------------------

_GAP_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "fintech/payments": [
        "fintech", "payments", "payment processing", "transactions", "banking",
        "financial services", "credit", "debit", "stripe", "checkout",
        "pci", "ach", "wire transfer", "lending", "loan", "mortgage",
    ],
    "healthcare/domain": [
        "healthcare", "health system", "ehr", "emr", "fhir", "hipaa",
        "clinical", "patient", "provider", "payer", "medical device",
        "pharma", "pharmaceutical", "hospital",
    ],
    "crm/lifecycle": [
        "crm ownership", "own the crm", "lifecycle marketing",
        "marketing automation", "hubspot admin", "salesforce admin",
        "marketo", "pardot", "eloqua", "email automation", "lead scoring",
        "drip campaign",
    ],
    "consumer/b2c": [
        "consumer product", "b2c", "consumer app", "mobile consumer",
        "social product", "gaming", "marketplace consumer", "viral growth",
        "user acquisition", "dau", "mau", "consumer mobile",
    ],
    "iot/hardware": [
        "iot", "hardware", "embedded", "firmware", "connected device",
        "sensor", "bluetooth", "zigbee", "edge computing", "physical product",
    ],
    "edtech/lms": [
        "edtech", "lms", "learning management", "curriculum", "k-12",
        "higher education", "student information system", "academic",
    ],
    "ai/ml": [
        "machine learning", "ml model", "ai product", "llm", "generative ai",
        "model training", "nlp", "computer vision", "recommendation engine",
    ],
}

# Transfer skills Jason has that are adjacent to each gap area
_TRANSFER_SKILLS: Dict[str, str] = {
    "fintech/payments": (
        "platform data integrity, cross-functional compliance coordination, "
        "and building trust-critical product features under regulatory constraints"
    ),
    "healthcare/domain": (
        "compliance workflows, data privacy, and cross-functional stakeholder "
        "alignment under regulatory constraints"
    ),
    "crm/lifecycle": (
        "owning the data that powers lifecycle tools — I've built and maintained "
        "the contact database and data pipeline that CRM systems consume, "
        "not the CRM product itself"
    ),
    "consumer/b2c": (
        "enterprise SaaS platform ownership with a strong focus on user trust, "
        "product reliability, and measurable customer outcomes"
    ),
    "iot/hardware": (
        "cross-functional platform delivery, vendor integration coordination, "
        "and managing product reliability across complex system dependencies"
    ),
    "edtech/lms": (
        "platform product management with a focus on user workflows, "
        "data integrity, and stakeholder alignment"
    ),
    "ai/ml": (
        "technically complex platform product work close to engineering, "
        "including data pipeline ownership, API integration, and working "
        "with engineers on system architecture decisions"
    ),
    "domain_generic": (
        "technically complex platform product work and cross-functional delivery "
        "in high-stakes, revenue-bearing environments"
    ),
}

# Honest statements per gap type — reviewed and approved
_HONEST_STATEMENTS: Dict[str, str] = {
    "fintech/payments": (
        "I don't have direct payments or fintech product experience."
    ),
    "healthcare/domain": (
        "I haven't worked in the healthcare domain specifically."
    ),
    "crm/lifecycle": (
        "My CRM experience is adjacent: I've owned the data that powers lifecycle tools, "
        "not the CRM product itself."
    ),
    "consumer/b2c": (
        "My background is in enterprise SaaS rather than consumer product."
    ),
    "iot/hardware": (
        "I haven't worked with connected hardware or embedded systems directly."
    ),
    "edtech/lms": (
        "I haven't worked in the edtech or LMS space specifically."
    ),
    "ai/ml": (
        "I haven't owned an AI or ML product — my background is in platform "
        "infrastructure and data integrity, not model training or AI product surfaces."
    ),
    "domain_generic": (
        "My background doesn't include {gap_area} specifically."
    ),
}

# Locked template (Story 9.3)
_GAP_TEMPLATE = (
    "I'll be direct about {gap_area}: {honest_statement} "
    "What I bring instead is {transfer_skill}. "
    "If there's room to develop {gap_area} experience on the job, "
    "I'd welcome the chance to make that case."
)


def classify_gap_type(requirement_text: str) -> str:
    """Map a JD requirement string to a gap area label (Story 9.2)."""
    req_l = requirement_text.lower()
    for gap_area, signals in _GAP_TYPE_KEYWORDS.items():
        if any(s in req_l for s in signals):
            return gap_area
    return "domain_generic"


# ---------------------------------------------------------------------------
# Gap detection (Story 9.1)
# ---------------------------------------------------------------------------

_DOMAIN_GAP_SIGNALS = frozenset({
    "fintech", "payments", "healthcare", "clinical", "consumer", "b2c",
    "iot", "hardware", "embedded", "edtech", "lms", "learning management",
    "gaming", "ml model", "machine learning", "generative ai",
})

_SKILL_GAP_SIGNALS = frozenset({
    "python", "sql", "tableau", "snowflake", "looker", "dbt", "spark",
    "kubernetes", "docker", "react", "typescript", "java", "scala",
    "aws", "gcp", "azure",
})


def _is_domain_gap(requirement_text: str) -> bool:
    """True when the gap is a domain/industry gap, not a missing hard skill."""
    req_l = requirement_text.lower()
    has_domain = any(s in req_l for s in _DOMAIN_GAP_SIGNALS)
    has_skill = any(s in req_l for s in _SKILL_GAP_SIGNALS)
    return has_domain and not has_skill


def _score_requirement_relevance(requirement_text: str, candidate_profile: dict) -> float:
    """Estimate relevance of a JD requirement against Jason's known background.

    Returns a float 0.0–1.0. Below 0.40 is considered a soft gap.
    This is a keyword-based heuristic since we're not calling an LLM.
    """
    req_l = requirement_text.lower()

    # Jason's strong areas — high relevance
    strong_signals = [
        "platform", "saas", "b2b", "data", "api", "integration",
        "roadmap", "prioritiz", "stakeholder", "cross-functional",
        "security", "compliance", "migration", "reliability",
        "enterprise", "customer", "churn", "retention",
    ]
    strong_hits = sum(1 for s in strong_signals if s in req_l)

    # Domain-specific gaps — low relevance
    weak_signals = list(_DOMAIN_GAP_SIGNALS) + list(_SKILL_GAP_SIGNALS)
    weak_hits = sum(1 for s in weak_signals if s in req_l)

    if strong_hits == 0 and weak_hits > 0:
        return 0.20
    if strong_hits > 0 and weak_hits > 0:
        return 0.35
    if strong_hits > 0 and weak_hits == 0:
        return 0.80
    return 0.50  # neutral


def detect_soft_gaps(
    jd_profile,
    candidate_profile: dict,
    overall_fit_score: float,
) -> List[SoftGap]:
    """Detect soft domain gaps when overall fit is still strong (Story 9.1).

    Returns soft gaps only when:
    - A specific JD requirement scores < 0.40 relevance
    - Overall fit score >= 72
    - The gap is a DOMAIN gap (industry, product type) not a SKILL gap

    Returns empty list if no soft gaps or overall fit < 72.
    """
    if overall_fit_score < 72:
        return []

    requirements = getattr(jd_profile, "requirements", [])
    gaps: List[SoftGap] = []

    for req_text in requirements:
        if not _is_domain_gap(req_text):
            continue
        relevance = _score_requirement_relevance(req_text, candidate_profile)
        if relevance >= 0.40:
            continue
        gap_area = classify_gap_type(req_text)
        transfer_skill = _TRANSFER_SKILLS.get(gap_area, _TRANSFER_SKILLS["domain_generic"])
        gaps.append(SoftGap(
            requirement_text=req_text,
            relevance_score=relevance,
            gap_area=gap_area,
            transfer_skill=transfer_skill,
        ))

    # Sort by relevance (lowest = most important to acknowledge)
    gaps.sort(key=lambda g: g.relevance_score)
    return gaps


# ---------------------------------------------------------------------------
# Gap paragraph assembly (Story 9.3)
# ---------------------------------------------------------------------------

def build_gap_paragraph(gap: SoftGap) -> str:
    """Assemble the gap acknowledgment paragraph from the locked template (Story 9.3).

    No LLM. Output matches the template exactly with gap-area substitutions.
    """
    honest_statement = _HONEST_STATEMENTS.get(gap.gap_area, _HONEST_STATEMENTS["domain_generic"])
    if "{gap_area}" in honest_statement:
        honest_statement = honest_statement.format(gap_area=gap.gap_area)

    paragraph = _GAP_TEMPLATE.format(
        gap_area=gap.gap_area,
        honest_statement=honest_statement,
        transfer_skill=gap.transfer_skill,
    )
    return paragraph.strip()


def select_primary_gap(gaps: List[SoftGap]) -> Optional[SoftGap]:
    """Return the single highest-priority gap to acknowledge (one per CL)."""
    if not gaps:
        return None
    # Lowest relevance score = most important gap to address
    return min(gaps, key=lambda g: g.relevance_score)
