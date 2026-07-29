#!/usr/bin/env python3
"""Draft all companies in csv_batch2_manifest.json."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
PY = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
MANIFEST = PROJECT_ROOT / "data" / "csv_batch2_manifest.json"
MIN_FIT = 72

sys.path.insert(0, str(SCRIPTS))

from applyr_python import assert_applyr_host  # noqa: E402
from batch_pipeline import _has_required_pdfs, process_single  # noqa: E402
from drafting_engine import run_drafting_engine  # noqa: E402
from utils import load_file, WORK_EXP_FILE  # noqa: E402


def force_draft(company: str, jd: str, score: int, summary: str) -> None:
    work_exp = load_file(WORK_EXP_FILE)
    result = {"Score": score, "Decision": "YES", "Summary": summary}
    run_drafting_engine(company, jd, work_exp, result, display_name=company)
    from batch_pipeline import generate_cheat_sheet, GPU_LOCK

    display = company
    with GPU_LOCK:
        generate_cheat_sheet(company, display_name=display)


def compile_pdfs(company: str, folder: Path) -> None:
    for md, pdf in (("Resume.md", "Resume.pdf"), ("CoverLetter.md", "CoverLetter.pdf")):
        md_path = folder / md
        if md_path.exists():
            subprocess.run(
                [str(PY), str(SCRIPTS / "compile_single.py"), str(md_path), str(folder / pdf)],
                check=True,
                cwd=str(SCRIPTS),
            )


def verify_company(company: str, folder: Path) -> list[str]:
    errors = []
    from quality_checker import check_resume
    from submission_linter import lint_document

    for doc in ("Resume.md", "CoverLetter.md"):
        path = folder / doc
        if not path.exists():
            errors.append(f"missing {doc}")
            continue
        r = lint_document(path.read_text(encoding="utf-8"), filename=doc)
        if r.blocks:
            errors.append(f"lint {doc}: {[b.rule_id for b in r.blocks]}")
    resume = folder / "Resume.md"
    if resume.exists():
        try:
            ok, msg = check_resume(str(resume))
            if not ok:
                errors.append(f"qa: {msg}")
        except Exception as exc:
            errors.append(f"qa: {str(exc)[:200]}")
    for pdf in ("Resume.pdf", "CoverLetter.pdf"):
        p = folder / pdf
        if not p.exists():
            errors.append(f"missing {pdf}")
            continue
        info = subprocess.run(
            ["pdfinfo", str(p)], capture_output=True, text=True, check=True
        )
        if "Pages:           2" in info.stdout or "Pages:           3" in info.stdout:
            errors.append(f"{pdf} multi-page")
    return errors


def slug(company: str) -> str:
    import re

    return re.sub(r"[\W_]+", "_", company).strip("_").lower()


def main() -> int:
    assert_applyr_host()
    if not MANIFEST.exists():
        print("Run import_csv_batch2.py first", file=sys.stderr)
        return 1

    manifest: list[list] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    conn = sqlite3.connect(DB)
    ok, fail = [], []

    for company, job_id, score in manifest:
        folder = PROJECT_ROOT / "data" / "submissions" / slug(company)
        print(f"\n{'='*60}\n{company} (score={score})")

        if _has_required_pdfs(company):
            print("  PDFs exist — skipping draft")
            conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
            conn.commit()
            ok.append(company)
            continue

        row = conn.execute(
            "SELECT url, jd_text, summary FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not row:
            fail.append((company, "job not in DB"))
            continue
        url, jd, summary = row

        try:
            # Curated shortlist: force draft (user already tiered); skip re-fit + location gates.
            print(f"  force-draft (curated tier score {score})")
            force_draft(company, jd, int(score), summary or "")
            compile_pdfs(company, folder)
        except Exception as exc:
            fail.append((company, str(exc)[:200]))
            print(f"  DRAFT FAIL: {exc}")
            continue

        if not _has_required_pdfs(company):
            fail.append((company, "missing PDFs after draft"))
            continue

        errs = verify_company(company, folder)
        if errs:
            fail.append((company, "; ".join(errs)))
            print(f"  VERIFY FAIL: {errs}")
            conn.execute(
                "UPDATE jobs SET status='Needs Retry' WHERE id=?", (job_id,)
            )
        else:
            conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
            ok.append(company)
            print("  OK")
        conn.commit()
        time.sleep(1)

    conn.close()
    print(f"\nDone: {len(ok)} ok | {len(fail)} fail")
    for f in fail:
        print(" ", f)
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
