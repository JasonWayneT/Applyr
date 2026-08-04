#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Calibration harness — CR-053 Epic 4 (offline heuristic scoring)."""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

os.environ["STRUCTURED_FIT"] = "1"

from batch_pipeline import evaluate_job_fit, load_file, load_candidate_preferences
from utils import WORK_EXP_SUMMARY_FILE, WORK_EXP_FILE

DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
FIT_RULES = os.path.join(PROJECT_ROOT, ".agent", "rules", "job_fit_engine.md")


def _load_jd(company: str, jd_text: str | None) -> str:
    if jd_text and len(jd_text.strip()) > 50:
        return jd_text
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run structured fit calibration against job history.")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    if not os.path.isfile(DB):
        print("No jobagent.sqlite — skip calibration")
        return 0

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    prefs = load_candidate_preferences()
    rules = load_file(FIT_RULES) if os.path.isfile(FIT_RULES) else ""

    rows = conn.execute(
        """
        SELECT company, title, score, status, rejection_type, outcome_notes, jd_text
        FROM jobs
        WHERE rejection_type='Self-Rejected' AND score >= 72
        ORDER BY score DESC
        LIMIT ?
        """,
        (args.limit,),
    ).fetchall()

    disagreements = 0
    skipped = 0
    print(f"Calibration: {len(rows)} high-score self-rejects")
    for row in rows:
        jd = _load_jd(row["company"], row["jd_text"])
        if not jd:
            skipped += 1
            continue
        result = evaluate_job_fit(jd, work_exp, rules, prefs)
        new_score = int(result.get("Score", 0))
        old_score = int(row["score"] or 0)
        if new_score >= 72:
            disagreements += 1
            print(
                f"  DISAGREE {row['company']}: old={old_score} new={new_score} "
                f"notes={(row['outcome_notes'] or '')[:60]}"
            )

    print(f"Done: disagreements={disagreements} skipped_no_jd={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
