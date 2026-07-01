#!/usr/bin/env python3
"""Years boundary tests — FR-109 / CR-036 AC-119: 7 pass, 8 fail."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seniority_gate import check_years_gate, parse_max_years_required

PREFS = {"experience_range": {"min": 2, "max": 7}}


def _assert(name: str, cond: bool, detail: str = "") -> int:
    if cond:
        print(f"  [PASS] {name}")
        return 0
    print(f"  [FAIL] {name} {detail}")
    return 1


def main() -> int:
    print("VERIFY-YEARS: experience_range.max boundary (7 pass, 8 fail)")
    failed = 0

    cases_pass = [
        ("4-7 years of product management experience", 7),
        ("minimum 7 years of experience", 7),
        ("7+ years of PM experience", 7),
        ("3 or more years", 3),
    ]
    cases_fail = [
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

    # Boundary: exactly 7 passes, 8 fails
    ok7, _ = check_years_gate("7 years of experience required", PREFS)
    ok8, reason8 = check_years_gate("8 years of experience required", PREFS)
    failed += _assert("boundary 7 passes", ok7)
    failed += _assert("boundary 8 fails", not ok8 and "8" in reason8)

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
