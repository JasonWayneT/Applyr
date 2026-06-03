"""
JD-theme primary claims — force high-signal ACC IDs into resume selection.
Implements FR-193 (CR-040).
When a theme is active in the JD profile, the best matching catalog claim is
prepended so composed bullets (and cover numeric audit) share the same metrics.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence

from jd_tailoring import JdProfile, THEME_KEYWORDS

# Theme key -> ordered claim IDs (first present in catalog wins)
THEME_PRIMARY_CLAIM_IDS: Dict[str, List[str]] = {
    "security": ["ACC-103-ROADMAP", "ACC-103-SEC", "ACC-103-PM"],
    "platform": ["ACC-101-TECH", "ACC-101-PM", "ACC-102-TECH"],
    "data": ["ACC-105-PROCESS", "ACC-105-EXECUTION"],
    "roadmap": ["ACC-103-ROADMAP", "ACC-101-PM"],
    "migration": ["ACC-104-OPS", "ACC-104-CS"],
}

_THEME_KEY_FROM_PHRASE = {phrase: kw for kw, phrase in THEME_KEYWORDS}


def _theme_keys_from_profile(profile: JdProfile) -> List[str]:
    keys: List[str] = []
    for theme in profile.priority_themes:
        key = _THEME_KEY_FROM_PHRASE.get(theme)
        if key and key not in keys:
            keys.append(key)
    return keys


def active_theme_keys(jd_text: str, profile: JdProfile) -> List[str]:
    """Themes that warrant primary claim injection."""
    jd_l = jd_text.lower()
    keys = _theme_keys_from_profile(profile)
    for kw, _phrase in THEME_KEYWORDS:
        if kw in jd_l and kw not in keys:
            keys.append(kw)
    return keys


def resolve_primary_claim_id(
    theme_key: str, valid_ids: Dict[str, str]
) -> Optional[str]:
    for cid in THEME_PRIMARY_CLAIM_IDS.get(theme_key, []):
        if cid in valid_ids:
            return cid
    return None


def primary_claim_ids_for_jd(
    jd_text: str,
    profile: JdProfile,
    valid_ids: Dict[str, str],
) -> List[str]:
    out: List[str] = []
    for key in active_theme_keys(jd_text, profile):
        cid = resolve_primary_claim_id(key, valid_ids)
        if cid and cid not in out:
            out.append(cid)
    return out


def inject_theme_primaries(
    selected: Sequence[str],
    valid_ids: Dict[str, str],
    jd_text: str,
    profile: JdProfile,
    quotas: Optional[Dict[str, int]] = None,
) -> List[str]:
    """
    Prepend theme primaries; if employer quota is full, drop lowest-priority
    same-employer claim that is not itself a primary.
    """
    from local_draft_stages import employer_for_claim_id, resume_bullet_quotas

    quotas = quotas or resume_bullet_quotas()
    primaries = primary_claim_ids_for_jd(jd_text, profile, valid_ids)
    if not primaries:
        return list(selected)

    out = list(dict.fromkeys(list(primaries) + list(selected)))

    for primary in primaries:
        employer = employer_for_claim_id(primary)
        cap = quotas.get(employer, 3)
        same_emp = [c for c in out if employer_for_claim_id(c) == employer]
        if len(same_emp) <= cap:
            continue
        drop: Optional[str] = None
        for c in reversed(out):
            if c == primary or c in primaries:
                continue
            if employer_for_claim_id(c) == employer:
                drop = c
                break
        if drop:
            out = [c for c in out if c != drop]

    return out
