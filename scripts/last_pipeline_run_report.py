#!/usr/bin/env python3
"""Report on the most recent pipeline run from jobagent.sqlite."""
from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"


def main() -> int:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT run_id, status, current_stage, last_error, started_at, updated_at
        FROM pipeline_runs ORDER BY updated_at DESC LIMIT 5
        """
    )
    runs = cur.fetchall()
    if not runs:
        print("No pipeline_runs found.")
        return 1

    run_id, status, stage, last_error, started_at, updated_at = runs[0]
    print("=" * 72)
    print("LAST PIPELINE RUN")
    print("=" * 72)
    print(f"Run ID:        {run_id}")
    print(f"Status:        {status}")
    print(f"Last stage:    {stage}")
    print(f"Started:       {started_at}")
    print(f"Updated:       {updated_at}")
    if last_error:
        print(f"Last error:    {last_error}")

    cur.execute(
        "SELECT timestamp FROM activity_log WHERE message LIKE ? ORDER BY id ASC LIMIT 1",
        (f"%{run_id}%",),
    )
    row = cur.fetchone()
    run_start = row[0] if row else started_at

    cur.execute(
        "SELECT status, current_item, items_completed, items_total, updated_at "
        "FROM system_status WHERE id='global'"
    )
    ui = cur.fetchone()
    print(f"\nUI system_status: {ui}")

    print("\n--- Recent runs (last 5) ---")
    for r in runs:
        print(f"  {r[0]} | {r[1]:10} | {r[2]:10} | {r[4]} -> {r[5]}")

    print("\n" + "=" * 72)
    print("STAGE TIMELINE")
    print("=" * 72)
    stage_markers = (
        "Pipeline Start",
        "Stage 1/5",
        "Stage 2/5",
        "Stage 3/5",
        "Stage 4/5",
        "Stage 5/5",
        "fully completed",
        "aborted due to failure",
        "BATCH_PROGRESS",
        "Export staging",
        "Evaluating fit",
    )
    cur.execute(
        """
        SELECT timestamp, level, source, message FROM activity_log
        WHERE timestamp >= ?
        ORDER BY id ASC
        """,
        (run_start,),
    )
    logs = cur.fetchall()

    for ts, level, source, msg in logs:
        if any(m in msg for m in stage_markers) or level == "ERROR":
            print(f"  [{ts}] {level:5} [{source:10}] {msg[:160]}")

    print("\n" + "=" * 72)
    print("CONNECTOR FETCH / SAVE")
    print("=" * 72)
    connector_lines = []
    for ts, level, source, msg in logs:
        if " fetched, " in msg and " saved" in msg:
            connector_lines.append((source, msg))
        if msg.startswith("Running connector:"):
            connector_lines.append((source, msg))
        if "Connector failed" in msg or (level == "ERROR" and source not in ("Scout", "Pipeline", "Ollama")):
            connector_lines.append((source, f"ERROR: {msg[:120]}"))

    if connector_lines:
        for src, msg in connector_lines:
            print(f"  [{src}] {msg}")
    else:
        print("  (no connector fetch/save lines in this run window)")

    print("\n" + "=" * 72)
    print("BATCH / EVALUATE SUMMARY")
    print("=" * 72)
    batch_progress = [msg for _, _, _, msg in logs if "[BATCH_PROGRESS]" in msg]
    if batch_progress:
        print(f"  Progress lines: {len(batch_progress)}")
        print(f"  First: {batch_progress[0][:140]}")
        print(f"  Last:  {batch_progress[-1][:140]}")
    else:
        print("  (no BATCH_PROGRESS lines — evaluate may not have run)")

    rejects = Counter()
    passes = 0
    for _, _, source, msg in logs:
        if source == "Pipeline" and "[REJECT]" in msg:
            reason = msg.split(" - ", 1)[-1].strip()[:80]
            rejects[reason] += 1
        if source == "Pipeline" and ("passed: true" in msg.lower() or "Passed (Score:" in msg):
            passes += 1

    print(f"  Draft passes logged: {passes}")
    if rejects:
        print(f"  Reject reasons ({sum(rejects.values())} total):")
        for reason, count in rejects.most_common(12):
            print(f"    {count:4d}  {reason}")

    print("\n" + "=" * 72)
    print("ERRORS / WARNINGS")
    print("=" * 72)
    err_lines = [(ts, source, msg) for ts, level, source, msg in logs if level == "ERROR"]
    if err_lines:
        for ts, source, msg in err_lines[-20:]:
            print(f"  [{ts}] [{source}] {msg[:180]}")
    else:
        print("  (none in run window)")

    ollama = [msg for _, _, src, msg in logs if src == "Ollama" or "VRAM" in msg or "Selected fallback" in msg]
    if ollama:
        print("\n  LLM / Ollama notes:")
        seen = set()
        for msg in ollama:
            key = msg[:100]
            if key not in seen:
                seen.add(key)
                print(f"    {msg[:160]}")

    print("\n" + "=" * 72)
    print("JOB QUEUE (current)")
    print("=" * 72)
    for row in cur.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY 2 DESC"):
        print(f"  {row[0]}: {row[1]}")

    cur.execute(
        """
        SELECT company, status, score, rejection_stage
        FROM jobs
        WHERE status IN ('Backlog', 'Drafted', 'Needs Retry', 'New')
        ORDER BY status, score DESC NULLS LAST
        LIMIT 20
        """
    )
    actionable = cur.fetchall()
    if actionable:
        print("\n  Actionable queue (sample):")
        for row in actionable:
            print(f"    {row}")

    print("\n" + "=" * 72)
    print("JOBS TOUCHED THIS RUN")
    print("=" * 72)
    cur.execute(
        """
        SELECT company, title, status, score, source_site, created_at
        FROM jobs
        WHERE created_at >= ?
        ORDER BY created_at DESC
        LIMIT 15
        """,
        (run_start,),
    )
    touched = cur.fetchall()
    if touched:
        for row in touched:
            print(f"  {row}")
    else:
        print("  (no job rows with timestamps in run window)")

    print("\n--- Samsara / LaSalle detail ---")
    for pattern in ("%Samsara%", "%LaSalle%"):
        cur.execute(
            "SELECT company, title, status, score, summary FROM jobs WHERE company LIKE ?",
            (pattern,),
        )
        for row in cur.fetchall():
            print(f"  {row}")

    print("\n--- Samsara pipeline messages ---")
    for row in cur.execute(
        """
        SELECT timestamp, message FROM activity_log
        WHERE timestamp >= ? AND message LIKE '%Samsara%'
        ORDER BY id
        """,
        (run_start,),
    ):
        print(f"  [{row[0]}] {row[1][:200]}")

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
