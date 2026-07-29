#!/usr/bin/env python3
"""Close stale pipeline-queue jobs and block staffing re-ingest."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "jobagent.sqlite"

CLOSE_JOBS = [
    (
        "2af9f69c-6c0f-4b1b-b789-8d9f15330ef2",
        "Staffing firm posting — not pursuing",
    ),
    (
        "769647d6-63ee-45ac-903b-f96414c718ca",
        "Staffing firm posting — not pursuing",
    ),
    (
        "328607e8-df2f-420e-ab8d-6281d6e07966",
        "Dismissed from pipeline queue",
    ),
    (
        "0e44fa47-10d2-4992-b3b8-c17af901568c",
        "Below fit threshold (68 < 72)",
    ),
    (
        "17a90089-cb9c-457c-b3a8-49a7b1b1ee8b",
        "Below fit threshold (20 < 72) — duplicate Acquia role",
    ),
]

STALE_URLS = [
    (
        "https://www.adzuna.com/land/ad/5793696990?se=ZkLocbF78RGm9YHvQ8XokQ&utm_medium=api&utm_source=2be7f996&v=61EDC3217EBDA87BA6938CE252AB4262D1933947",
        "Beacon Talent",
        "Senior Product Manager, Life Sciences Data Products",
    ),
    (
        "https://www.adzuna.com/land/ad/5736199270?se=uhWAWCZ68RGeHY1Elccfvg&utm_medium=api&utm_source=2be7f996&v=3CF66E090B30BB5B39D52BC5FCBAC27023E04E48",
        "Apex Systems",
        "Digital Technical Product Manager",
    ),
]


def main() -> None:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for job_id, note in CLOSE_JOBS:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'Closed',
                rejection_type = 'Self-Rejected',
                rejection_stage = 'Closed',
                outcome_notes = ?
            WHERE id = ?
            """,
            (note, job_id),
        )
        print(f"Closed {job_id}: {note}")

    for url, company, title in STALE_URLS:
        cur.execute(
            "INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)",
            (url, company, title),
        )
        print(f"Stale-listed {company}")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
