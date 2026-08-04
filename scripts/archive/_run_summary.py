#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Quick summary of latest sync run."""
import re
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
SINCE = "2026-07-06 19:35:00"

conn = sqlite3.connect(DB)
rows = conn.execute(
    "SELECT source, message FROM activity_log WHERE timestamp >= ? ORDER BY id",
    (SINCE,),
).fetchall()

reasons = Counter()
connector_stats = []
errors = []
llm_calls = []
for source, msg in rows:
    if " fetched, " in msg and " saved" in msg:
        connector_stats.append((source, msg))
    if "REJECT]" in msg:
        r = msg.split(" - ", 1)[-1].strip()[:70]
        reasons[r] += 1
    if source in ("Pipeline", "Ollama") and "Calling Local" in msg:
        llm_calls.append(msg[:200])
    if "ERROR" in msg or "Connector failed" in msg:
        errors.append(f"[{source}] {msg[:200]}")

print("=== Connector fetch/save ===")
for src, msg in connector_stats:
    print(f"  [{src}] {msg}")

print(f"\n=== Top reject reasons ({sum(reasons.values())} total) ===")
for r, c in reasons.most_common(15):
    print(f"  {c:4d}  {r}")

print("\n=== Job queue ===")
for row in conn.execute(
    "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY 2 DESC"
):
    print(f"  {row[0]}: {row[1]}")

print("\n=== Drafted / Backlog / Needs Retry ===")
for row in conn.execute(
    """
    SELECT company, status, LENGTH(COALESCE(jd_text,'')) as jd_len, fit_score
    FROM jobs
    WHERE status IN ('Drafted', 'Backlog', 'Needs Retry')
    ORDER BY status, jd_len DESC
    """
):
    print(f"  {row}")

print("\n=== theirstack rejects this run ===")
for (msg,) in conn.execute(
    "SELECT message FROM activity_log WHERE timestamp >= ? AND source='theirstack'",
    (SINCE,),
):
    print(f"  {msg[:200]}")

conn.close()
