#!/usr/bin/env python3
"""Mark Werfen as Applied (or create if missing)."""
import sqlite3
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
JOBS_DIR = PROJECT_ROOT / "jobs"

JD = """Software Product Owner — Werfen (Autoimmunity)
San Diego, CA — hybrid, 3 days onsite

Werfen is a worldwide leader in specialized diagnostics (Hemostasis, Acute Care, Transfusion, Autoimmunity, Transplant).

Software Product Owner role in the Autoimmunity business line:
- Own and maintain prioritized product backlog
- Translate user needs into requirements, user stories, acceptance criteria
- Collaborate with engineering, QA, product managers, regulatory/quality teams
- Agile ceremonies, sprint planning, release readiness
- 3-5 years Software Product Owner or similar PM-focused role
- Preferred: biotech/medical device software, regulatory standards
- Salary: $110k-$140k
"""

COMPANY = "Werfen"
TITLE = "Software Product Owner"


def sync_fts(conn: sqlite3.Connection, rowid: int) -> None:
    row = conn.execute(
        "SELECT company, title, summary, url FROM jobs WHERE rowid = ?", (rowid,)
    ).fetchone()
    if not row:
        return
    conn.execute("DELETE FROM jobs_fts WHERE rowid = ?", (rowid,))
    conn.execute(
        "INSERT INTO jobs_fts(rowid, company, title, summary, url) VALUES (?, ?, ?, ?, ?)",
        (rowid, row[0] or "", row[1] or "", row[2] or "", row[3] or ""),
    )


def main() -> None:
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT id, rowid, status FROM jobs WHERE company LIKE ? ORDER BY rowid DESC LIMIT 1",
        ("%Werfen%",),
    ).fetchone()

    if row:
        job_id, rowid, old_status = row
        conn.execute(
            "UPDATE jobs SET status = 'Applied', company = ?, title = ? WHERE id = ?",
            (COMPANY, TITLE, job_id),
        )
        sync_fts(conn, rowid)
        print(f"Updated {COMPANY}: {old_status} -> Applied (id={job_id})")
    else:
        job_id = str(uuid.uuid4())
        url = f"local://werfen_{job_id[:8]}"
        summary = "Healthcare diagnostics; Software PO, Autoimmunity line, San Diego hybrid."
        conn.execute(
            """INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
               VALUES (?, ?, ?, ?, 'Applied', ?, ?, ?, 0)""",
            (job_id, COMPANY, TITLE, url, JD, 62, summary),
        )
        rowid = conn.execute("SELECT rowid FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
        sync_fts(conn, rowid)
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        staging = JOBS_DIR / f"Werfen_{job_id[:8]}.txt"
        staging.write_text(f"Title: {TITLE}\nURL: {url}\n\n{JD}", encoding="utf-8")
        print(f"Created {COMPANY} as Applied (id={job_id})")

    conn.commit()
    verify = conn.execute(
        "SELECT company, title, status FROM jobs WHERE company = ?", (COMPANY,)
    ).fetchone()
    print("Verify:", verify)
    conn.close()


if __name__ == "__main__":
    main()
