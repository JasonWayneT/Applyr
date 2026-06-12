"""
Canonical approved numeric tokens for resume/cover validation (CR-031 / FR-174).

Single source — import here instead of duplicating lists in drafting_engine,
verify_master_claims, and quality gates.
"""
from __future__ import annotations

import re
from typing import List, Set

# Derived from workExperience MET-* lines + catalog-backed variants.
APPROVED_METRICS: List[str] = [
    "$40", "40M", "40,000,000", "40000000",
    "3,500", "3500",
    "25,000", "25000",
    "7%",
    "$1M", "$2M", "$3M", "1,000,000", "2,000,000", "3,000,000",
    "40%",
    "100%",
    "90%",
    "200",
    "300",
    "700",
    "$288", "288,000",
    "$8,500", "8500",
    "$22,100", "22,100",
    "$34,000", "34000",
    "6+", "6 years",
    "100", "100+",
    "10",
    "0",
    "5",
    "$800,000", "800,000", "$800K", "800K",
]

# Contact header, dates, and area codes — not résumé metrics.
_EXCLUDED_LITERALS: Set[str] = {
    "760", "317", "8264", "619", "858",
    "2017", "2018", "2019", "2021", "2022", "2023", "2024", "2025", "2026",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "10", "11", "12",
}

_NUMERIC_PATTERN = re.compile(
    r"(?:\$[\d,]+(?:M|K|B)?|\d+(?:,\d{3})*(?:\.\d+)?\s*%|\d{1,3}(?:,\d{3})+|\b\d{2,}\b)"
)

_YEARish = re.compile(r"^20\d{2}$")


def _approved_match(clean: str) -> bool:
    cl = clean.lower().replace(",", "")
    for approved in APPROVED_METRICS:
        al = approved.lower().replace(",", "")
        if al in cl or cl in al:
            return True
    return False


def _is_excluded_token(clean: str) -> bool:
    raw = clean.strip().replace(",", "").replace("$", "").replace("%", "")
    if raw in _EXCLUDED_LITERALS:
        return True
    if _YEARish.match(raw):
        return True
    if re.match(r"^\d{1,2}$", raw):
        return True
    return False


def find_unapproved_metrics(text: str) -> List[str]:
    """Return numeric fragments in text that are not on the approved list."""
    found = _NUMERIC_PATTERN.findall(text or "")
    unapproved: List[str] = []
    for num in found:
        clean = num.strip()
        if _is_excluded_token(clean):
            continue
        if not _approved_match(clean):
            unapproved.append(clean)
    return unapproved


def metric_integrity_message(unapproved: List[str]) -> str:
    return (
        "METRIC INTEGRITY: Unverified numeric claims found (not in approved metrics list): "
        + ", ".join(unapproved)
    )
