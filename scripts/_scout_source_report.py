"""Per-source report for the current scout run only."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute(
    "SELECT run_id, status, current_stage, updated_at FROM pipeline_runs ORDER BY updated_at DESC LIMIT 1"
)
run = cur.fetchone()
run_id, run_status, stage, run_ts = run
print(f"RUN: {run_id} | {run_status} | {stage} | {run_ts}")

cur.execute(
    "SELECT timestamp FROM activity_log WHERE message LIKE ? ORDER BY id ASC LIMIT 1",
    (f"%Initialized run {run_id}%",),
)
run_start_row = cur.fetchone()
run_start = run_start_row[0] if run_start_row else run_ts
print(f"Run started (log): {run_start}")

cur.execute("SELECT status, current_item, updated_at FROM system_status WHERE id='global'")
print(f"UI:  {cur.fetchone()}\n")

cur.execute("SELECT id, name, status, consecutive_failures, last_success_at FROM sources ORDER BY id")
all_sources = {row[0]: row for row in cur.fetchall()}
print(f"Registered sources: {len(all_sources)}\n")

# Logs since this run started (use run timestamp)
cur.execute(
    """
    SELECT timestamp, level, source, message FROM activity_log
    WHERE timestamp >= ?
      AND (
        message LIKE 'Running connector:%'
        OR (source = 'Scout' AND message LIKE '% fetched,% saved')
        OR (level = 'ERROR' AND source IN (SELECT id FROM sources))
        OR message LIKE 'Connector failed:%'
      )
    ORDER BY id ASC
    """,
    (run_start,),
)
rows = cur.fetchall()

summary: dict[str, dict] = {sid: {"ran": False, "fetched": None, "saved": None, "error": None} for sid in all_sources}

for ts, level, source, msg in rows:
    if msg.startswith("Running connector:"):
        sid = msg.split(":", 1)[1].strip()
        if sid in summary:
            summary[sid]["ran"] = True
            summary[sid]["started_at"] = ts
    if source == "Scout" and " fetched," in msg and " saved" in msg:
        sid, rest = msg.split(":", 1)
        sid = sid.strip()
        if sid in summary:
            summary[sid]["ran"] = True
            # " 37 fetched, 0 saved"
            parts = rest.strip().split(",")
            for p in parts:
                p = p.strip()
                if p.endswith(" fetched"):
                    summary[sid]["fetched"] = int(p.split()[0])
                if p.endswith(" saved"):
                    summary[sid]["saved"] = int(p.split()[0])
    if level == "ERROR" and source in summary:
        summary[source]["error"] = msg[:180]

ok, warn, fail, pending = [], [], [], []
for sid in sorted(all_sources.keys()):
    s = summary[sid]
    name = all_sources[sid][1]
    db_status = all_sources[sid][2]
    if not s["ran"]:
        pending.append((sid, name, db_status))
    elif s["error"]:
        fail.append((sid, name, s))
    elif s["fetched"] == 0 and s["saved"] == 0:
        warn.append((sid, name, s))  # ran but zero results — may be normal
    else:
        ok.append((sid, name, s))

print("=== CONNECTOR FETCH OK (returned jobs) ===")
for sid, name, s in ok:
    print(f"  {sid:16} {name:18} fetched={s['fetched']} saved={s['saved']}")

print(f"\n=== RAN, ZERO NEW JOBS ({len(warn)}) — connector worked, nothing passed gates ===")
for sid, name, s in warn:
    err = f" | last err: {s['error']}" if s.get("error") else ""
    print(f"  {sid:16} {name:18} fetched=0 saved=0{err}")

print(f"\n=== FAILED ({len(fail)}) ===")
for sid, name, s in fail:
    print(f"  {sid:16} {name:18} {s['error']}")

print(f"\n=== NOT RUN YET ({len(pending)}) ===")
for sid, name, db_status in pending:
    print(f"  {sid:16} {name:18} db={db_status}")

print(f"\nTOTAL: {len(all_sources)} sources | ran={len(all_sources)-len(pending)} | fetch_ok={len(ok)} | zero={len(warn)} | fail={len(fail)} | pending={len(pending)}")
conn.close()
