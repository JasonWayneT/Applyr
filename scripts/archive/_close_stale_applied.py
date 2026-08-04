#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Close Applied jobs older than 60 days as Ghosted."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
DAYS = 60

conn = sqlite3.connect(DB)
rows = conn.execute(
    """
    SELECT id, company, title, created_at
    FROM jobs
    WHERE status = 'Applied'
      AND created_at < datetime('now', ?)
    ORDER BY created_at
    """,
    (f"-{DAYS} days",),
).fetchall()

print(f"Applied jobs older than {DAYS} days: {len(rows)}")
for r in rows:
    print(f"  {r[3][:10]}  {r[1]} — {r[2]}")

if not rows:
    conn.close()
    raise SystemExit(0)

conn.executemany(
    """
    UPDATE jobs SET
        status = 'Closed',
        rejection_stage = 'Applied',
        rejection_type = 'Ghosted',
        outcome_notes = 'Auto-closed: Applied with no activity for > 60 days'
    WHERE id = ?
    """,
    [(r[0],) for r in rows],
)
conn.commit()
print(f"\nClosed {len(rows)} jobs.")

remaining = conn.execute(
    "SELECT company, title, created_at FROM jobs WHERE status = 'Applied' ORDER BY created_at"
).fetchall()
print(f"Remaining Applied: {len(remaining)}")
for r in remaining:
    print(f"  {r[2][:10]}  {r[0]} — {r[1]}")
conn.close()
