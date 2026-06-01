#!/usr/bin/env python3
"""One-off diagnostic for last pipeline run."""
import sqlite3
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "jobagent.sqlite")
conn = sqlite3.connect(DB)

print("=== Job status counts ===")
for row in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY 2 DESC"):
    print(f"  {row[0]}: {row[1]}")

print("\n=== Funnel (New/Backlog/Drafted/Needs Retry) ===")
for row in conn.execute(
    "SELECT company, title, status, score, created_at FROM jobs "
    "WHERE status IN ('New','Backlog','Drafted','Needs Retry') ORDER BY created_at DESC LIMIT 20"
):
    print(row)

print("\n=== Jobs with company 'name' (scrape bug) ===")
for row in conn.execute(
    "SELECT id, company, title, substr(url,1,60), status, score FROM jobs "
    "WHERE lower(company) = 'name' OR company LIKE '%name%' ORDER BY created_at DESC LIMIT 15"
):
    print(row)

print("\n=== Latest run scout logs (FOUND/REJECT/scout) ===")
for row in conn.execute(
    "SELECT timestamp, substr(message,1,140) FROM activity_log "
    "WHERE id > (SELECT MAX(id) - 200 FROM activity_log) "
    "AND (message LIKE '%FOUND%' OR message LIKE '%Scout%' OR message LIKE '%Match Found%' "
    "OR message LIKE '%REJECT%' OR message LIKE '%Staging%' OR message LIKE '%ZERO-TOKEN%' "
    "OR message LIKE '%duplicate%' OR message LIKE '%BATCH_SUMMARY%') "
    "ORDER BY id"
):
    print(row)

print("\n=== system_status ===")
print(conn.execute("SELECT * FROM system_status WHERE id='global'").fetchone())

print("\n=== Built In jobs in DB ===")
for row in conn.execute(
    "SELECT status, COUNT(1) FROM jobs WHERE source_site = 'Built In' GROUP BY status"
):
    print(row)
for row in conn.execute(
    "SELECT company, title, length(COALESCE(jd_text,'')), status, created_at "
    "FROM jobs WHERE source_site = 'Built In' ORDER BY created_at DESC LIMIT 8"
):
    print(row)
row = conn.execute(
    "SELECT COUNT(1) FROM jobs WHERE source_site = 'Built In' AND jd_text IS NOT NULL AND length(jd_text) > 200"
).fetchone()
print("Built In with jd_text>200:", row[0])

conn.close()
