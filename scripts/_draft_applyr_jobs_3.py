#!/usr/bin/env python3
"""Add PointClickCare + draft Expel, Secureframe, Doximity from applyr_jobs (3).csv."""
from __future__ import annotations

import csv
import sqlite3
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
JOBS_DIR = PROJECT_ROOT / "jobs"
SUBMISSIONS = PROJECT_ROOT / "data" / "submissions"
CSV_PATH = Path(r"C:\Users\Jason\Downloads\applyr_jobs (3).csv")

REMOTE_PREFIX = "Location: Remote, United States\n\n"

ADD_ONLY = {
    "Pointclickcare": {
        "score": 75,
        "summary": "Manual add — healthcare SaaS PM; cross-functional delivery + roadmap overlap (remote assumed).",
    },
}

DRAFT = {
    "Expel": {
        "score": 76,
        "summary": "Manual override — security/platform PM; SaaS monetization + detection strategy angle.",
        "display": "Expel",
    },
    "Secureframe": {
        "score": 77,
        "summary": "Manual override — compliance/GRC SaaS PM; security backlog + compliance workflow fit.",
        "display": "Secureframe",
    },
    "Doximity": {
        "score": 75,
        "summary": "Manual override — healthcare media platform PM; hospital partnerships + data-driven delivery.",
        "display": "Doximity",
    },
}

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from applyr_python import assert_applyr_host  # noqa: E402
from batch_pipeline import _has_required_pdfs, process_single  # noqa: E402
from company_slug import company_submission_dir, sanitize_company_slug  # noqa: E402
from import_csv_jobs import _format_staging_jd, sanitize_filename  # noqa: E402
from utils import init_pipeline_prefs  # noqa: E402


def load_csv_rows() -> dict[str, dict]:
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


def write_original_jd(company: str, jd: str) -> None:
    folder = Path(company_submission_dir(str(SUBMISSIONS), company))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Original_JD.txt").write_text(jd, encoding="utf-8")


def upsert_job(
    conn: sqlite3.Connection,
    row: dict,
    *,
    score: int,
    summary: str,
    status: str,
    remote_jd: bool,
) -> str:
    company = row["company"]
    url = row["url"] or f"local://{sanitize_filename(company)}_{uuid.uuid4().hex[:8]}"
    jd_text = (REMOTE_PREFIX + row["jd"]) if remote_jd else row["jd"]
    existing = conn.execute(
        "SELECT id, rowid FROM jobs WHERE url = ? OR (LOWER(company) = LOWER(?) AND url LIKE '%welcometothejungle%') ORDER BY rowid DESC LIMIT 1",
        (url, company),
    ).fetchone()
    if existing:
        job_id, rowid = existing
        conn.execute(
            """
            UPDATE jobs
            SET company = ?, title = ?, url = ?, jd_text = ?, status = ?,
                score = ?, summary = ?, retry_count = 0, rejection_stage = NULL
            WHERE id = ?
            """,
            (company, row["position"], url, jd_text, status, score, summary, job_id),
        )
        sync_fts(conn, rowid)
    else:
        job_id = uuid.uuid4().hex[:8]
        conn.execute(
            """
            INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (job_id, company, row["position"], url, status, jd_text, score, summary),
        )
        rowid = conn.execute("SELECT rowid FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
        sync_fts(conn, rowid)

    conn.commit()
    slug = sanitize_filename(company)
    staging = JOBS_DIR / f"{slug}_{job_id[:8]}.txt"
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    staging.write_text(_format_staging_jd(row["position"], url, jd_text), encoding="utf-8")
    write_original_jd(company, row["jd"])
    return job_id


def draft_job(company: str, job_id: str, jd_text: str, url: str) -> tuple[bool, str]:
    if _has_required_pdfs(company):
        return True, "PDFs already exist"
    print(f"\n>>> Drafting {company} (job_id={job_id[:8]}, draft_only=True)")
    try:
        process_single(company, url=url, jd_text=jd_text, job_id=job_id, draft_only=True)
        if _has_required_pdfs(company):
            return True, "ok"
        return False, "missing PDFs after draft"
    except Exception as exc:
        return False, str(exc)[:400]


def main() -> int:
    assert_applyr_host()
    init_pipeline_prefs()
    if not CSV_PATH.exists():
        print(f"CSV not found: {CSV_PATH}", file=sys.stderr)
        return 1

    rows = load_csv_rows()
    needed = set(ADD_ONLY) | set(DRAFT)
    missing = sorted(needed - set(rows))
    if missing:
        print(f"Missing from CSV: {missing}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB)
    ok, fail = [], []

    for company, meta in ADD_ONLY.items():
        row = rows[company]
        job_id = upsert_job(
            conn,
            row,
            score=meta["score"],
            summary=meta["summary"],
            status="Backlog",
            remote_jd=True,
        )
        print(f"  added    {company} -> Backlog (score {meta['score']}, id={job_id[:8]})")
        ok.append((company, "added to Backlog"))

    for company, meta in DRAFT.items():
        row = rows[company]
        jd_text = REMOTE_PREFIX + row["jd"]
        job_id = upsert_job(
            conn,
            row,
            score=meta["score"],
            summary=meta["summary"],
            status="Drafted",
            remote_jd=True,
        )
        url = row["url"]
        success, msg = draft_job(company, job_id, jd_text, url)
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
