#!/usr/bin/env python3
"""Title blocklist contextual matching — CR-055 Epic 2."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seniority_gate import title_blocked

PREFS = {
    "blocked_role_titles": ["Head", "Lead", "Director", "Staff", "Principal"],
    "blocked_focus_area_words": ["Growth", "Developer", "Designer", "Marketer"],
}


def _assert(name: str, title: str, expect_blocked: bool) -> int:
    hit = title_blocked(title, PREFS)
    ok = (hit is not None) == expect_blocked
    if ok:
        print(f"  [PASS] {name}")
        return 0
    print(f"  [FAIL] {name} title={title!r} hit={hit!r} expect_blocked={expect_blocked}")
    return 1


def main() -> int:
    print("VERIFY-TITLE-BLOCKLIST: contextual focus-area matching (CR-055)")
    failed = 0
    failed += _assert("Head of Growth blocks", "Head of Growth", True)
    failed += _assert("PM Growth passes", "Product Manager, Growth", False)
    failed += _assert("PM Platform Growth passes", "Product Manager, Platform Growth", False)
    failed += _assert(
        "NVIDIA developer productivity passes",
        "Senior Product Manager, AI Platform and Developer Productivity",
        False,
    )
    failed += _assert("Lead PM blocks", "Lead Product Manager", True)
    failed += _assert("leaders lead with passes", "leaders lead with a people-first approach", False)
    failed += _assert("Software Developer blocks", "Senior Software Developer", True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
