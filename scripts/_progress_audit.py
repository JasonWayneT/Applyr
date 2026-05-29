#!/usr/bin/env python3
import sqlite3
import os
import re

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobagent.sqlite")
c = sqlite3.connect(DB)

print("=== JOB_PROGRESS timeline (this run) ===")
rows = c.execute(
    """
    SELECT timestamp, message FROM activity_log
    WHERE message LIKE '%JOB_PROGRESS%' OR message LIKE '%Job %/%: Evaluating%'
    ORDER BY id ASC
    """
).fetchall()
for ts, msg in rows[-40:]:
    print(f"  {ts}  {msg}")

print("\n=== Unique evaluate targets (last 50 'Evaluating' lines) ===")
evals = c.execute(
    """
    SELECT timestamp, message FROM activity_log
    WHERE message LIKE '%Evaluating %' AND source IN ('Pipeline', 'Scout')
    ORDER BY id DESC LIMIT 50
    """
).fetchall()
seen = []
for ts, msg in reversed(evals):
    m = re.search(r"Evaluating (.+?)\.\.\.", msg) or re.search(r"Evaluating (.+)$", msg)
    name = m.group(1) if m else msg[:60]
    if name not in seen[-5:]:
        seen.append(name)
    print(f"  {ts}  {name}")

print("\n=== system_status current_item history (last 20) ===")
# current_item updates may be in activity as Pipeline lines
for ts, msg in c.execute(
    """
    SELECT timestamp, message FROM activity_log
    WHERE message LIKE 'Job %/%:%' OR message LIKE '%current_item%'
    ORDER BY id DESC LIMIT 20
    """
).fetchall():
    print(f"  {ts}  {msg[:100]}")

print("\n=== Stuck LLM calls? (last 5 min) ===")
for ts, msg in c.execute(
    """
    SELECT timestamp, message FROM activity_log
    WHERE timestamp > datetime('now', '-30 minutes')
    AND (message LIKE '%Calling Local LLM%' OR message LIKE '%LLM Local%' OR message LIKE '%Ollama%'
         OR message LIKE '%Result:%' OR message LIKE '%GATEKEEPER%' OR message LIKE '%Processing:%')
    ORDER BY id DESC LIMIT 25
    """
).fetchall():
    print(f"  {ts}  {msg[:120]}")

print("\n=== Last log entry ===")
row = c.execute("SELECT timestamp, level, message FROM activity_log ORDER BY id DESC LIMIT 1").fetchone()
print(row)

c.close()
