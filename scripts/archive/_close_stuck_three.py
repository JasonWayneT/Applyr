# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Close the 3 stuck Drafted jobs (thin JD / years gate) and remove staging debris."""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "jobagent.sqlite"
JOBS_DIR = ROOT / "jobs"
SUB = ROOT / "data" / "submissions"

CLOSE_BY_ID = {
    "91ac1f28": ("DUÄST", "Thin JD from aggregator — removed from pipeline"),
}

CLOSE = {
    "Securly": "Wrong role + thin JD snippet — removed from pipeline",
    "Cambridge Spark": "10+ years required (exceeds max 7) — removed from pipeline",
}


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company, flags=re.I).strip("_")


def _close_one(
    conn: sqlite3.Connection, job_id: str, company: str, status: str, note: str
) -> None:
    conn.execute(
        """
        UPDATE jobs
        SET status = 'Closed',
            rejection_stage = ?,
            rejection_type = 'Self-Rejected',
            outcome_notes = ?
        WHERE id = ?
        """,
        (status, note, job_id),
    )
    print(f"  Closed {company} ({status} -> Closed)")

    prefix = job_id[:8]
    if JOBS_DIR.is_dir():
        for path in JOBS_DIR.glob(f"*{prefix}*.txt"):
            path.unlink(missing_ok=True)
            print(f"    removed staging {path.name}")

    folder = SUB / slug(company)
    if folder.is_dir() and not any(folder.glob("Resume.pdf")):
        shutil.rmtree(folder, ignore_errors=True)
        print(f"    removed empty submission folder {folder.name}")


def main() -> int:
    conn = sqlite3.connect(DB)
    closed = 0

    for prefix, (label, note) in CLOSE_BY_ID.items():
        row = conn.execute(
            "SELECT id, company, status FROM jobs WHERE id LIKE ? ORDER BY rowid DESC LIMIT 1",
            (f"{prefix}%",),
        ).fetchone()
        if not row:
            print(f"  [skip] {label} — not in DB")
            continue
        job_id, company, status = row
        _close_one(conn, job_id, company or label, status, note)
        closed += 1

    for company, note in CLOSE.items():
        row = conn.execute(
            "SELECT id, status FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()
        if not row:
            print(f"  [skip] {company} — not in DB")
            continue
        job_id, status = row
        _close_one(conn, job_id, company, status, note)
        closed += 1

    conn.commit()
    conn.close()
    print(f"\nDone — closed {closed} job(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
