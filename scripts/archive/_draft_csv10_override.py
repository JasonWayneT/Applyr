#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""One-off: draft 4 jobs the automated fit engine scored 60-62 (unstable across
reruns, no clear reject reason) but manual review flagged as strong B2B SaaS
PM fits. User-approved override, see conversation 2026-07-14."""
import glob
import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from applyr_python import assert_applyr_host
from drafting_engine import run_drafting_engine
from generate_cheat_sheet import generate_cheat_sheet
from utils import JOBS_DIR, WORK_EXP_FILE, init_pipeline_prefs, load_file


def _load_staging_jd(job_id: str) -> str:
    prefix = job_id[:8]
    matches = glob.glob(os.path.join(JOBS_DIR, f"*_{prefix}.txt"))
    if not matches:
        return ""
    text = load_file(matches[0])
    # Strip staging "Title:"/"URL:" header lines
    lines = text.strip().splitlines()
    body, past_headers = [], False
    for line in lines:
        s = line.strip()
        if not past_headers:
            if s.startswith("Title:") or s.startswith("URL:") or not s:
                continue
            past_headers = True
        body.append(line)
    return "\n".join(body).strip() if body else text.strip()

JOBS = [
    {
        "job_id": "b93ec717",
        "company": "Sago",
        "display": "Sago",
        "summary": "User override: location-gate false positive (Canada eligibility mention triggered non-US flag despite explicit US remote eligibility). Enterprise digital projects, existing product, 3+ YOE fits.",
    },
]

MANUAL_SCORE = 80


def main() -> int:
    assert_applyr_host()
    init_pipeline_prefs()
    db_path = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
    work_exp = load_file(WORK_EXP_FILE)

    for job in JOBS:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT company FROM jobs WHERE id LIKE ?", (f"{job['job_id']}%",)
        ).fetchone()
        conn.close()
        if not row:
            print(f"[SKIP] Job not found in DB for {job['company']} ({job['job_id']})")
            continue
        db_company = row[0]
        jd_text = _load_staging_jd(job["job_id"])
        if not jd_text or len(jd_text) < 100:
            print(f"[SKIP] No staging JD text found for {job['company']} ({job['job_id']})")
            continue

        result = {
            "Score": MANUAL_SCORE,
            "Decision": "YES",
            "Summary": job["summary"],
        }
        print(f"\n=== Drafting {job['display']} ===")
        try:
            run_drafting_engine(
                db_company, jd_text, work_exp, result, display_name=job["display"]
            )
        except Exception as e:
            print(f"  [DRAFT ERROR] {job['display']}: {e}")
            continue
        try:
            generate_cheat_sheet(db_company, display_name=job["display"])
        except Exception as e:
            print(f"  [Cheat sheet warning] {e}")

        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE jobs SET status = 'Backlog', score = ?, summary = ? WHERE id LIKE ?",
            (MANUAL_SCORE, job["summary"], f"{job['job_id']}%"),
        )
        conn.commit()
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
