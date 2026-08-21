#!/usr/bin/env python3
"""Frozen rule_id → authoring-defect category map (CR-097 Story 1.1).

Single source of truth for the scanner (Epic 2) and the bank validator
(Epic 3). Pure constants and lookups — no I/O, no imports beyond stdlib.

`wrong_job_bleed` is in CATEGORIES from day one so the ledger can group it,
but RULE_CATEGORY has no mapping until Epic 5 registers a lint rule.
"""
from __future__ import annotations

# Implements CR-097 SR-06
CATEGORIES: tuple[str, ...] = (
    "gap_confession",
    "forbidden_punctuation",
    "wrong_job_bleed",
)

RULE_CATEGORY: dict[str, str] = {
    "LR-016": "gap_confession",
    "LR-006": "forbidden_punctuation",
    "LR-014": "forbidden_punctuation",
    "LR-015": "forbidden_punctuation",
    "LW-032": "wrong_job_bleed",
}


def category_for_rule(rule_id: str) -> str | None:
    """Return the CR-097 category for a lint rule id, or None if unmapped."""
    return RULE_CATEGORY.get(rule_id)


def rule_ids_for_category(category: str) -> list[str]:
    """Return rule ids mapped to *category*, empty if none are registered yet."""
    return sorted(rid for rid, cat in RULE_CATEGORY.items() if cat == category)
