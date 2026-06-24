import glob
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "jobagent.sqlite")
conn = sqlite3.connect(DB)

print("Staging (jobs/*.txt):", len(glob.glob(os.path.join(ROOT, "jobs", "*.txt"))))
print("\nJob counts:")
for row in conn.execute(
    "SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY COUNT(*) DESC"
):
    print(f"  {row[0]}: {row[1]}")

print("\nRecent pipeline runs:")
for r in conn.execute(
    "SELECT run_id, status, current_stage, started_at FROM pipeline_runs "
    "ORDER BY started_at DESC LIMIT 3"
):
    print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")

row = conn.execute(
    "SELECT status, current_item, items_completed, items_total, updated_at "
    "FROM system_status WHERE id='global'"
).fetchone()
print("\nSystem status:", row)

# Backlog with assets hint
backlog = conn.execute(
    "SELECT company, score FROM jobs WHERE status='Backlog' ORDER BY score DESC LIMIT 8"
).fetchall()
if backlog:
    print("\nTop Backlog (ready to apply):")
    for c, sc in backlog:
        print(f"  {c} (score {sc})")

conn.close()
