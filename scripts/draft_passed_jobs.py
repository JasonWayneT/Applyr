"""Seed pass scores for jobs that cleared fit earlier, then draft-only (skip re-score)."""
from __future__ import annotations

import os
import sqlite3
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from applyr_python import assert_applyr_host
from batch_pipeline import _has_required_pdfs, process_single

# Passed structured fit in prior batch run (score 88) before local LLM regression
PASS_SCORE = 88
COMPANIES = [
    "Constellation Dealer Group",
    "Ottimate",
    "Preservica",
    "Securly",
    "hackajob",
    "Tivity Health",
    "Distru",
]


def main() -> int:
    assert_applyr_host()
    conn = sqlite3.connect(DB)
    ok, fail = [], []

    for company in COMPANIES:
        row = conn.execute(
            "SELECT id, status FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()
        if not row:
            fail.append((company, "not in DB"))
            continue
        job_id, status = row
        if _has_required_pdfs(company):
            print(f"[skip] {company} — PDFs exist")
            continue
        conn.execute(
            "UPDATE jobs SET score = ?, summary = ? WHERE id = ?",
            (PASS_SCORE, "Structured fit evaluation (draft-only re-run)", job_id),
        )
        conn.commit()
        print(f"\n>>> Draft-only {company} (score={PASS_SCORE})")
        try:
            process_single(company, url=None, jd_text="", job_id=job_id, draft_only=True)
            if _has_required_pdfs(company):
                ok.append(company)
            else:
                fail.append((company, "missing PDFs after draft"))
        except Exception as exc:
            fail.append((company, str(exc)[:200]))
        time.sleep(2)

    conn.close()
    print(f"\n=== {len(ok)} ok, {len(fail)} failed ===")
    for c in ok:
        print(f"  OK   {c}")
    for c, e in fail:
        print(f"  FAIL {c}: {e}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
