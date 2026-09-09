"""
CR-110 Gap B: JD content validation at Stage 0.

The pipeline has no content validation between DB insert and Stage 0 — the only
check is MIN_JD_CHARS = 200 (a character count). This module provides two
deterministic checks that run as part of the preference gate:

1. Bracket-placeholder detection: catches JDs with unfilled template fields
   like [Company X], [Your Company], [phone], [email].
2. Network-page detection: catches talent-matching pages that are not
   single-employer job postings ("apply once and get matched", "talent network").

Both produce hard rejects (Skip), not soft flags — a JD with template placeholders
or a network page should not enter the authoring pipeline.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Bracket-placeholder detection
# ---------------------------------------------------------------------------

# Matches [Company X], [Your Company], [Company Name], [Target Company], etc.
_BRACKET_COMPANY_RE = re.compile(
    r"\[(?:Company|Your Company|Target Company|Company Name)\s*[A-Z]?\]",
    re.I,
)

# Matches [phone], [email], [LinkedIn], [URL], [link], etc. in JD body
# (not just headers — these can appear anywhere in a template JD)
_BRACKET_CONTACT_RE = re.compile(
    r"\[(?:phone|email|e-mail|linkedin|url|link|website|address)\]",
    re.I,
)

# Matches [Your ...], [Insert ...], [Placeholder ...] — generic template markers
_BRACKET_TEMPLATE_RE = re.compile(
    r"\[(?:Your|Insert|Placeholder|Example|Sample)\s+\w+\]",
    re.I,
)


def check_jd_placeholders(jd_text: str) -> list[dict]:
    """Return reject dicts if the JD contains bracket placeholders.

    Args:
        jd_text: Raw JD text.

    Returns:
        List of reject dicts with code 'jd_placeholder' and the matched pattern.
    """
    if not jd_text:
        return []

    rejects: list[dict] = []
    matches: list[str] = []

    for pat in (_BRACKET_COMPANY_RE, _BRACKET_CONTACT_RE, _BRACKET_TEMPLATE_RE):
        for m in pat.finditer(jd_text):
            matches.append(m.group(0))

    if matches:
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                unique.append(m)
        rejects.append({
            "code": "jd_placeholder",
            "reason": f"JD contains template placeholders: {', '.join(unique[:5])}",
        })

    return rejects


# ---------------------------------------------------------------------------
# Network-page detection
# ---------------------------------------------------------------------------

# Phrases that indicate a talent-matching network page, not a single-employer posting.
_NETWORK_PAGE_PHRASES = [
    "apply once and get matched",
    "apply once and let employers",
    "join our talent network",
    "join our talent pool",
    "talent network",
    "talent marketplace",
    "get matched with employers",
    "get matched with companies",
    "one application, multiple employers",
    "one application, multiple companies",
]

_NETWORK_PAGE_RE = re.compile(
    r"|".join(re.escape(p) for p in _NETWORK_PAGE_PHRASES),
    re.I,
)


def check_network_page(jd_text: str) -> list[dict]:
    """Return reject dicts if the JD is a talent-matching network page.

    Args:
        jd_text: Raw JD text.

    Returns:
        List of reject dicts with code 'network_page' and the matched phrase.
    """
    if not jd_text:
        return []

    m = _NETWORK_PAGE_RE.search(jd_text)
    if m:
        return [{
            "code": "network_page",
            "reason": f"JD appears to be a talent-matching network page: '{m.group(0)}'",
        }]

    return []
