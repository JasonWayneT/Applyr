#!/usr/bin/env python3
"""Tests for prefs_rollout.merge_gate_prefs."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prefs_rollout import merge_gate_prefs


def main() -> int:
    example = {
        "blocked_role_titles": ["Director"],
        "blocked_focus_area_words": ["Growth"],
        "blocked_companies": ["Unity"],
        "min_confidence_score": 55,
    }
    live = {"blocked_titles": ["Lead"], "blocked_companies": ["Acme"]}
    merged, changes = merge_gate_prefs(live, example)
    failed = 0
    if "blocked_role_titles" not in merged:
        print("  [FAIL] missing blocked_role_titles")
        failed += 1
    if "Unity" not in merged.get("blocked_companies", []):
        print("  [FAIL] Unity not union-merged")
        failed += 1
    if "Acme" not in merged.get("blocked_companies", []):
        print("  [FAIL] existing Acme removed")
        failed += 1
    if not changes:
        print("  [FAIL] expected change lines")
        failed += 1
    if failed == 0:
        print("  [PASS] merge_gate_prefs")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
