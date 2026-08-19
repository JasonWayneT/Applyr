#!/usr/bin/env python3
"""Golden-set regression checker for the Fit Rubric (data/fit_rubric_spec.html).

Layer 3 of the self-healing plan agreed 2026-08-19: every confirmed real miss
in Stage 0's gap classification becomes a locked-in entry in
data/fit_rubric_golden_set.json, and this script checks the CURRENT code
against every entry, every time the gate logic changes -- not just against
whichever one JD prompted the fix. Catches regressions on past-confirmed
cases the way scripts/test_stage0_extraction_corpus.py already does for
section extraction.

Per golden-dataset best practice (see the rubric spec's evidence ledger):
report pass/fail PER CATEGORY, not one aggregate number -- a healthy overall
score can hide a total collapse in one category (e.g. every domain-gate case
failing while tool/degree cases still pass).

Only checks what current code can mechanically verify: gate class and
gap_source, via the same functions build_stage0_fit_gate.py's classifier
uses directly (no LLM call, no live JD file needed -- these are single-line
checks against the real verbatim JD lines already captured in the golden
set). Entries whose expected_evidence_level is the only assertion (the
clean_evidence_match / preferred_nongate / hedge_nongate categories) are
skipped with a clear note: the graded 0-4 evidence scale from the rubric
spec is not implemented in code yet, only designed. Re-run this after that
lands to get full coverage.

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

from build_stage0_fit_gate import (  # noqa: E402
    _is_unbridgeable_advanced_degree,
    _unbridgeable_domain_requirement,
    _get_hard_tool_pattern,
    _is_soft_familiarity_hedge,
    _alt_list_anchor,
    _load_anchor_vocab,
    _determine_tier,
    _classify_single_clause,
)

_ROOT = os.path.dirname(_SCRIPT_DIR)
_GOLDEN_SET = os.path.join(_ROOT, "data", "fit_rubric_golden_set.json")

# Categories this script can mechanically check today (gate-level only).
_GATE_CHECKABLE = {"domain_gate", "degree_gate", "tool_nongate", "internal_term"}


def _classify_gate(jd_line: str, vocab: set[str]) -> tuple[str, str | None]:
    """Mirrors _classify_one_item's gate dispatch order for a single
    required-bucket line, without needing the full packet/company context
    the real function takes -- sufficient for the gate-only checks this
    script covers."""
    item_lower = jd_line.lower()

    if _is_unbridgeable_advanced_degree(item_lower):
        return "HARD", "degree"

    domain_match = _unbridgeable_domain_requirement(item_lower, vocab)
    if domain_match:
        return "HARD", "domain"

    hard_match = _get_hard_tool_pattern().search(item_lower)
    if hard_match:
        if _alt_list_anchor(item_lower):
            return "NONE", None  # or-similar list satisfied by a real anchored alternative
        if _is_soft_familiarity_hedge(item_lower):
            return "NONE", None  # plain familiarity/exposure hedge -> SOFT, not this script's concern
        return "HARD", "tool"

    return "NONE", None


def _forces_skip(gap_class: str, gap_source: str | None) -> bool:
    """Whether a single flagged HARD gap of this gap_source would, on its
    own, make _determine_tier() return Skip -- mirrors that function's own
    degree/domain absolute-Skip set (see build_stage0_fit_gate.py)."""
    if gap_class != "HARD":
        return False
    flagged = [{"item": "x", "gap_class": "HARD", "gap_source": gap_source}]
    tier, decision = _determine_tier(
        {"passed": True}, flagged, "clear", thin_incomplete=False, required_empty=False
    )
    return decision == "SKIP"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default=None, help="Only check this category")
    args = parser.parse_args()

    with open(_GOLDEN_SET, encoding="utf-8") as f:
        golden = json.load(f)

    vocab = _load_anchor_vocab()
    entries = [e for e in golden["entries"] if e.get("status") == "active"]
    if args.category:
        entries = [e for e in entries if e["category"] == args.category]

    by_category: dict[str, list[tuple[str, bool, str]]] = defaultdict(list)
    skipped = 0

    for entry in entries:
        cat = entry["category"]
        if cat not in _GATE_CHECKABLE:
            skipped += 1
            continue

        if cat == "internal_term":
            # This does NOT reach a HARD tool pattern at all (confirmed live:
            # neither "Empower"/"Exchange" nor "Clerkie" match the deny-list),
            # so _classify_gate would pass this vacuously without ever
            # exercising the exclusion it's meant to test. Call
            # _classify_single_clause directly with the real company/
            # internal_terms context instead, and check the SOFT
            # "unconfirmed tool" path it actually protects.
            # Pass original casing, not .lower() -- _looks_like_named_tool()
            # relies on capitalization to spot proper-noun candidates in the
            # first place (build_stage0_fit_gate.py lowercases internally
            # only for its own anchor-matching, never for tool detection).
            # Lowercasing here first made this check vacuously pass: with no
            # capitalized "Empower"/"Exchange" surviving, no tool candidate
            # was ever extracted at all, so the check passed whether or not
            # the internal_terms exclusion actually worked. Confirmed live:
            # with original casing and internal_terms=[], this line DOES
            # produce "unconfirmed tool(s): Empower, Exchange" -- the real
            # bug this entry is supposed to catch, invisible until casing
            # was fixed.
            result = _classify_single_clause(
                entry["jd_line"],
                vocab,
                company=entry.get("company", ""),
                internal_terms=entry.get("internal_terms"),
            )
            has_unconfirmed_tool = "unconfirmed tool" in (result.get("anchor") or "")
            ok = has_unconfirmed_tool != entry.get("expected_no_unconfirmed_tool", True)
            detail = f"anchor={result.get('anchor')!r}"
            by_category[cat].append((entry["id"], ok, detail))
            continue

        got_gate, got_source = _classify_gate(entry["jd_line"], vocab)
        expected_gate = entry["expected_gate"]
        expected_source = entry.get("expected_gap_source")

        ok = got_gate == expected_gate and (
            expected_gate != "HARD" or got_source == expected_source
        )
        detail = f"got gate={got_gate!r} source={got_source!r}"

        if ok and "expected_forces_skip" in entry:
            got_forces_skip = _forces_skip(got_gate, got_source)
            if got_forces_skip != entry["expected_forces_skip"]:
                ok = False
                detail += f"; forces_skip={got_forces_skip} expected {entry['expected_forces_skip']}"

        by_category[cat].append((entry["id"], ok, detail))

    total = 0
    total_pass = 0
    print("=== Fit Rubric Golden Set — gate-level check ===\n")
    for cat in sorted(by_category):
        rows = by_category[cat]
        passed = sum(1 for _, ok, _ in rows if ok)
        total += len(rows)
        total_pass += passed
        status = "PASS" if passed == len(rows) else "FAIL"
        print(f"[{status}] {cat}: {passed}/{len(rows)}")
        for entry_id, ok, detail in rows:
            if not ok:
                print(f"    FAIL {entry_id}: {detail}")
    print(f"\nTotal: {total_pass}/{total} gate-checkable entries pass.")
    if skipped:
        print(
            f"{skipped} entries skipped (evidence-level categories — the 0-4 "
            "evidence scale from the rubric spec isn't implemented in code "
            "yet, only designed. Re-run after it lands)."
        )

    return 0 if total_pass == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
