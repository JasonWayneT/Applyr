#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Force-draft soft-eval tier 1/2 shortlist (BOLD skipped). Curated — skip re-fit/location gates."""
from __future__ import annotations

import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
PY = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"

# Display company names as imported (match DB lower(company))
COMPANIES = [
    "Tilt",
    "OneStream Software",
    "Lumos",
    "MyTime",
    "Covideo",
    "DataGrail",
    "Remote",
    "PAR",
    "Buyers Edge Platform",
    "Redox",
    "Ontra",
    "ParkingPass.com",
]

sys.path.insert(0, str(SCRIPTS))

from applyr_python import assert_applyr_host  # noqa: E402
from batch_pipeline import _has_required_pdfs, GPU_LOCK  # noqa: E402
from company_slug import company_submission_dir, sanitize_company_slug  # noqa: E402
from drafting_engine import run_drafting_engine  # noqa: E402
from utils import WORK_EXP_FILE, init_pipeline_prefs, load_file  # noqa: E402


def force_draft(company: str, jd: str, score: int, summary: str) -> None:
    work_exp = load_file(WORK_EXP_FILE)
    result = {"Score": score, "Decision": "YES", "Summary": summary}
    run_drafting_engine(company, jd, work_exp, result, display_name=company)
    from batch_pipeline import generate_cheat_sheet

    with GPU_LOCK:
        generate_cheat_sheet(company, display_name=company)


def compile_pdfs(folder: Path) -> None:
    for md, pdf in (("Resume.md", "Resume.pdf"), ("CoverLetter.md", "CoverLetter.pdf")):
        md_path = folder / md
        if md_path.exists():
            subprocess.run(
                [str(PY), str(SCRIPTS / "compile_single.py"), str(md_path), str(folder / pdf)],
                check=True,
                cwd=str(SCRIPTS),
            )


def folder_for(company: str) -> Path:
    return Path(company_submission_dir(str(PROJECT_ROOT / "data" / "submissions"), company))


def main() -> int:
    assert_applyr_host()
    init_pipeline_prefs()
    conn = sqlite3.connect(DB)
    ok, fail = [], []

    for company in COMPANIES:
        print(f"\n{'=' * 60}\n{company}")
        row = conn.execute(
            """SELECT id, company, url, jd_text, score, summary, status
               FROM jobs WHERE lower(company) = lower(?)
               ORDER BY rowid DESC LIMIT 1""",
            (company,),
        ).fetchone()
        if not row:
            fail.append((company, "not in DB"))
            print("  FAIL: not in DB")
            continue

        job_id, db_company, url, jd, score, summary, status = row
        folder = folder_for(db_company)
        folder.mkdir(parents=True, exist_ok=True)
        if jd and not (folder / "Original_JD.txt").exists():
            (folder / "Original_JD.txt").write_text(jd, encoding="utf-8")

        if _has_required_pdfs(db_company) or _has_required_pdfs(company):
            print("  PDFs exist — marking Drafted")
            conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
            conn.commit()
            ok.append(company)
            continue

        if not jd or len(jd) < 200:
            fail.append((company, "JD too short"))
            print("  FAIL: JD too short")
            continue

        try:
            print(f"  force-draft score={score} (was {status})")
            force_draft(db_company if db_company else company, jd, int(score or 72), summary or "")
            compile_pdfs(folder)
        except Exception as exc:
            fail.append((company, str(exc)[:300]))
            print(f"  DRAFT FAIL: {exc}")
            conn.execute(
                "UPDATE jobs SET status='Needs Retry' WHERE id=?",
                (job_id,),
            )
            conn.commit()
            continue

        if not (_has_required_pdfs(db_company) or _has_required_pdfs(company)):
            # Also check folder directly
            if not ((folder / "Resume.pdf").exists() and (folder / "CoverLetter.pdf").exists()):
                fail.append((company, "missing PDFs after draft"))
                conn.execute(
                    "UPDATE jobs SET status='Needs Retry' WHERE id=?",
                    (job_id,),
                )
                conn.commit()
                continue

        conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
        conn.commit()
        ok.append(company)
        print("  OK")
        time.sleep(1)

    conn.close()
    print(f"\nDone: {len(ok)} ok | {len(fail)} fail")
    for c in ok:
        print(f"  OK   {c}")
    for c, m in fail:
        print(f"  FAIL {c}: {m}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
