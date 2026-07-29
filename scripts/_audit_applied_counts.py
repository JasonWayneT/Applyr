#!/usr/bin/env python3
import re
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
ARCH = Path(__file__).resolve().parent.parent / "data" / "archive" / "submissions"

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

conn = sqlite3.connect(DB)
c = conn.cursor()

print("=== DB status ===")
for row in c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY 2 DESC"):
    print(f"  {row[0]}: {row[1]}")

active = c.execute(
    """
    SELECT COUNT(*) FROM jobs WHERE status IN (
      'Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation'
    )
    """
).fetchone()[0]
print(f"\nDashboard header (activeJobs): {active}")

print("\n=== Closed rejection_stage ===")
for row in c.execute(
    """
    SELECT COALESCE(rejection_stage, '(null)'), COUNT(*)
    FROM jobs WHERE status = 'Closed'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 15
    """
):
    print(f"  {row[0]}: {row[1]}")

applied = [r[0] for r in c.execute("SELECT company FROM jobs WHERE status = 'Applied'")]
folders = [
    p.name
    for p in ARCH.iterdir()
    if p.is_dir() and "_backup_" not in p.name
]

applied_slugs = {slug(x) for x in applied}
arch_slugs = {slug(x) for x in folders}

print(f"\n=== Filesystem vs DB ===")
print(f"  Applied in DB: {len(applied)}")
print(f"  Archive folders (no backups): {len(folders)}")
print(f"  Archive folders NOT Applied in DB: {len(arch_slugs - applied_slugs)}")
print(f"  Applied in DB NOT in archive: {len(applied_slugs - arch_slugs)}")

backlog_assets = c.execute("SELECT COUNT(*) FROM jobs WHERE status='Backlog'").fetchone()[0]
drafted = c.execute("SELECT COUNT(*) FROM jobs WHERE status='Drafted'").fetchone()[0]
new = c.execute("SELECT COUNT(*) FROM jobs WHERE status='New'").fetchone()[0]
print(f"\n=== Other pipeline statuses ===")
print(f"  Backlog: {backlog_assets}")
print(f"  Drafted: {drafted}")
print(f"  New: {new}")

conn.close()
