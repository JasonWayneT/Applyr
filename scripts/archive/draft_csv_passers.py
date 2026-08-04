#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Draft CSV eval passers + retry stuck Needs Retry jobs with saved fit scores."""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
JOBS_DIR = PROJECT_ROOT / "jobs"
CSV_PATH = Path(r"C:\Users\Jason\Downloads\Job Evaluation 1 - Sheet1.csv")
RESULTS_JSON = PROJECT_ROOT / "docs" / "reports" / "csv-job-evaluation-1-results.json"

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from applyr_python import assert_applyr_host  # noqa: E402
from batch_pipeline import _has_required_pdfs, process_single  # noqa: E402
from import_csv_jobs import _format_staging_jd, sanitize_filename  # noqa: E402


def load_csv_by_company() -> dict[str, dict]:
    out: dict[str, dict] = {}
    with CSV_PATH.open(encoding="utf-8-sig", errors="ignore") as f:
        for row in csv.DictReader(f):
            company = (row.get("Company") or "").strip()
            if company:
                out[company] = {
                    "company": company,
                    "position": (row.get("Position") or "").strip(),
                    "url": (row.get("URL") or "").strip(),
                    "jd": (row.get("Job Description") or "").strip(),
                }
    return out


def upsert_job(conn: sqlite3.Connection, row: dict, score: int) -> str:
    company = row["company"]
    url = row["url"] or f"local://{sanitize_filename(company)}_{uuid.uuid4().hex[:8]}"
    existing = conn.execute(
        "SELECT id, status FROM jobs WHERE company = ? OR url = ? ORDER BY rowid DESC LIMIT 1",
        (company, url),
    ).fetchone()
    if existing:
        job_id = existing[0]
        conn.execute(
            """
            UPDATE jobs
            SET title = ?, url = ?, jd_text = ?, status = 'Drafted',
                score = ?, summary = ?, retry_count = 0
            WHERE id = ?
            """,
            (
                row["position"],
                url,
                row["jd"],
                score,
                "Structured fit evaluation (CSV import)",
                job_id,
            ),
        )
    else:
        job_id = uuid.uuid4().hex[:8]
        conn.execute(
            """
            INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
            VALUES (?, ?, ?, ?, 'Drafted', ?, ?, ?, 0)
            """,
            (
                job_id,
                company,
                row["position"],
                url,
                row["jd"],
                score,
                "Structured fit evaluation (CSV import)",
            ),
        )
    conn.commit()
    slug = sanitize_filename(company)
    staging = JOBS_DIR / f"{slug}_{job_id[:8]}.txt"
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    staging.write_text(_format_staging_jd(row["position"], url, row["jd"]), encoding="utf-8")
    return job_id


def draft_job(company: str, job_id: str, jd: str, url: str) -> tuple[bool, str]:
    if _has_required_pdfs(company):
        return True, "PDFs already exist"
    print(f"\n>>> Drafting {company} (job_id={job_id[:8]}, draft_only=True)")
    try:
        process_single(company, url=url, jd_text=jd, job_id=job_id, draft_only=True)
        if _has_required_pdfs(company):
            return True, "ok"
        return False, "missing PDFs after draft"
    except Exception as exc:
        return False, str(exc)[:300]


def main() -> int:
    assert_applyr_host()
    if not RESULTS_JSON.exists():
        print(f"Missing results: {RESULTS_JSON}", file=sys.stderr)
        return 1

    results = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    passers = [r for r in results if r.get("verdict") == "PASS"]
    csv_rows = load_csv_by_company()

    conn = sqlite3.connect(DB)
    ok, fail = [], []

    print(f"=== CSV passers ({len(passers)}) ===")
    for r in passers:
        company = r["company"]
        csv_row = csv_rows.get(company)
        if not csv_row or not csv_row["jd"]:
            fail.append((company, "missing JD in CSV"))
            continue
        score = int(r.get("score") or 88)
        job_id = upsert_job(conn, csv_row, score)
        success, msg = draft_job(company, job_id, csv_row["jd"], csv_row["url"])
        (ok if success else fail).append((company, msg))
        time.sleep(2)

    retry_companies = ["hackajob", "Ottimate"]
    print(f"\n=== Needs Retry re-draft ({len(retry_companies)}) ===")
    for company in retry_companies:
        row = conn.execute(
            "SELECT id, url, jd_text, score FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()
        if not row:
            fail.append((company, "not in DB"))
            continue
        job_id, url, jd_text, score = row
        if not jd_text:
            fail.append((company, "no jd_text"))
            continue
        if score is None or score < 72:
            fail.append((company, f"no pass score ({score})"))
            continue
        conn.execute(
            "UPDATE jobs SET retry_count = 0, status = 'Drafted' WHERE id = ?",
            (job_id,),
        )
        conn.commit()
        success, msg = draft_job(company, job_id, jd_text, url or "")
        (ok if success else fail).append((company, msg))
        time.sleep(2)

    conn.close()
    print(f"\n=== DONE: {len(ok)} ok, {len(fail)} failed ===")
    for c, m in ok:
        print(f"  OK   {c}: {m}")
    for c, m in fail:
        print(f"  FAIL {c}: {m}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
