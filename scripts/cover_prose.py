"""Prose helpers for resumes and cover letters — avoid chained 'and' from JD theme labels."""
from __future__ import annotations

from typing import List


def _short_theme_label(theme: str) -> str:
    """Use the leading phrase before an internal ' and ' when themes are compound."""
    t = theme.strip()
    if " and " in t:
        return t.split(" and ", 1)[0].strip()
    return t


def format_themes_for_prose(themes: List[str], max_items: int = 2) -> str:
    """
    Join JD themes for a sentence without 'X and Y and Z' from nested theme strings.
    Example: ['platform reliability and scale', 'data integrity and ingestion']
      -> 'platform reliability and data integrity'
    """
    labels = [_short_theme_label(t) for t in themes[:max_items] if t and t.strip()]
    if not labels:
        return "platform delivery and data integrity"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{labels[0]}, {labels[1]}, and {labels[2]}"


def posting_focus_phrase(jd_text: str) -> str:
    """Short phrase for 'focus of your posting' without repeating theme strings."""
    jd_l = jd_text.lower()
    parts: List[str] = []
    if "platform" in jd_l or "intelligence" in jd_l:
        parts.append("platform scale")
    if "data" in jd_l or "ranking" in jd_l:
        parts.append("structured data")
    if "monetiz" in jd_l or "revenue" in jd_l:
        parts.append("commercial outcomes")
    if "engineering" in jd_l or "cross-functional" in jd_l:
        parts.append("cross-functional execution")
    if not parts:
        return "platform, data, and execution"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"
