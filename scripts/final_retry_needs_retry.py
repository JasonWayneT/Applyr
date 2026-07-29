#!/usr/bin/env python3
"""Final retry for remaining Needs Retry jobs with JD in DB."""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "jobagent.sqlite"
sys.path.insert(0, str(ROOT / "scripts"))

from applyr_python import assert_applyr_host
from batch_pipeline import _has_required_pdfs, process_single

COMPANIES = ["Tivity Health", "UKG"]


def main() -> int:
    assert_applyr_host()
    conn = sqlite3.connect(DB)
    ok, fail = [], []

    for company in COMPANIES:
        row = conn.execute(
            """
            SELECT id, url, jd_text, score, status
            FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1
            """,
            (company,),
        ).fetchone()
        if not row:
            fail.append((company, "not in DB"))
            continue

        job_id, url, jd_text, score, status = row
        if not jd_text or len(jd_text.strip()) < 800:
            fail.append((company, f"JD too short ({len(jd_text or '')} chars)"))
            continue

        conn.execute(
            "UPDATE jobs SET retry_count = 0, status = 'Drafted' WHERE id = ?",
            (job_id,),
        )
        conn.commit()

        print(f"\n>>> Final retry: {company} (was {status}, jd={len(jd_text)} chars)")
        try:
            process_single(
                company,
                url=url or "",
                jd_text=jd_text,
                job_id=job_id,
                draft_only=False,
            )
            if _has_required_pdfs(company):
                conn.execute(
                    "UPDATE jobs SET status = 'Backlog', retry_count = 0 WHERE id = ?",
                    (job_id,),
                )
                conn.commit()
                ok.append(company)
            else:
                fail.append((company, "missing PDFs after run"))
        except Exception as exc:
            fail.append((company, str(exc)[:300]))

        time.sleep(2)

    conn.close()
    print(f"\n=== FINAL RETRY: {len(ok)} ok, {len(fail)} failed ===")
    for c in ok:
        print(f"  OK   {c}")
    for c, err in fail:
        print(f"  FAIL {c}: {err}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
