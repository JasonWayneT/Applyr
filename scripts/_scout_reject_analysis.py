#!/usr/bin/env python3
"""Analyze scout reject reasons for last pipeline run."""
import re
import sqlite3
from collections import Counter
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
RUN_START = "2026-07-07 16:02:00"

conn = sqlite3.connect(DB)
rows = conn.execute(
    """
    SELECT source, message FROM activity_log
    WHERE timestamp >= ? AND message LIKE '[REJECT]%'
    ORDER BY id
    """,
    (RUN_START,),
).fetchall()

reasons = Counter()
by_source = Counter()
silent = Counter()

for source, msg in rows:
    by_source[source] += 1
    if "Title Blocklist" in msg:
        reasons["title_blocklist"] += 1
    elif "target_role_scope" in msg:
        reasons["target_role_scope"] += 1
    elif "URL already exists" in msg:
        reasons["url_duplicate"] += 1
    elif "Company/Title already exists" in msg:
        reasons["company_title_duplicate"] += 1
    elif "LinkedIn URL blocked" in msg:
        reasons["linkedin_blocked"] += 1
    elif "GEOGRAPHIC REJECT" in msg:
        reasons["geographic"] += 1
    elif "industry_blocked" in msg:
        reasons["industry_blocked"] += 1
    elif "required_years" in msg:
        reasons["years_exceeded"] += 1
    else:
        reasons["other_logged"] += 1

# Industry/geo rejections often don't log per-job in orchestrator - only filtered++
# Count fetched vs logged rejects
fetched_total = 0
saved_total = 0
for source, msg in conn.execute(
    """
    SELECT source, message FROM activity_log
    WHERE timestamp >= ? AND source = 'Scout' AND message LIKE '% fetched,% saved'
    """,
    (RUN_START,),
):
    m = re.search(r"(\d+) fetched, (\d+) saved", msg)
    if m:
        fetched_total += int(m.group(1))
        saved_total += int(m.group(2))

print("=== SCOUT REJECT ANALYSIS (last run) ===")
print(f"Fetched: {fetched_total} | Saved: {saved_total} | Filtered (no save): {fetched_total - saved_total}")
print(f"\nLogged [REJECT] lines: {len(rows)}")
print("\nBy reason:")
for r, c in reasons.most_common():
    print(f"  {c:4d}  {r}")

print("\nBy source (logged rejects only):")
for s, c in by_source.most_common():
    print(f"  {c:4d}  {s}")

print("\nTop target_role_scope examples:")
scope_examples = [msg for _, msg in rows if "target_role_scope" in msg][:8]
for ex in scope_examples:
    print(f"  {ex[:120]}")

print("\nTop title blocklist examples:")
tb = [msg for _, msg in rows if "Title Blocklist" in msg][:8]
for ex in tb:
    print(f"  {ex[:120]}")

# Silent filters: industry + geo don't always log in orchestrator
print("\nNote: industry_blocked and geographic gates increment filtered without per-job log lines.")

conn.close()
