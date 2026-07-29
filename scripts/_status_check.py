import json
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
conn = sqlite3.connect(db)
settings = json.loads(conn.execute("SELECT value FROM profiles WHERE key='llm_settings'").fetchone()[0])
print("=== llm_settings ===")
for k in ("primaryProvider", "localModel", "localModelFit", "localFallbackModel", "vram_threshold_mb"):
    print(f"  {k}: {settings.get(k, '(unset)')}")

rows = conn.execute(
    "SELECT process_type, status, current_item, items_completed, items_total, updated_at "
    "FROM system_status ORDER BY updated_at DESC LIMIT 3"
).fetchall()
print("\n=== system_status ===")
for r in rows:
    print(f"  {r}")

print("\n=== recent pipeline (last 25 notable) ===")
logs = conn.execute(
    """
    SELECT timestamp, level, message FROM activity_log
    WHERE message LIKE '%phi4%' OR message LIKE '%LLM%' OR message LIKE '%BATCH%'
       OR message LIKE '%Scout%' OR message LIKE '%ERROR%' OR message LIKE '%Export%'
       OR message LIKE '%evaluate%' OR message LIKE '%DRAFT%'
    ORDER BY id DESC LIMIT 25
    """
).fetchall()
if not logs:
    logs = conn.execute(
        "SELECT timestamp, level, message FROM activity_log ORDER BY id DESC LIMIT 10"
    ).fetchall()
for ts, level, msg in reversed(logs):
    print(f"  [{ts}] {level}: {msg[:180]}")

print("\n=== latest activity (any, last 8) ===")
latest = conn.execute(
    "SELECT timestamp, level, source, message FROM activity_log ORDER BY id DESC LIMIT 8"
).fetchall()
for ts, level, source, msg in reversed(latest):
    print(f"  [{ts}] {level} [{source}]: {msg[:180]}")

conn.close()
