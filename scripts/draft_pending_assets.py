"""Draft assets for New/Drafted jobs missing PDFs."""
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


def main() -> int:
    assert_applyr_host()
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """
        SELECT id, company, title, status
        FROM jobs
        WHERE status IN ('New', 'Drafted', 'Backlog', 'Needs Retry')
        ORDER BY company
        """
    ).fetchall()
    conn.close()

    pending = []
    for job_id, company, title, status in rows:
        if _has_required_pdfs(company):
            print(f"[skip] {company} — PDFs already exist")
            continue
        pending.append((job_id, company, title, status))

    if not pending:
        print("No pending-assets jobs found.")
        return 0

    print(f"Drafting {len(pending)} job(s)...")
    ok, fail = [], []
    for job_id, company, title, status in pending:
        print(f"\n{'='*60}\n>>> {company} ({status}) {title[:50]}\n{'='*60}")
        try:
            process_single(company, url=None, jd_text="", job_id=job_id, draft_only=False)
            if _has_required_pdfs(company):
                ok.append(company)
            else:
                fail.append((company, "missing PDFs after draft"))
        except SystemExit:
            fail.append((company, "system exit"))
        except Exception as exc:
            fail.append((company, str(exc)))
        time.sleep(2)

    print(f"\n=== DONE: {len(ok)} ok, {len(fail)} failed ===")
    for c in ok:
        print(f"  OK   {c}")
    for c, err in fail:
        print(f"  FAIL {c}: {err[:200]}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
