#!/usr/bin/env python3
"""Stage 1 retrieval-scoped authoring examples (CR-097 Epic 3).

Modeled on fit_rubric_examples.py but not copied. Two deliberate deviations:

1. Scoring uses containment (|query ∩ entry| / |entry|), not Jaccard.
   Stage 1's query is a whole packet. Jaccard's union term makes every score
   collapse toward zero and effectively ranks by entry length instead of
   relevance. Containment asks "how much of this example is actually in the
   current job," which is the right question for a document-level query.

2. Embeddings stay out of v1. The bank starts at zero entries (Epic 4 seeds
   it). fit_rubric_examples.py's own stated threshold is "revisit past ~10-15
   entries per category"; we are nowhere near that.

Import-light and side-effect-free: safe to import from the packet builder.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
_DEFAULT_BANK = os.path.join(_ROOT, "data", "authoring_example_bank.json")

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "for", "to", "with", "on",
    "is", "are", "this", "that", "across",
})
_TOKEN_RE = re.compile(r"[a-z][a-z'-]*")


def _tokenize(text: str) -> set[str]:
    """Lowercased tokens with stopwords and 1-2 char tokens removed."""
    return {
        t for t in _TOKEN_RE.findall((text or "").lower())
        if t not in _STOPWORDS and len(t) > 2
    }


def load_bank(path: str | None = None) -> list[dict]:
    """Return bank entries, or [] when the file is missing — never raise."""
    bank_path = path or _DEFAULT_BANK
    if not os.path.isfile(bank_path):
        return []
    try:
        with open(bank_path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


def bank_version(path: str | None = None) -> str:
    """First 16 hex chars of sha256 of the bank file bytes, or '' if missing."""
    bank_path = path or _DEFAULT_BANK
    if not os.path.isfile(bank_path):
        return ""
    try:
        with open(bank_path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return ""


def _applies(entry: dict, context: dict) -> bool:
    """Return True when the entry's applies_when condition is met."""
    applies = entry.get("applies_when") or {}
    mode = applies.get("mode") or "always"
    if mode == "always":
        return True
    if mode == "packet_condition":
        condition = applies.get("condition")
        if condition == "soft_gaps_present":
            return bool(context.get("soft_gaps"))
        return False
    return False


def _context_text(context: dict) -> str:
    """Flatten jd_buckets + soft_gaps into one query string."""
    parts: list[str] = []
    buckets = context.get("jd_buckets") or {}
    if isinstance(buckets, dict):
        for key in ("required", "preferred", "responsibilities", "culture"):
            for item in buckets.get(key) or []:
                parts.append(str(item))
    for sg in context.get("soft_gaps") or []:
        if isinstance(sg, dict):
            parts.append(str(sg.get("item") or ""))
        else:
            parts.append(str(sg))
    return " ".join(parts)


def _containment(query_tokens: set[str], entry: dict) -> float:
    """|query ∩ entry| / |entry| against match_text. Empty entry → 0.0."""
    entry_tokens = _tokenize(str(entry.get("match_text") or ""))
    if not entry_tokens:
        return 0.0
    return len(query_tokens & entry_tokens) / len(entry_tokens)


def format_learned_examples(examples: list[dict]) -> str:
    """Render selected entries as BEFORE/AFTER/why groups.

    Returns "" when empty so callers can splice unconditionally, matching
    fit_rubric_examples.format_examples_for_prompt.
    """
    if not examples:
        return ""
    lines = [
        "These are real corrected drafts, not new rules. Apply the same "
        "correction when the current job is shaped like the BEFORE line."
    ]
    for entry in examples:
        lines.append(f"[{entry.get('category') or 'example'}]")
        lines.append(f"BEFORE: {entry.get('before') or ''}")
        lines.append(f"AFTER: {entry.get('after') or ''}")
        lines.append(f"why: {entry.get('why') or ''}")
    return "\n".join(lines)


def select_examples(
    context: dict,
    k: int = 3,
    max_chars: int = 1800,
    entries: list[dict] | None = None,
) -> list[dict]:
    """Pick at most one active, eligible example per category, capped by k/chars.

    Primary selector is condition-gating plus per-category slot caps.
    Containment against match_text is an intra-category tiebreak only,
    then added_date descending.
    """
    pool = entries if entries is not None else load_bank()
    eligible = [
        e
        for e in pool
        if e.get("status") == "active"
        and e.get("few_shot_eligible")
        and _applies(e, context)
    ]
    query_tokens = _tokenize(_context_text(context))

    by_category: dict[str, list[dict]] = {}
    for entry in eligible:
        cat = str(entry.get("category") or "")
        by_category.setdefault(cat, []).append(entry)

    best: list[dict] = []
    for cat, group in by_category.items():
        group.sort(
            key=lambda e: (
                _containment(query_tokens, e),
                str(e.get("added_date") or ""),
            ),
            reverse=True,
        )
        best.append(group[0])

    selected: list[dict] = []
    for entry in best:
        if len(selected) >= k:
            break
        trial = selected + [entry]
        rendered = format_learned_examples(trial)
        if selected and len(rendered) > max_chars:
            break
        if not selected and len(rendered) > max_chars:
            continue
        selected.append(entry)
    return selected
