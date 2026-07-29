"""
Internal codename (VOC) → plain-language replacements for employer-facing text.

Must stay aligned with LR-011 in submission_linter.py and AGENTS.md VOC table.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# Longest phrases first so shorter keys do not steal partial matches.
VOC_REPLACEMENTS: List[Tuple[str, str]] = [
    ("Platform Data Remediation", "centralized platform data remediation initiative"),
    (
        "Core B2B SaaS Platform",
        "customer-facing B2B SaaS media monitoring and contact database platform",
    ),
    ("Centralized Contact Database", "centralized contact source-of-truth database"),
    ("Critical Save Program", "high-risk account retention program"),
    ("White Glove Accounts", "premium high-revenue enterprise clients"),
    ("Airo", "a macOS security product"),
]


def voc_codename_pattern() -> re.Pattern[str]:
    alts = "|".join(re.escape(codename) for codename, _ in VOC_REPLACEMENTS)
    return re.compile(rf"\b({alts})\b", re.IGNORECASE)


def contains_voc_codename(text: str) -> bool:
    return bool(voc_codename_pattern().search(text or ""))


def find_voc_codenames(text: str) -> List[str]:
    return [m.group(0) for m in voc_codename_pattern().finditer(text or "")]


def apply_voc_replacements(text: str) -> str:
    out = text or ""
    for codename, replacement in VOC_REPLACEMENTS:
        out = re.sub(
            rf"\b{re.escape(codename)}\b",
            replacement,
            out,
            flags=re.IGNORECASE,
        )
    return out
