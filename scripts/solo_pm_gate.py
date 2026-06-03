"""
Deterministic solo-PM trap gate (CR-036 / FR-189).

Rejects JDs where the candidate would be the only / founding / first PM.
Does NOT reject squad PM roles, structured product orgs, or informal PM mentorship.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

# Phrases suggesting sole/founding PM ownership (body text, case-insensitive substring).
DEFAULT_SOLO_SIGNALS: List[str] = [
    "only product manager",
    "sole product manager",
    "sole product person",
    "single product manager",
    "only product person",
    "only pm on the team",
    "only pm on the product team",
    "first product hire",
    "first product manager",
    "first pm hire",
    "our first pm",
    "founding product manager",
    "founding pm",
    "build the product function",
    "establish the product team",
    "establish the pm team",
    "create the product team",
    "you will be the product manager for the entire",
    "only product professional",
    "single product professional",
]

# Signals that the role sits inside a structured product org (allowlist).
DEFAULT_TEAM_STRUCTURE_SIGNALS: List[str] = [
    "product organization",
    "product organisation",
    "product org",
    "reports to director of product",
    "reports to head of product",
    "reports to vp of product",
    "director of product",
    "head of product",
    "vp of product",
    "peer pm",
    "peer product manager",
    "other product managers",
    "other pms",
    "squad",
    "portfolio of products",
    "product managers on the team",
    "l1/l2",
    "l1 pm",
    "l2 pm",
    "guide junior",
    "informal mentorship",
    "mentorship",
    "mentor",
    "pairing with",
    "cross-functional",
    "product organization by guiding",
]

# Weak substring — ignore when part of solo-trap phrasing ("establish the product team").
_WEAK_TEAM_PHRASES = frozenset({"product team", "product org"})

_SOLO_TRAP_CONTEXT = re.compile(
    r"\b(?:establish|build|create|first|founding|only|sole|single)\b.{0,40}\b(?:product team|pm team)\b",
    re.I,
)

# Mentorship language — never treat as solo trap when present without strong solo signal.
MENTORSHIP_SIGNALS: List[str] = [
    "mentor",
    "mentorship",
    "guide l1",
    "guide l2",
    "l1/l2 pm",
    "junior pm",
    "informal mentorship",
    "pairing",
]


def _pref_enabled(prefs: dict) -> bool:
    p = (prefs or {}).get("preferences") or {}
    if "avoid_solo_pm_trap" in p:
        return bool(p.get("avoid_solo_pm_trap"))
    # Legacy: structured_team_required implies avoiding solo traps.
    return bool(p.get("structured_team_required", True))


def _solo_phrases(prefs: dict) -> List[str]:
    custom = (prefs or {}).get("solo_pm_blocklist_phrases")
    if isinstance(custom, list) and custom:
        return [str(x).strip().lower() for x in custom if str(x).strip()]
    return [p.lower() for p in DEFAULT_SOLO_SIGNALS]


def _team_phrases(prefs: dict) -> List[str]:
    custom = (prefs or {}).get("team_structure_signals")
    if isinstance(custom, list) and custom:
        return [str(x).strip().lower() for x in custom if str(x).strip()]
    return [p.lower() for p in DEFAULT_TEAM_STRUCTURE_SIGNALS]


def _text_lower(jd_text: str) -> str:
    return re.sub(r"\s+", " ", (jd_text or "").lower()).strip()


def find_solo_signal(jd_text: str, prefs: dict | None = None) -> Optional[str]:
    text = _text_lower(jd_text)
    if not text:
        return None
    for phrase in _solo_phrases(prefs or {}):
        if phrase in text:
            return phrase
    return None


def has_team_structure_signal(jd_text: str, prefs: dict | None = None) -> bool:
    text = _text_lower(jd_text)
    if not text:
        return False
    if _SOLO_TRAP_CONTEXT.search(text):
        return False
    for phrase in _team_phrases(prefs or {}):
        if phrase not in text:
            continue
        if phrase in _WEAK_TEAM_PHRASES:
            continue
        return True
    return False


def has_mentorship_only_signal(jd_text: str) -> bool:
    text = _text_lower(jd_text)
    return any(m in text for m in MENTORSHIP_SIGNALS)


def check_solo_pm_gate(jd_text: str, prefs: dict | None = None) -> Tuple[bool, str]:
    """
    Returns (passes, reason). passes=True when NOT a solo-PM trap.
    Implements FR-189 (CR-036).
    """
    prefs = prefs or {}
    if not _pref_enabled(prefs):
        return True, ""

    solo = find_solo_signal(jd_text, prefs)
    if not solo:
        return True, ""

    if has_team_structure_signal(jd_text, prefs):
        return True, ""

    # Mentorship without team/org signals still passes — not head-of-function.
    if has_mentorship_only_signal(jd_text) and solo not in (
        "founding product manager",
        "founding pm",
        "first product hire",
        "first product manager",
        "first pm hire",
        "our first pm",
        "only product manager",
        "sole product manager",
    ):
        return True, ""

    return False, f"solo_pm_trap:{solo}"


def team_structure_prompt_note(jd_text: str, prefs: dict | None = None) -> str:
    """Inject when structured product org detected (scoring context)."""
    if not has_team_structure_signal(jd_text, prefs or {}):
        return ""
    return (
        "ORG_STRUCTURE: Structured product team detected (squad/org/peers/manager). "
        "This is NOT a solo-PM trap. Informal mentorship of junior PMs is ALLOWED."
    )
