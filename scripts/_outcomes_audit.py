#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
c = sqlite3.connect(DB)

print("=== TOTAL JOBS ===", c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])

print("\n=== BY STATUS ===")
for r in c.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status ORDER BY 2 DESC"):
    print(f"  {r[0]}: {r[1]}")

print("\n=== APPLIED (ever in funnel) ===")
applied_now = c.execute("SELECT COUNT(*) FROM jobs WHERE status='Applied'").fetchone()[0]
in_funnel = c.execute("""
    SELECT COUNT(*) FROM jobs WHERE status IN (
      'Applied','Recruiter Screen','Core Interviews','Offer and Negotiation'
    )
""").fetchone()[0]
closed_from_applied = c.execute("""
    SELECT COUNT(*) FROM jobs WHERE status='Closed' AND rejection_stage='Applied'
""").fetchone()[0]
later = c.execute(
    "SELECT COUNT(*) FROM jobs WHERE status IN ('Recruiter Screen','Core Interviews','Offer and Negotiation')"
).fetchone()[0]
ever_applied = applied_now + closed_from_applied + later
print(f"  Currently Applied: {applied_now}")
print(f"  Active funnel (Applied + screens + offer): {in_funnel}")
print(f"  Closed with rejection_stage=Applied: {closed_from_applied}")
print(f"  Estimated ever-applied: {ever_applied}")

print("\n=== CLOSED: rejection_stage x rejection_type ===")
for r in c.execute("""
    SELECT COALESCE(rejection_stage,'(null)'), COALESCE(rejection_type,'(null)'), COUNT(*)
    FROM jobs WHERE status='Closed'
    GROUP BY 1,2 ORDER BY 3 DESC
"""):
    print(f"  stage={r[0]:20} type={r[1]:25} count={r[2]}")

print("\n=== REJECTIONS AFTER APPLY (stage Applied or later, status Closed) ===")
for r in c.execute("""
    SELECT COALESCE(rejection_stage,'(null)'), COALESCE(rejection_type,'(null)'), COUNT(*)
    FROM jobs WHERE status='Closed'
      AND rejection_stage IN ('Applied','Recruiter Screen','Core Interviews','Offer and Negotiation')
    GROUP BY 1,2 ORDER BY 3 DESC
"""):
    print(f"  stage={r[0]:20} type={r[1]:25} count={r[2]}")

print("\n=== REJECTED status (pre-apply pipeline rejects) ===")
for r in c.execute("""
    SELECT COALESCE(rejection_type,'(null)'), COUNT(*)
    FROM jobs WHERE status='Rejected'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
"""):
    print(f"  type={r[0]}: {r[1]}")

print("\n=== rejection_stage='Closed' (the suspicious 2) ===")
for r in c.execute("""
    SELECT company, rejection_type, outcome_notes
    FROM jobs WHERE status='Closed' AND rejection_stage='Closed'
"""):
    print(f"  {r[0]} | {r[1]} | {str(r[2])[:80]}")

FUNNEL_STAGES = (
    "Applied",
    "Recruiter Screen",
    "Core Interviews",
    "Offer and Negotiation",
)
stages_sql = ",".join(f"'{s}'" for s in FUNNEL_STAGES)

ever = c.execute(
    f"""
    SELECT COUNT(*) FROM jobs WHERE
      status IN ({stages_sql})
      OR (status = 'Closed' AND rejection_stage IN ({stages_sql}))
    """
).fetchone()[0]
print(f"\n=== Ever applied (SQL) === {ever}")

c.close()
