#!/usr/bin/env python3
"""Years boundary tests — CR-110 Round 5: below max is a candidate, max+ is blocked.

Jason targets mid-level only (no senior targeting). With experience_range.max=7,
6 passes and 7 fails — updated from the prior 7-pass/8-fail boundary when
check_years_gate's comparison flipped from `>` to `>=` (2026-09-03).
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seniority_gate import check_years_gate, parse_max_years_required

PREFS = {"experience_range": {"min": 2, "max": 7}}


class TestYearsGateApostropheAndWordNumbers(unittest.TestCase):
    def test_apostrophe_years_experience(self):
        jd = "10 years’ experience as a Product Manager"
        self.assertEqual(parse_max_years_required(jd), 10)

    def test_spelled_out_twelve_years(self):
        jd = "Twelve+ years in product management"
        self.assertEqual(parse_max_years_required(jd), 12)

    def test_years_in_product_management(self):
        jd = "5 years in product management"
        self.assertEqual(parse_max_years_required(jd), 5)


def _assert(name: str, cond: bool, detail: str = "") -> int:
    if cond:
        print(f"  [PASS] {name}")
        return 0
    print(f"  [FAIL] {name} {detail}")
    return 1


def main() -> int:
    print("VERIFY-YEARS: experience_range.max boundary (6 pass, 7 fail)")
    failed = 0

    cases_pass = [
        ("4-6 years of product management experience", 6),
        ("minimum 6 years of experience", 6),
        ("6+ years of PM experience", 6),
        ("3 or more years", 3),
    ]
    cases_fail = [
        ("7 years of product management experience", 7),
        ("minimum 7 years required", 7),
        ("8 years of product management experience", 8),
        ("minimum 8 years required", 8),
        ("10+ years of experience", 10),
        ("requires 8-12 years", 12),
    ]

    for jd, expected in cases_pass:
        parsed = parse_max_years_required(jd)
        ok, _ = check_years_gate(jd, PREFS)
        failed += _assert(
            f"pass: {jd[:40]!r}…",
            ok and parsed == expected,
            f"parsed={parsed} ok={ok}",
        )

    for jd, expected in cases_fail:
        parsed = parse_max_years_required(jd)
        ok, reason = check_years_gate(jd, PREFS)
        failed += _assert(
            f"reject: {jd[:40]!r}…",
            (not ok) and parsed == expected and "exceeds_max" in reason,
            f"parsed={parsed} ok={ok} reason={reason}",
        )

    # Boundary: below max (6) passes, max (7) and above fails
    ok6, _ = check_years_gate("6 years of experience required", PREFS)
    ok7, reason7 = check_years_gate("7 years of experience required", PREFS)
    failed += _assert("boundary 6 passes", ok6)
    failed += _assert("boundary 7 fails", not ok7 and "7" in reason7)

    # CR-055: incidental years in prose must not gate-kill
    jackson = (
        "The Jackson Laboratory celebrates 90 years of genetics research. "
        "Requirements: 5+ years of product management experience."
    )
    parsed_j = parse_max_years_required(jackson)
    ok_j, _ = check_years_gate(jackson, PREFS)
    failed += _assert(
        "jackson lab ignores 90-year history",
        parsed_j == 5 and ok_j,
        f"parsed={parsed_j} ok={ok_j}",
    )

    civica = (
        "Founded 21 years ago. Qualifications: minimum 4 years of PM experience."
    )
    parsed_c = parse_max_years_required(civica)
    failed += _assert(
        "civica ignores founded-years prose",
        parsed_c == 4,
        f"parsed={parsed_c}",
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
