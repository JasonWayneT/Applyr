"""
Vertical/industry detection for fit scoring context (CR-039 / FR-192).

Does NOT zero-token reject on domain or customer-base mismatch — surfaces gaps for
transferable-skills scoring only. Supersedes CR-037 hard gate.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional, Tuple

DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "healthcare": (
        "healthcare",
        "health care",
        "life sciences",
        "pharmaceutical",
        "pharma",
        "biotech",
        "medtech",
        "medical device",
        "clinical care",
        "hipaa",
        "payment integrity",
        "coordination of benefits",
        "subrogation",
        "healthcare payment",
        "health outcomes",
        "healthcare industry",
    ),
    "fintech": (
        "fintech",
        "financial services",
        "banking industry",
        "capital markets",
        "wealth management",
        "investment management",
        "payments industry",
    ),
    "insurance": (
        "insurance industry",
        "insurtech",
        "p&c insurance",
        "property and casualty",
        "insurance sector",
    ),
    "government": (
        "government contracting",
        "federal government",
        "public sector",
        "defense industry",
        "defense contracting",
    ),
    "legal": (
        "legal industry",
        "legaltech",
        "law firm",
        "legal sector",
    ),
    "real estate": (
        "real estate industry",
        "proptech",
        "commercial real estate",
    ),
}

DEFAULT_DOMAIN_EXPERIENCE: tuple[str, ...] = (
    "b2b saas",
    "enterprise software",
    "platform",
    "software",
    "integration",
)

_OPTIONAL_IN_CLAUSE = re.compile(
    r"(?:"
    r"nice\s+plus|nice to have|preferably|not required|may not have experience|"
    r"\boptional\b|is beneficial|\(preferred\)|background is a plus"
    r")",
    re.I,
)

_PM_YEARS_CLAUSE = re.compile(
    r"years?\)?\s+in\s+product\s+management",
    re.I,
)

_REQUIRED_DOMAIN_PATTERNS = (
    re.compile(
        r"(\d+)\s*[-–]\s*(\d+)\s+years?\s+of\s+experience\s+in\s+(?:the\s+)?(.+?)\s*"
        r"(?:industry|sector|field)\b",
        re.I,
    ),
    re.compile(
        r"(\d+)\s*\+\s*years?\s+of\s+experience\s+in\s+(?:the\s+)?(.+?)\s*"
        r"(?:industry|sector|field)\b",
        re.I,
    ),
    re.compile(
        r"(?:minimum|min\.?|at least|requires?)\s*(\d+)\s+years?\s+(?:of\s+)?experience\s+in\s+"
        r"(?:the\s+)?(.+?)\s*(?:industry|sector|field)\b",
        re.I,
    ),
    re.compile(
        r"(\d+)\s+years?\s+of\s+experience\s+in\s+(?:the\s+)?(?:US\s+)?(.+?)\s*"
        r"(?:industry|sector|field)\b",
        re.I,
    ),
)


def _normalize_token(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _canonical_from_text(text: str) -> Optional[str]:
    blob = _normalize_token(text)
    if not blob:
        return None
    for canon, aliases in DOMAIN_ALIASES.items():
        for alias in aliases:
            if alias in blob:
                return canon
    return None


def _candidate_canonicals(domain_experience: Iterable[str]) -> set[str]:
    found: set[str] = set()
    for entry in domain_experience:
        blob = _normalize_token(entry)
        if not blob:
            continue
        canon = _canonical_from_text(blob)
        if canon:
            found.add(canon)
            continue
        if blob in DOMAIN_ALIASES:
            found.add(blob)
    return found


def get_domain_experience(prefs: dict | None) -> list[str]:
    raw = (prefs or {}).get("domain_experience")
    if isinstance(raw, list) and raw:
        return [str(x) for x in raw if str(x).strip()]
    return list(DEFAULT_DOMAIN_EXPERIENCE)


def extract_required_domains(jd_text: str) -> list[tuple[int, str, str]]:
    """Return (min_years, domain_blob, canonical_domain) for vertical clauses in JD."""
    if not jd_text:
        return []

    results: list[tuple[int, str, str]] = []
    seen: set[tuple[int, str]] = set()

    chunks = re.split(r"[\n\r•]|(?<=[.!?])\s+", jd_text)
    for chunk in chunks:
        clause = chunk.strip()
        if len(clause) < 25:
            continue
        if _OPTIONAL_IN_CLAUSE.search(clause):
            continue
        if _PM_YEARS_CLAUSE.search(clause):
            continue

        for pat in _REQUIRED_DOMAIN_PATTERNS:
            for match in pat.finditer(clause):
                groups = match.groups()
                if len(groups) == 3:
                    min_years = int(groups[0])
                    domain_blob = groups[2].strip()
                elif len(groups) == 2:
                    min_years = int(groups[0])
                    domain_blob = groups[1].strip()
                else:
                    continue

                canon = _canonical_from_text(domain_blob)
                if not canon:
                    continue

                key = (min_years, canon)
                if key in seen:
                    continue
                seen.add(key)
                results.append((min_years, domain_blob, canon))

    return results


def has_required_domain_requirements(jd_text: str) -> bool:
    return bool(extract_required_domains(jd_text))


def get_domain_gaps(jd_text: str, prefs: dict | None = None) -> list[dict]:
    """
    Verticals the JD emphasizes that are not in candidate domain_experience.
    Informational only — never used for zero-token reject (FR-192).
    """
    min_years_threshold = int((prefs or {}).get("required_domain_min_years") or 2)
    candidate_domains = _candidate_canonicals(get_domain_experience(prefs))
    gaps: list[dict] = []
    seen: set[str] = set()

    for min_years, blob, canon in extract_required_domains(jd_text):
        if min_years < min_years_threshold:
            continue
        if canon in candidate_domains or canon in seen:
            continue
        seen.add(canon)
        gaps.append({"vertical": canon, "min_years": min_years, "jd_phrase": blob[:80]})

    return gaps


def check_domain_gate(jd_text: str, prefs: dict | None = None) -> Tuple[bool, str]:
    """Deprecated gate API — always passes (CR-039). Use get_domain_gaps for diagnostics."""
    return True, ""


def transferable_skills_prompt_block(jd_text: str, prefs: dict | None = None) -> str:
    """Inject when JD mentions vertical industry context (FR-192)."""
    gaps = get_domain_gaps(jd_text, prefs)
    candidate = ", ".join(get_domain_experience(prefs)[:6]) or "platform PM"
    base = (
        "TRANSFERABLE SKILLS POLICY: Do NOT reject solely because the JD's industry vertical "
        "or customer base (B2C vs B2B) differs from the candidate's background. Score PM "
        "craft overlap: platform/roadmap ownership, cross-functional delivery, agile execution, "
        "stakeholder alignment, data/system complexity, compliance-aware product work, and "
        "metrics-driven iteration. Domain or customer-base gaps may appear in RiskFlags — "
        "never as the sole reject reason or score below 40 for mismatch alone."
    )
    if not gaps:
        return base
    verticals = ", ".join(g["vertical"] for g in gaps)
    return (
        f"{base} JD emphasizes vertical experience in: {verticals}. "
        f"Candidate background: {candidate}. Bridge transferable wins; do not auto-reject."
    )
