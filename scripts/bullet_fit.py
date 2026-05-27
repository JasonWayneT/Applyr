"""
Sentence-aware bullet length fitting (CR-018 / FR-105).
"""
from __future__ import annotations

import re

DEFAULT_MAX_BULLET_WORDS = 28

INCOMPLETE_ENDINGS = re.compile(
    r"\b(increasing|reducing|improving|supporting|ensuring|maintaining|"
    r"facilitating|implementing|partnering|building|designing|managing|"
    r"and|with|to|for|by|from|into|across|through)\s*\.\s*$",
    re.IGNORECASE,
)


def _ensure_period(text: str) -> str:
    text = text.strip().rstrip(",;:")
    if text and not text.endswith("."):
        text += "."
    return text


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return parts[0].strip() if parts else text.strip()


def fit_bullet_to_budget(text: str, max_words: int = DEFAULT_MAX_BULLET_WORDS) -> str:
    """
    Fit bullet to word budget without mid-clause truncation.
    """
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return text

    words = text.split()
    if len(words) <= max_words:
        return _ensure_period(text)

    chunk = " ".join(words[:max_words])
    min_keep = max(int(max_words * 0.5), 8)

    for sep in (". ", "; "):
        idx = chunk.rfind(sep)
        if idx >= min_keep:
            return _ensure_period(chunk[: idx + 1].strip())

    idx = chunk.rfind(", ")
    if idx >= min_keep:
        return _ensure_period(chunk[:idx].strip())

    first = first_sentence(text)
    first_words = first.split()
    if len(first_words) <= max_words:
        return _ensure_period(first)

    return _ensure_period(" ".join(first_words[:max_words]))


def is_incomplete_bullet(bullet: str) -> bool:
    """True when bullet likely ends mid-thought."""
    b = bullet.strip()
    if not b:
        return True
    if INCOMPLETE_ENDINGS.search(b):
        return True
    if b.endswith((",", ";", ":")):
        return True
    return False
