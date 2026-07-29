import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "jobagent.sqlite"
SUB = ROOT / "data" / "submissions"
JOBS = ROOT / "jobs"

conn = sqlite3.connect(DB)
rows = conn.execute(
    """
    SELECT company, title, status, LENGTH(COALESCE(jd_text,'')) as jd_len,
           COALESCE(retry_count,0), score, outcome_notes, rejection_type, url
    FROM jobs
    WHERE status IN ('Drafted', 'Needs Retry', 'Backlog')
    ORDER BY status, company
    """
).fetchall()

print("=== Pipeline queue (Drafted / Needs Retry / Backlog) ===")
for r in rows:
    co = r[0]
    slug = co.lower().replace(" ", "_")
    sub = SUB / slug
    if not sub.exists():
        for d in SUB.iterdir() if SUB.exists() else []:
            if d.name.lower().replace(" ", "_") == slug.replace(" ", "_"):
                sub = d
                break
    pdfs = []
    if sub.exists():
        for name in ("Resume.pdf", "CoverLetter.pdf"):
            p = sub / name
            pdfs.append(f"{name}:{'Y' if p.exists() else 'N'}")
    staging = list(JOBS.glob(f"{co.replace(' ', '_')}*.txt")) if JOBS.exists() else []
    print(f"\n{co} | {r[2]} | jd={r[3]} | retries={r[4]} | score={r[5]}")
    print(f"  title: {r[1][:70]}")
    if r[6]:
        print(f"  notes: {str(r[6])[:120]}")
    if r[7]:
        print(f"  rejection: {r[7]}")
    if pdfs:
        print(f"  assets: {', '.join(pdfs)}")
    if staging:
        print(f"  staging: {staging[0].name} ({staging[0].stat().st_size} bytes)")
    elif r[2] == "Drafted":
        print("  staging: MISSING")

conn.close()
