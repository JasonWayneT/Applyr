#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Import CSV eval shortlist (Business Wire + tier 1/2) into jobs DB as Backlog."""
from __future__ import annotations

import csv
import json
import sqlite3
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
CSV_PATH = Path(r"C:\Users\Jason\Downloads\Job Evaluation 1 - Sheet1 (1).csv")
RESULTS = PROJECT_ROOT / "docs/reports/job-evaluation-1-sheet1-1-results.json"
JOBS_DIR = PROJECT_ROOT / "jobs"

KEEP = {
    "Business Wire": {
        "tier": "network",
        "score": 75,
        "summary": "User shortlist — internal contact at Business Wire. Media-adjacent TPM; frame platform PM + data, not SWE background.",
    },
    "Avetta": {
        "tier": 1,
        "score": 78,
        "summary": "Tier 1 — B2B compliance/supplier-risk SaaS; strong platform + discovery fit.",
    },
    "Endava": {
        "tier": 1,
        "score": 88,
        "summary": "Tier 1 — healthcare kidney-care platform PM; verify client embed vs product ownership.",
    },
    "Donorbox": {
        "tier": 1,
        "score": 76,
        "summary": "Tier 1 — data-model-heavy B2B CRM; segmentation + comms automation angle.",
    },
    "Outmarket AI": {
        "tier": 2,
        "score": 70,
        "summary": "Tier 2 — B2B insurance workflow PM; AI-enabled ops, not AI lead.",
    },
    "Rhythm Energy": {
        "tier": 2,
        "score": 68,
        "summary": "Tier 2 — customer data PM; Cision data pipeline story; energy vertical stretch.",
    },
    "Protege": {
        "tier": 2,
        "score": 72,
        "summary": "Tier 2 — ingestion/QA platform PM; AI data company caveat; ACC-102 angle.",
    },
}


def sanitize_filename(name: str) -> str:
    import re
    return re.sub(r"[\W_]+", "_", name).strip("_")


def format_staging_jd(position: str, url: str, jd: str) -> str:
    parts = []
    if position:
        parts.append(f"Title: {position}")
    if url:
        parts.append(f"URL: {url}")
    if parts:
        parts.append("")
    parts.append(jd)
    return "\n".join(parts)


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


def load_csv_rows() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with CSV_PATH.open(encoding="utf-8-sig", errors="ignore") as f:
        for row in csv.DictReader(f):
            company = (row.get("Company") or "").strip()
            if company in KEEP:
                url = (row.get("URL") or "").strip()
                if company == "ZoomInfo":
                    pass
                if url and not url.startswith("http"):
                    url = f"https://{url}"
                out[company] = {
                    "company": company,
                    "position": (row.get("Position") or "").strip(),
                    "url": url,
                    "jd": (row.get("Job Description") or "").strip(),
                }
    return out


def main() -> int:
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}")
        return 1

    rows = load_csv_rows()
    missing = sorted(set(KEEP) - set(rows))
    if missing:
        print(f"Missing from CSV: {missing}")
        return 1

    conn = sqlite3.connect(DB)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    added = updated = 0

    for company, meta in KEEP.items():
        row = rows[company]
        url = row["url"] or f"local://{sanitize_filename(company)}_{uuid.uuid4().hex[:8]}"
        existing = conn.execute(
            "SELECT id, rowid, status FROM jobs WHERE company = ? OR url = ? ORDER BY rowid DESC LIMIT 1",
            (company, url),
        ).fetchone()

        if existing:
            job_id, rowid, old_status = existing
            conn.execute(
                """
                UPDATE jobs SET title = ?, url = ?, jd_text = ?, status = 'Backlog',
                    score = ?, summary = ?, retry_count = 0
                WHERE id = ?
                """,
                (row["position"], url, row["jd"], meta["score"], meta["summary"], job_id),
            )
            sync_fts(conn, rowid)
            updated += 1
            print(f"  updated  {company} ({old_status} -> Backlog)")
        else:
            job_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
                VALUES (?, ?, ?, ?, 'Backlog', ?, ?, ?, 0)
                """,
                (job_id, company, row["position"], url, row["jd"], meta["score"], meta["summary"]),
            )
            rowid = conn.execute("SELECT rowid FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
            sync_fts(conn, rowid)
            added += 1
            print(f"  added    {company} (tier {meta['tier']}, score {meta['score']})")

        slug = sanitize_filename(company)
        staging = JOBS_DIR / f"{slug}_{job_id[:8]}.txt"
        staging.write_text(format_staging_jd(row["position"], url, row["jd"]), encoding="utf-8")

    conn.commit()
    conn.close()
    print(f"\nDone: {added} added, {updated} updated — {len(KEEP)} on shortlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
