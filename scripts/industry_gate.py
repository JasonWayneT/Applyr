"""
Deterministic industry blocklist gate (CR-027 / FR-170).

Matches blocked_industries from candidate_preferences using word boundaries.
Scout scope: company + title (+ optional short snippet).
Batch scope: company + title + JD header (first N chars) — not full JD body.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

# Implements FR-170 — keep in sync with scout_local.ts passesIndustryGate()
HEADER_SCAN_CHARS = 600
SHORT_SNIPPET_CHARS = 120


def term_matches_blocked(text: str, term: str) -> bool:
    phrase = (term or "").strip()
    if not phrase or not text:
        return False
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return bool(re.search(pattern, text, re.I))


def _blocked_list(prefs: dict) -> List[str]:
    raw = (prefs or {}).get("blocked_industries") or []
    if not isinstance(raw, list):
        return []
    return [str(t).strip() for t in raw if str(t).strip()]


def industry_blocked_in_text(text: str, blocked: List[str]) -> Optional[str]:
    if not text or not blocked:
        return None
    for term in blocked:
        if term_matches_blocked(text, term):
            return term
    return None


def scout_industry_blocked(
    company: str,
    title: str,
    description: str = "",
    prefs: Optional[dict] = None,
) -> Tuple[bool, str]:
    """
    Returns (is_blocked, matched_term).
    Scout checks company and title; includes description only when very short (listing snippet).
    """
    blocked = _blocked_list(prefs or {})
    if not blocked:
        return False, ""

    for blob in (company or "", title or ""):
        hit = industry_blocked_in_text(blob, blocked)
        if hit:
            return True, hit

    desc = (description or "").strip()
    if desc and len(desc) <= SHORT_SNIPPET_CHARS:
        hit = industry_blocked_in_text(desc, blocked)
        if hit:
            return True, hit

    return False, ""


def batch_industry_blocked(
    company: str,
    jd_text: str,
    prefs: Optional[dict] = None,
) -> Tuple[bool, str]:
    """
    Returns (is_blocked, matched_term).
    Checks company, job title line, and JD header only (avoids client-industry false positives).
    """
    blocked = _blocked_list(prefs or {})
    if not blocked:
        return False, ""

    hit = industry_blocked_in_text(company or "", blocked)
    if hit:
        return True, hit

    if not jd_text:
        return False, ""

    from seniority_gate import extract_job_title_line

    title_line = extract_job_title_line(jd_text)
    hit = industry_blocked_in_text(title_line, blocked)
    if hit:
        return True, hit

    header = jd_text[:HEADER_SCAN_CHARS]
    hit = industry_blocked_in_text(header, blocked)
    if hit:
        return True, hit

    return False, ""


def check_industry_gate(
    company: str,
    jd_text: str = "",
    title: str = "",
    prefs: Optional[dict] = None,
) -> Tuple[bool, str]:
    """Unified API for batch: (passes, reason). passes=True when NOT blocked."""
    if jd_text:
        blocked, term = batch_industry_blocked(company, jd_text, prefs)
    else:
        blocked, term = scout_industry_blocked(company, title, "", prefs)
    if blocked:
        return False, f"industry_blocked:{term}"
    return True, ""
