#!/usr/bin/env python3
"""Golden-set regression checker for the Fit Rubric (data/fit_rubric_spec.html).

CR-093 rewrite: the old version checked only the 16 of 21 entries whose
answer was mechanically derivable from regex (gate class + gap_source),
explicitly skipping the 5 that needed a real 0-4 evidence-level judgment
because that scale wasn't implemented in code yet. It now is
(scripts/evidence_scale.py) -- this checker runs every active entry, live,
through the real classifier.

**This is no longer instant/offline/deterministic** -- that property
belonged to the regex classifier this checks, which CR-093 removed by
design (Jason, 2026-08-19: "regex wasn't working and we have been
bypassing it completely either way"). Every run here is a real LLM call
per entry against local Ollama. Evidence-level agreement is graded +-1
(a judgment call, not a bit-exact fact) and reported per-category, same
"don't hide a category collapse behind a healthy aggregate" principle the
original checker used.

Usage:
    python scripts/check_fit_rubric_golden_set.py
    python scripts/check_fit_rubric_golden_set.py --category domain_gate
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from evidence_scale import EvidenceClassificationError, classify_requirement  # noqa: E402
from utils import WORK_EXP_FILE, load_file  # noqa: E402

_ROOT = os.path.dirname(_SCRIPT_DIR)
_GOLDEN_SET = os.path.join(_ROOT, "data", "fit_rubric_golden_set.json")


def _check_entry(entry: dict, work_exp: str) -> tuple[bool, str]:
    is_required = entry.get("requirement_type") != "Preferred/Bonus"
    try:
        judgment = classify_requirement(
            entry["jd_line"],
            work_exp,
            is_required=is_required,
            company=entry.get("company", ""),
            internal_terms=entry.get("internal_terms"),
        )
    except EvidenceClassificationError as exc:
        return False, f"LLM classification failed: {exc}"

    expected_gate = entry["expected_gate"]
    expected_source = entry.get("expected_gap_source")
    expected_level = entry.get("expected_evidence_level")

    ok = judgment.gate == expected_gate
    parts = [f"gate={judgment.gate} (expected {expected_gate})"]

    if expected_gate == "HARD":
        source_ok = judgment.gap_source == expected_source
        ok = ok and source_ok
        parts.append(f"source={judgment.gap_source} (expected {expected_source})")

    if expected_level is not None:
        exact = judgment.evidence_level == expected_level
        close = abs(judgment.evidence_level - expected_level) <= 1
        ok = ok and close
        tag = "exact" if exact else ("+-1" if close else "MISS")
        parts.append(f"level={judgment.evidence_level} (expected {expected_level}, {tag})")

    return ok, ", ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default=None, help="Only check this category")
    args = parser.parse_args()

    with open(_GOLDEN_SET, encoding="utf-8") as f:
        golden = json.load(f)

    # Full, untruncated text -- classify_requirement() retrieves the
    # relevant excerpt per requirement line internally (CR-093 Epic 2
    # Story 2.1's build_evidence_context()).
    work_exp = load_file(WORK_EXP_FILE) or ""

    entries = [e for e in golden["entries"] if e.get("status") == "active"]
    if args.category:
        entries = [e for e in entries if e["category"] == args.category]

    by_category: dict[str, list[tuple[str, bool, str]]] = defaultdict(list)
    for entry in entries:
        ok, detail = _check_entry(entry, work_exp)
        by_category[entry["category"]].append((entry["id"], ok, detail))

    total = 0
    total_pass = 0
    print("=== Fit Rubric Golden Set — evidence-scale engine (CR-093), live LLM ===\n")
    for cat in sorted(by_category):
        rows = by_category[cat]
        passed = sum(1 for _, ok, _ in rows if ok)
        total += len(rows)
        total_pass += passed
        status = "PASS" if passed == len(rows) else "FAIL"
        print(f"[{status}] {cat}: {passed}/{len(rows)}")
        for entry_id, ok, detail in rows:
            marker = "    " if ok else "FAIL"
            print(f"    {marker} {entry_id}: {detail}")
    print(f"\nTotal: {total_pass}/{total} entries pass.")

    return 0 if total_pass == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
