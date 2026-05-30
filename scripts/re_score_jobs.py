"""
Re-run fit evaluation on Rejected jobs (CR-019).

Usage:
  python scripts/re_score_jobs.py
  python scripts/re_score_jobs.py --status Rejected --limit 50
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_pipeline import evaluate_job_fit, _load_jd_for_job
from utils import (
    FIT_ENGINE_FILE,
    JOBS_DIR,
    PROJECT_ROOT,
    WORK_EXP_SUMMARY_FILE,
    WORK_EXP_FILE,
    get_min_fit_score,
    load_candidate_preferences,
    load_file,
)

DB = os.path.join(PROJECT_ROOT, "jobagent.sqlite")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", default="Rejected", help="Job status to re-score")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    if not os.path.exists(DB):
        print("No jobagent.sqlite")
        return

    prefs = load_candidate_preferences()
    fit_rules = load_file(FIT_ENGINE_FILE)
    work_exp_summary = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """SELECT id, company, title, url, score FROM jobs
           WHERE status = ? ORDER BY company LIMIT ?""",
        (args.status, args.limit),
    ).fetchall()
    conn.close()

    if not rows:
        print(f"No jobs with status={args.status}")
        return

    print(f"Re-scoring {len(rows)} job(s) (status={args.status})...")
    passed = 0
    for job_id, company, title, url, old_score in rows:
        jd = _load_jd_for_job(company, job_id)
        if not jd or len(jd.strip()) < 100:
            jobs_glob = os.path.join(JOBS_DIR, f"*_{job_id}.txt")
            import glob
            matches = glob.glob(jobs_glob)
            if matches:
                jd = load_file(matches[0])
        if not jd:
            print(f"  [Skip] {company}: no JD text")
            continue

        result = evaluate_job_fit(jd, work_exp_summary, fit_rules, prefs)
        if not result:
            print(f"  [Error] {company}: evaluation failed")
            continue

        score = int(result.get("Score", 0))
        decision = result.get("Decision", "NO")
        summary = result.get("Summary", "")
        print(f"  {company}: {decision} score={score} (was {old_score}) — {summary[:60]}...")

        conn = sqlite3.connect(DB)
        min_score = get_min_fit_score()
        if decision == "YES" and score >= min_score:
            conn.execute(
                "UPDATE jobs SET status = 'New', score = ?, summary = ? WHERE id = ?",
                (score, summary[:500], job_id),
            )
            passed += 1
        else:
            conn.execute(
                "UPDATE jobs SET score = ?, summary = ? WHERE id = ?",
                (score, summary[:500], job_id),
            )
        conn.commit()
        conn.close()

    print(f"Done. {passed} job(s) moved to New for re-draft (score >= {get_min_fit_score()}).")


if __name__ == "__main__":
    main()
