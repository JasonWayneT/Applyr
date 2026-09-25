"""
Submission tone guard (FR-096): block layoff / workforce-reduction language on resumes and cover letters.
Prefer constraints framing in rewrites.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Business-relationship nouns that make a preceding "X attrition" churn
# vocabulary, not workforce-reduction language -- the two share this same
# list (previously two independently hand-typed lookbehind chains that could
# silently drift apart). Widened 2026-09-21 (isolved, live false positive):
# "account attrition" -- as ordinary a SaaS churn term as "customer
# attrition" (fixed 2026-09-20 on swoon) -- tripped the same hard block.
# Same whack-a-mole risk as the "epic"/EHR-company fix elsewhere in this
# repo: enumerating individual "safe" nouns will keep missing new ones
# (member, user, tenant, buyer attrition are all equally legitimate and
# equally unlisted before this pass). Kept as an explicit allowlist rather
# than inverted to "block only near workforce words" because the failure
# direction matters here: a missed real layoff reference (false negative)
# violates Jason's explicit hard rule against ever naming layoffs, which is
# worse than an occasional false-positive block needing a one-word rewrite --
# so this stays a conservative, if imperfect, allowlist rather than a laxer
# workforce-context check.
_ATTRITION_SAFE_NOUNS = (
    "customer", "client", "subscriber", "account", "user", "member",
)
_ATTRITION_PATTERN_SRC = (
    "".join(rf"(?<!{noun}\s)" for noun in _ATTRITION_SAFE_NOUNS) + r"\battrition\b"
)

# Longest-first rewrite chains (applied before hard block checks on output).
_TONE_REWRITES: List[Tuple[re.Pattern, str]] = [
    (
        re.compile(r"\bPartnered\s+closely\s+with\b", re.IGNORECASE),
        "Coordinated with",
    ),
    (
        re.compile(
            r"multiple\s+rounds\s+of\s+layoffs?\s+and\s+attrition",
            re.IGNORECASE,
        ),
        "periods of increasing organizational and resource constraints",
    ),
    (
        re.compile(r"layoffs?\s+and\s+attrition", re.IGNORECASE),
        "increasing resource and staffing constraints",
    ),
    (
        re.compile(
            r"through\s+layoffs?\s+and\s+attrition",
            re.IGNORECASE,
        ),
        "through increasing organizational and resource constraints",
    ),
    (re.compile(r"\bworkforce\s+attrition\b", re.IGNORECASE), "staffing constraints"),
    (
        re.compile(_ATTRITION_PATTERN_SRC, re.IGNORECASE),
        "staffing constraints",
    ),
    (re.compile(r"\blayoffs?\b", re.IGNORECASE), "resource constraints"),
    (re.compile(r"\blaid[\s-]off\b", re.IGNORECASE), "resource-constrained"),
    (
        re.compile(r"\breductions?\s+in\s+force\b", re.IGNORECASE),
        "resource constraints",
    ),
    (re.compile(r"\bR\.?I\.?F\.?\b"), "resource constraints"),
]

# Patterns that must not appear in finalized resume / cover letter text.
# NOTE (fixed 2026-07-21): "Partnered closely" was previously hard-blocked here under a
# "Forbidden workforce-reduction language" error message, which is wrong on its face - the
# phrase has no relation to layoffs/attrition/RIF, this file's actual stated purpose (see
# module docstring). It incorrectly hard-failed a real, clean cover letter (Human Interest,
# "partnered closely with engineering"). Removed. If there is a genuine stylistic preference
# against "partnered closely with" as a generic phrase, that belongs in submission_linter.py's
# WARN-level generic-phrase rules (LW-004/LW-006 style), not this file's hard-block list.
_BLOCKED_TONE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\blayoffs?\b", re.IGNORECASE),
    re.compile(r"\blaid[\s-]off\b", re.IGNORECASE),
    # 2026-09-20 (swoon) / 2026-09-21 (isolved): customer/client/subscriber/
    # account/user/member attrition is standard churn vocabulary, unrelated
    # to this file's actual purpose (workforce reduction). See
    # _ATTRITION_PATTERN_SRC above for the shared allowlist and why it stays
    # an allowlist rather than a broader workforce-context check.
    re.compile(_ATTRITION_PATTERN_SRC, re.IGNORECASE),
    re.compile(r"\breductions?\s+in\s+force\b", re.IGNORECASE),
    re.compile(r"\bR\.?I\.?F\.?\b"),
]


def sanitize_submission_tone(text: str) -> str:
    """Rewrite blocked workforce-reduction phrasing to constraints language."""
    if not text:
        return text
    out = text
    for pattern, replacement in _TONE_REWRITES:
        out = pattern.sub(replacement, out)
    return out


def tone_violations(text: str) -> List[str]:
    """Return human-readable snippets for any remaining blocked phrases."""
    if not text:
        return []
    found: List[str] = []
    for pat in _BLOCKED_TONE_PATTERNS:
        for m in pat.finditer(text):
            found.append(m.group(0))
    return found


def assert_submission_tone_clean(text: str) -> Tuple[bool, str | None]:
    violations = tone_violations(text)
    if violations:
        return False, f"Forbidden workforce-reduction language: {', '.join(sorted(set(violations)))}"
    return True, None
