"""
Deterministic seniority gating (CR-019 / FR-109).

- Title blocklist: word-boundary match on job title line only (not full JD).
- Years gate: regex on JD required experience vs experience_range.max.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

_YEARS_PATTERNS = [
    re.compile(
        r"(?:minimum|min\.?|at least|requires?|requirement[s]?:?)\s*(\d+)\s*\+?\s*(?:years?|yrs?\.?)",
        re.I,
    ),
    re.compile(r"(\d+)\s*\+\s*years?", re.I),
    re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*years?", re.I),
    re.compile(r"(\d+)\s+to\s+(\d+)\s+years?", re.I),
    re.compile(r"(\d+)\s+years?\s+(?:of\s+)?experience", re.I),
    re.compile(r"(\d+)\s+years?\s+of\s+", re.I),
    re.compile(r"(\d+)\s+or\s+more\s+years?", re.I),
]


def extract_job_title_line(jd_text: str) -> str:
    """First line or explicit Title: header from staging CSV imports."""
    if not jd_text:
        return ""
    for line in jd_text.splitlines()[:8]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("title:"):
            return stripped.split(":", 1)[1].strip()
        if stripped.lower().startswith("position:"):
            return stripped.split(":", 1)[1].strip()
        if len(stripped) < 120 and not stripped.lower().startswith(("url:", "http", "about ")):
            return stripped
    return jd_text.splitlines()[0].strip() if jd_text.splitlines() else ""


def title_matches_blocked(title: str, blocked: str) -> bool:
    phrase = blocked.strip()
    if not phrase or not title:
        return False
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return bool(re.search(pattern, title, re.I))


def title_blocked(title: str, blocked_titles: list) -> Optional[str]:
    """Return matched blocklist term or None."""
    if not title:
        return None
    for term in blocked_titles:
        if title_matches_blocked(title, term):
            # Special exception: skip blocking "assistant" if it's part of a product name 
            # (e.g. preceded by virtual, ai, intelligent, digital, voice, chat, smart)
            if term.lower() == "assistant":
                pattern = r"\b(virtual|ai|intelligent|digital|voice|chat|smart)\s+assistant\b"
                all_matches = list(re.finditer(r"\bassistant\b", title, re.I))
                product_matches = list(re.finditer(pattern, title, re.I))
                if all_matches and len(all_matches) == len(product_matches):
                    continue
            return term
    return None


def parse_max_years_required(jd_text: str) -> Optional[int]:
    """Highest years figure implied as required in JD (conservative for ranges)."""
    if not jd_text:
        return None
    found: list[int] = []
    for pat in _YEARS_PATTERNS:
        for m in pat.finditer(jd_text):
            groups = [g for g in m.groups() if g is not None]
            if not groups:
                continue
            nums = [int(g) for g in groups]
            if len(nums) == 1:
                found.append(nums[0])
            else:
                found.append(max(nums))
    return max(found) if found else None


def check_years_gate(jd_text: str, prefs: dict) -> Tuple[bool, str]:
    """
    Returns (passes, reason). Fails closed when JD requires more than max years.
    """
    exp = (prefs or {}).get("experience_range") or {}
    max_years = exp.get("max")
    if max_years is None:
        return True, ""
    required = parse_max_years_required(jd_text)
    if required is None:
        return True, ""
    if required > int(max_years):
        return False, f"required_years_{required}_exceeds_max_{max_years}"
    return True, ""


def passes_title_gate(jd_text: str, prefs: dict) -> Tuple[bool, str]:
    blocked = (prefs or {}).get("blocked_titles") or []
    title = extract_job_title_line(jd_text)
    hit = title_blocked(title, blocked)
    if hit:
        return False, f"title_blocked:{hit}"
    return True, ""
