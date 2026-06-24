"""
Clean up pending-assets backlog: close duplicate rows, restore archive PDFs, draft missing assets.

Operational script (read/write DB + filesystem). Safe to re-run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "submissions")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "archive", "submissions")

# Junk / duplicate Backlog rows identified in pending-assets audit
CLOSE_JOB_IDS: list[tuple[str, str]] = [
    ("cvs_health_manager_digital_product", "Generic careers URL, no fit score"),
    (
        "cvs_health_manager_digital_product_client_clinical_experience",
        "Google search URL, no fit score",
    ),
    ("0b283601", "Duplicate Global Payments row (kept UUID listing)"),
]

KEEP_GLOBAL_PAYMENTS_ID = "17786605-adc9-4fa4-9670-553a1d0c6349"
GLOBAL_PAYMENTS_CAREERS_URL = (
    "https://jobs.globalpayments.com/en/jobs/r0071330/product-manager-platform-services"
)


def slug(company: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    return s or "company"


def resolve_folder(base: str, company: str) -> str:
    if not os.path.isdir(base):
        return os.path.join(base, slug(company))
    target = slug(company).replace("_", "")
    for name in os.listdir(base):
        path = os.path.join(base, name)
        if os.path.isdir(path) and name.replace("_", "") == target:
            return path
    return os.path.join(base, slug(company))


def has_resume_cover_pdfs(folder: str) -> bool:
    if not os.path.isdir(folder):
        return False
    pdfs = [f.lower() for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    return any("resume" in f for f in pdfs) and any("cover" in f for f in pdfs)


def merge_folder(src: str, dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dest, name)
        if os.path.isdir(s):
            merge_folder(s, d)
        else:
            shutil.copy2(s, d)


def restore_archived(company: str, dry_run: bool) -> bool:
    archive_path = resolve_folder(ARCHIVE_DIR, company)
    active_path = resolve_folder(SUBMISSIONS_DIR, company)
    if not os.path.isdir(archive_path):
        print(f"  [skip restore] no archive for {company}")
        return False
    if not has_resume_cover_pdfs(archive_path):
        print(f"  [skip restore] archive missing full PDFs for {company}")
        return False
    if dry_run:
        print(f"  [dry-run] would restore {archive_path} -> {active_path}")
        return True
    os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
    if os.path.isdir(active_path):
        merge_folder(archive_path, active_path)
        shutil.rmtree(archive_path)
    else:
        shutil.move(archive_path, active_path)
    print(f"  [restored] {company}")
    return True


def close_duplicates(conn: sqlite3.Connection, dry_run: bool) -> int:
    closed = 0
    for job_id, reason in CLOSE_JOB_IDS:
        row = conn.execute(
            "SELECT company, title, status FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            print(f"  [skip close] id not found: {job_id}")
            continue
        if row[2] != "Backlog":
            print(f"  [skip close] {row[0]} not Backlog ({row[2]}): {job_id}")
            continue
        note = f"Pending-assets cleanup: {reason}"
        if dry_run:
            print(f"  [dry-run] close {row[0]} — {row[1][:50]} ({job_id})")
        else:
            conn.execute(
                """
                UPDATE jobs SET status = 'Closed', rejection_stage = 'Backlog',
                rejection_type = 'Self-Rejected', outcome_notes = ?
                WHERE id = ?
                """,
                (note, job_id),
            )
            print(f"  [closed] {row[0]} ({job_id})")
        closed += 1

    row = conn.execute(
        "SELECT url FROM jobs WHERE id = ?", (KEEP_GLOBAL_PAYMENTS_ID,)
    ).fetchone()
    if row and row[0] != GLOBAL_PAYMENTS_CAREERS_URL:
        if dry_run:
            print(f"  [dry-run] update Global Payments URL on {KEEP_GLOBAL_PAYMENTS_ID}")
        else:
            conn.execute(
                "UPDATE jobs SET url = ? WHERE id = ?",
                (GLOBAL_PAYMENTS_CAREERS_URL, KEEP_GLOBAL_PAYMENTS_ID),
            )
            print("  [updated] Global Payments careers URL on kept row")
    return closed


def backlog_without_pdfs(conn: sqlite3.Connection) -> list[tuple]:
    rows = conn.execute(
        """
        SELECT id, company, title, score, status
        FROM jobs
        WHERE status IN ('Backlog', 'Needs Retry')
        ORDER BY score IS NULL, score DESC, company
        """
    ).fetchall()
    pending = []
    for r in rows:
        active = resolve_folder(SUBMISSIONS_DIR, r[1])
        if has_resume_cover_pdfs(active):
            continue
        pending.append(r)
    return pending


def draft_jobs(job_rows: list[tuple], dry_run: bool) -> tuple[list[str], list[tuple[str, str]]]:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
    from batch_pipeline import (  # noqa: E402
        _company_submission_dir,
        _has_required_pdfs,
        process_single,
    )

    ok: list[str] = []
    fail: list[tuple[str, str]] = []
    for job_id, company, title, score, status in job_rows:
        if score is not None and int(score) < 72:
            print(f"  [skip draft] {company} score {score} < 72")
            continue
        print(f"\n>>> Draft {company} ({job_id[:8]}...) score={score}")
        if dry_run:
            print("  [dry-run] would run process_single draft-only")
            continue
        try:
            process_single(company, url=None, jd_text="", job_id=job_id, draft_only=True)
            manifest = os.path.join(_company_submission_dir(company), "draft_manifest.json")
            if _has_required_pdfs(company) and os.path.exists(manifest):
                ok.append(company)
            else:
                fail.append((company, "missing PDFs or manifest after draft"))
        except SystemExit:
            fail.append((company, "system exit"))
        except Exception as exc:
            fail.append((company, str(exc)))
        time.sleep(1)
    return ok, fail


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean pending-assets backlog")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Run draft-only pipeline for jobs still missing PDFs",
    )
    parser.add_argument(
        "--no-restore",
        action="store_true",
        help="Skip archive -> submissions restore",
    )
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print("jobagent.sqlite not found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    print("=== Phase 1: Close duplicate Backlog rows ===")
    n_closed = close_duplicates(conn, args.dry_run)
    if not args.dry_run:
        conn.commit()

    if not args.no_restore:
        print("\n=== Phase 2: Restore archive PDFs to submissions/ ===")
        rows = conn.execute(
            "SELECT DISTINCT company FROM jobs WHERE status IN ('Backlog', 'Needs Retry')"
        ).fetchall()
        restored = 0
        for (company,) in rows:
            active = resolve_folder(SUBMISSIONS_DIR, company)
            if has_resume_cover_pdfs(active):
                continue
            if restore_archived(company, args.dry_run):
                restored += 1
        print(f"Restored {restored} company folder(s)")

    pending = backlog_without_pdfs(conn)
    print(f"\n=== Still pending PDFs: {len(pending)} job(s) ===")
    for r in pending:
        print(f"  score={r[3]}  {r[1][:28]:28}  {r[2][:40]}")

    if args.draft and pending:
        print("\n=== Phase 3: Draft missing assets ===")
        ok, fail = draft_jobs(pending, args.dry_run)
        print(f"\nDraft complete: {len(ok)} ok, {len(fail)} failed")
        for c in ok:
            print(f"  OK   {c}")
        for c, err in fail:
            print(f"  FAIL {c}: {err}")

    conn.close()
    print(f"\nDone. Closed {n_closed} duplicate row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
