#!/usr/bin/env python3
"""Tail activity_log + system_status during a job search run."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
POLL_SEC = 3
MAX_SEC = 1800


def main() -> int:
    if not DB.exists():
        print(f"[MONITOR] DB not found: {DB}", flush=True)
        return 1

    conn = sqlite3.connect(DB, timeout=5)
    last_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM activity_log").fetchone()[0]
    conn.close()

    seen_status: str | None = None
    start = time.time()
    print("=== Job search monitor started ===", flush=True)
    print(f"Watching from activity_log id > {last_id}", flush=True)

    while time.time() - start < MAX_SEC:
        try:
            conn = sqlite3.connect(DB, timeout=5)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT status, current_item, updated_at FROM system_status WHERE id='global'"
            ).fetchone()
            if row:
                st = f"{row['status']}|{row['current_item']}"
                if st != seen_status:
                    seen_status = st
                    print(
                        f"[STATUS] {row['status']}: {row['current_item']} ({row['updated_at']})",
                        flush=True,
                    )

            rows = conn.execute(
                """
                SELECT id, timestamp, level, source, message
                FROM activity_log WHERE id > ? ORDER BY id
                """,
                (last_id,),
            ).fetchall()
            for r in rows:
                last_id = r["id"]
                lvl = r["level"]
                msg = (r["message"] or "")[:500]
                prefix = f"[{r['timestamp']}] {lvl:5} [{r['source']}] "
                low = msg.lower()
                if lvl in ("ERROR", "WARN"):
                    print(prefix + msg, flush=True)
                elif any(
                    k in low
                    for k in (
                        "error",
                        "failed",
                        "reject",
                        "connector_error",
                        "exited with code",
                        "abort",
                    )
                ):
                    print(prefix + msg, flush=True)
                elif "fetched" in low or "saved" in low or "batch_summary" in low:
                    print(prefix + msg, flush=True)

            conn.close()

            if row and row["status"] == "idle" and time.time() - start > 45:
                conn = sqlite3.connect(DB, timeout=5)
                recent = conn.execute(
                    """
                    SELECT COUNT(*) FROM activity_log
                    WHERE timestamp > datetime('now', '-90 seconds')
                    """
                ).fetchone()[0]
                conn.close()
                if recent == 0:
                    print("[MONITOR] Pipeline idle, no log activity — stopping.", flush=True)
                    break
        except Exception as e:
            print(f"[MONITOR] poll error: {e}", flush=True)
        time.sleep(POLL_SEC)

    print("=== Monitor ended ===", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
