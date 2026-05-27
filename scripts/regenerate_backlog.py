"""
Regenerate all Backlog submission folders with compose + CR-018 polish.
Implements FR-100–FR-108 (CR-017, CR-018).
"""
import os
import sqlite3
import sys
import time

# Ensure compose + local-first + template cheat sheets for regeneration
os.environ.setdefault("DRAFT_MODE", "compose")
os.environ.setdefault("LOCAL_ONLY_MODE", "1")
os.environ.setdefault("CHEAT_SHEET_MODE", "template")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(PROJECT_ROOT, "jobagent.sqlite")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from batch_pipeline import process_single  # noqa: E402


def main():
    if not os.path.exists(DB):
        print("No jobagent.sqlite")
        sys.exit(1)

    conn = sqlite3.connect(DB)
    rows = conn.execute(
        """SELECT id, company, score, summary FROM jobs
           WHERE (status = 'Backlog' OR status = 'Needs Retry')
             AND score >= 72
           ORDER BY company"""
    ).fetchall()
    conn.close()

    if not rows:
        print("No Backlog jobs found.")
        return

    print(f"Regenerating {len(rows)} Backlog job(s) (DRAFT_MODE={os.environ.get('DRAFT_MODE')}, LOCAL_ONLY_MODE={os.environ.get('LOCAL_ONLY_MODE')})")
    ok, fail = [], []
    from batch_pipeline import _has_required_pdfs, _company_submission_dir

    for job_id, company, score, summary in rows:
        print(f"\n{'='*60}\n>>> {company} ({job_id[:8]}...) score={score}\n{'='*60}")
        try:
            process_single(
                company,
                url=None,
                jd_text="",
                job_id=job_id,
                draft_only=True,
            )
            manifest_path = os.path.join(
                _company_submission_dir(company), "draft_manifest.json"
            )
            if _has_required_pdfs(company) and os.path.exists(manifest_path):
                with open(manifest_path, encoding="utf-8") as f:
                    import json
                    m = json.load(f)
                if m.get("verification_passed") and m.get("pipeline_version", "").startswith("CR-017"):
                    ok.append(company)
                else:
                    fail.append((company, f"incomplete manifest: {m.get('pipeline_version')}"))
            else:
                fail.append((company, "missing PDFs or manifest after draft"))
        except SystemExit:
            fail.append((company, "system exit"))
        except Exception as e:
            print(f"FAILED {company}: {e}")
            fail.append((company, str(e)))
        time.sleep(2)

    print(f"\n=== DONE: {len(ok)} ok, {len(fail)} failed ===")
    for c in ok:
        print(f"  OK  {c}")
    for c, err in fail:
        print(f"  FAIL {c}: {err}")


if __name__ == "__main__":
    main()
