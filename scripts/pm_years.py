"""Years-of-experience figure from workExperience.md §1.0. Not a hardcoded constant."""

from __future__ import annotations

import re

_SECTION_1_0_RE = re.compile(
    r"### 1\.0\b.*?(?=\n### |\n## |\Z)",
    re.S,
)
_YEARS_RE = re.compile(
    r"with\s+\*\*(\d+)\s+years\*\*\s+of experience",
    re.I,
)
_YEAR_WORDS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
}


def parse_pm_years_of_experience(we_text: str) -> int:
    """Return the §1.0 PM years figure. Raises if the sourced line is missing."""
    section_match = _SECTION_1_0_RE.search(we_text or "")
    section = section_match.group(0) if section_match else (we_text or "")
    match = _YEARS_RE.search(section)
    if not match:
        raise ValueError("workExperience.md §1.0 is missing the years-of-experience figure")
    years = int(match.group(1))
    if years < 1 or years > 40:
        raise ValueError(f"workExperience.md §1.0 years figure is out of range: {years}")
    return years


def _never_list(years: int) -> str:
    values = [str(n) for n in range(4, years)]
    if not values:
        return "a lower invented figure"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} or {values[1]}"
    return ", ".join(values[:-1]) + f", or {values[-1]}"


def pm_years_hard_constraint(years: int) -> str:
    word = _YEAR_WORDS.get(years, str(years))
    return (
        f"Total product management experience: {years} years "
        f"(write '{word} years' or '{years} years'; never {_never_list(years)})"
    )


def years_constraint_from_we(we_text: str) -> str:
    return pm_years_hard_constraint(parse_pm_years_of_experience(we_text))
