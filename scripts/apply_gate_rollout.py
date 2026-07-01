#!/usr/bin/env python3
"""
One-shot CR-053/054/055 post-deploy rollout.

1. Merge gate keys into data/candidate_preferences.json (from example template)
2. Re-run location gate on Backlog/New jobs (dry-run unless --apply)

Usage:
  python scripts/apply_gate_rollout.py           # prefs merge + location dry-run
  python scripts/apply_gate_rollout.py --apply  # prefs merge + location apply
  python scripts/apply_gate_rollout.py --prefs-only
  python scripts/apply_gate_rollout.py --location-only
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from prefs_rollout import apply_prefs_rollout
from zero_shot_classifier import classify_onsite

DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")


def run_location_rescore(*, apply: bool) -> tuple[int, int]:
    """Return (checked, rejected)."""
    if not os.path.isfile(DB):
        print("  [SKIP] no jobagent.sqlite")
        return 0, 0

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, title, jd_text, status FROM jobs "
        "WHERE status IN ('Backlog', 'New') AND jd_text IS NOT NULL AND length(jd_text) > 50"
    ).fetchall()

    rejected = 0
    for row in rows:
        reject, reason = classify_onsite(row["jd_text"])
        if not reject:
            continue
        rejected += 1
        prefix = "" if apply else "[dry-run] "
        print(f"  {prefix}REJECT {row['company']} | {row['title'][:50]} | {reason[:80]}")
        if apply:
            conn.execute(
                "UPDATE jobs SET status='Rejected', rejection_type='Unfit', "
                "outcome_notes=? WHERE id=?",
                (f"location_gate_rescore: {reason[:200]}", row["id"]),
            )
    if apply:
        conn.commit()
    conn.close()
    return len(rows), rejected


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply CR-053/054/055 gate rollout.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write prefs and apply location rejects (default: prefs write + location dry-run)",
    )
    parser.add_argument("--prefs-only", action="store_true")
    parser.add_argument("--location-only", action="store_true")
    parser.add_argument(
        "--dry-run-prefs",
        action="store_true",
        help="Show prefs merge plan without writing candidate_preferences.json",
    )
    args = parser.parse_args()

    do_prefs = not args.location_only
    do_location = not args.prefs_only

    print("=== Gate rollout (CR-053/054/055) ===")

    if do_prefs:
        print("\n--- Step 1: candidate_preferences.json ---")
        changed, lines = apply_prefs_rollout(write=not args.dry_run_prefs)
        for line in lines:
            print(f"  {line}")
        if not changed and not args.dry_run_prefs:
            print("  (no prefs changes needed)")

    if do_location:
        print("\n--- Step 2: location gate rescore (Backlog/New) ---")
        checked, rejected = run_location_rescore(apply=args.apply)
        mode = "APPLIED" if args.apply else "dry-run"
        print(f"  Summary: checked={checked} location_rejects={rejected} mode={mode}")

    if not args.apply and do_location:
        print("\nRe-run with --apply to persist location rejects.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
