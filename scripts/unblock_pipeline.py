"""
Reset stuck RUNNING pipeline runs and set system_status to idle.

Use when evaluate stage hung (e.g. Ollama fit timeout) and UI shows Job 4/15 forever.
Implements BUG-011 recovery path.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "jobagent.sqlite")


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"No database at {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    runs = conn.execute(
        "SELECT run_id, current_stage FROM pipeline_runs WHERE status = 'RUNNING'"
    ).fetchall()
    note = f"Manual unblock at {datetime.now().isoformat(timespec='seconds')}"
    for run_id, stage in runs:
        conn.execute(
            """
            UPDATE pipeline_runs
            SET status = 'FAILED', last_error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE run_id = ?
            """,
            (f"{note} (was {stage})", run_id),
        )
        print(f"  Marked FAILED: {run_id} (stage {stage})")

    conn.execute(
        """
        UPDATE system_status
        SET status = 'idle',
            current_item = ?,
            items_completed = 0,
            items_total = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 'global'
        """,
        ("Pipeline unblocked. Start a new sync when ready.",),
    )
    conn.commit()
    conn.close()

    if not runs:
        print("No RUNNING pipeline runs found; system_status set to idle.")
    else:
        print(f"Unblocked {len(runs)} run(s). Restart dev server if batch Python is still running.")
    print("Tip: run `ollama ps` — if qwen is stuck loaded, stop it with `ollama stop qwen2.5:7b-instruct-q4_K_M`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
