#!/usr/bin/env python3
"""Static template lint — CR-054 Epic 4."""
from __future__ import annotations

import os
import re
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from submission_linter import ALL_RULES, lint_document
from summary_builder import _TEMPLATE_CONSUMER, _TEMPLATE_ENTERPRISE, _TEMPLATE_NEUTRAL

# These templates render a standalone summary PARAGRAPH, not a complete resume -- structural
# rules (LR-020/LR-021 requiring all 3 canonical career-history employers, etc.) can never pass
# against a snippet and were never this test's concern; it exists to catch bad PHRASING baked
# into the template source (LR-013 stale years figure, LR-015 colon-elaboration tell, forbidden
# words). Excluding structural-type rule ids here, added after this test was originally written,
# from silently retroactively breaking it on every run regardless of actual template content.
_STRUCTURAL_RULE_IDS = {r.rule_id for r in ALL_RULES if r.check_type == "structural"}

FORBIDDEN = [
    (re.compile(r"—"), "em-dash"),
    (re.compile(r"\bleverage\b", re.I), "leverage"),
    (re.compile(r"\bpassionate\b", re.I), "passionate"),
]

_SAMPLE = {
    # Canonical figure per workExperience.md §1.0 -- was stale "6" here; LR-013 (added after this
    # test was written) now correctly catches a superseded years-of-experience figure anywhere.
    "years": "7",
    "environment_type": "B2B SaaS platforms",
    "company": "Example Co",
    "scope": "platform roadmap",
    "scale": "3,500 accounts",
    "partner_1": "Engineering",
    "partner_2": "Sales",
    "partner_3": "Customer Experience",
    "outcome_1": "eliminated a 40% data drop-off",
    "outcome_2": "resolved 90% of a security backlog",
}


def main() -> int:
    print("VERIFY-TEMPLATE-LINT-SOURCES (CR-054 Epic 4)")
    failed = 0
    templates = [
        ("enterprise", _TEMPLATE_ENTERPRISE.format(**_SAMPLE)),
        ("consumer", _TEMPLATE_CONSUMER.format(**_SAMPLE)),
        ("neutral", _TEMPLATE_NEUTRAL.format(**_SAMPLE)),
    ]
    for name, text in templates:
        for pat, label in FORBIDDEN:
            if pat.search(text):
                print(f"  [FAIL] summary template {name} contains forbidden {label}")
                failed += 1
        r = lint_document(text, filename="resume")
        real_blocks = [b for b in r.blocks if b.rule_id not in _STRUCTURAL_RULE_IDS]
        if real_blocks:
            print(f"  [FAIL] summary template {name}: {[b.rule_id for b in real_blocks]}")
            failed += 1
        else:
            print(f"  [PASS] summary template {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
