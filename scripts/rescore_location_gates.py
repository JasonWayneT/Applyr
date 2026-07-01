#!/usr/bin/env python3
"""Re-apply location gate to Backlog/New jobs after classifier fixes (CR-053 Epic 1.4)."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from zero_shot_classifier import classify_onsite

DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

    if not os.path.isfile(DB):
        print("No database found.")
        return 0

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, title, jd_text, status FROM jobs "
        "WHERE status IN ('Backlog', 'New') AND jd_text IS NOT NULL AND length(jd_text) > 50"
    ).fetchall()

    rejected = 0
    for row in rows:
        reject, reason = classify_onsite(row["jd_text"])
        if reject:
            rejected += 1
            print(f"{'[dry-run] ' if dry_run else ''}REJECT {row['company']} | {row['title'][:50]} | {reason[:80]}")
            if not dry_run:
                conn.execute(
                    "UPDATE jobs SET status='Rejected', rejection_type='Unfit', "
                    "outcome_notes=? WHERE id=?",
                    (f"location_gate_rescore: {reason[:200]}", row["id"]),
                )
    if not dry_run:
        conn.commit()
    conn.close()
    print(f"Checked {len(rows)} jobs; location rejects={rejected} dry_run={dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
