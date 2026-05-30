"""
Deterministic required-anchors gate (CR-028 / FR-172).

Optional via ANCHOR_GATE_ENABLED=1. Requires >=2 anchor phrase hits in JD text.
"""
from __future__ import annotations

from typing import List, Optional, Tuple


def count_anchor_hits(jd_text: str, anchors: List[str]) -> Tuple[int, List[str]]:
    if not jd_text or not anchors:
        return 0, []
    lower = jd_text.lower()
    matched: List[str] = []
    for raw in anchors:
        phrase = (raw or "").strip().lower()
        if len(phrase) < 3:
            continue
        if phrase in lower and phrase not in matched:
            matched.append(phrase)
    return len(matched), matched


def check_anchor_gate(jd_text: str, prefs: dict) -> Tuple[bool, str]:
    """Returns (passes, reason)."""
    try:
        from pipeline_env import anchor_gate_enabled
    except ImportError:
        def anchor_gate_enabled() -> bool:
            return False

    if not anchor_gate_enabled():
        return True, ""

    anchors = (prefs or {}).get("required_anchors") or []
    if not isinstance(anchors, list) or not anchors:
        return True, ""

    hits, _ = count_anchor_hits(jd_text, anchors)
    if hits < 2:
        return False, f"anchor_hits_{hits}"
    return True, ""
