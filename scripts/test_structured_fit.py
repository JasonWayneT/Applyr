#!/usr/bin/env python3
"""Structured fit scoring unit tests — CR-053 Epic 2 (no LLM)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from structured_fit import (
    compute_fit_report,
    extract_must_haves,
    _heuristic_judgments,
)

JD_STRONG = """
Title: Product Manager
Requirements:
- 5+ years product management experience
- B2B SaaS platform roadmap ownership
- Cross-functional agile delivery with engineering
Remote US. Must have stakeholder management.
"""

JD_IAM = """
Title: Product Manager
Required: IAM/RBAC experience mandatory.
5+ years PM experience. B2B SaaS platform.
"""

WORK_EXP = """
Product Manager with B2B SaaS platform, roadmap, cross-functional agile delivery.
"""


def _assert(name: str, cond: bool, detail: str = "") -> int:
    if cond:
        print(f"  [PASS] {name}")
        return 0
    print(f"  [FAIL] {name} {detail}")
    return 1


def main() -> int:
    print("VERIFY-STRUCTURED-FIT: deterministic path (CR-053 Epic 2)")
    failed = 0

    must = extract_must_haves(JD_STRONG)
    failed += _assert("extracts must-haves", len(must) >= 1, str(must))

    judgments = _heuristic_judgments(JD_STRONG, WORK_EXP, must)
    report = compute_fit_report(JD_STRONG, WORK_EXP, judgments, {}, 72)
    failed += _assert("strong JD scores >= 72", report.fit_score >= 72, str(report.fit_score))
    failed += _assert("strong JD decision YES or REVIEW", report.decision in ("YES", "REVIEW"))

    iam_judgments = _heuristic_judgments(JD_IAM, WORK_EXP, extract_must_haves(JD_IAM))
    iam_report = compute_fit_report(JD_IAM, WORK_EXP, iam_judgments, {}, 72)
    failed += _assert(
        "IAM required domain lowers vs strong",
        iam_report.fit_score <= report.fit_score,
        f"iam={iam_report.fit_score} strong={report.fit_score}",
    )
    failed += _assert(
        "optional domain note skipped",
        "required_domain_gap" not in " ".join(
            compute_fit_report(
                "Healthcare experience is a nice plus. B2B SaaS PM role.",
                WORK_EXP,
                _heuristic_judgments("nice plus healthcare", WORK_EXP, []),
                {},
                72,
            ).risks
        ),
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
