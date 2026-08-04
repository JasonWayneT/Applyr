#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Promote clean batch2 jobs to Drafted; lint-fix + retry failures."""
from __future__ import annotations

import json
import re
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
SUB = PROJECT_ROOT / "data/submissions"

sys.path.insert(0, str(SCRIPTS))

from applyr_python import assert_applyr_host  # noqa: E402
from batch_pipeline import _has_required_pdfs  # noqa: E402
from quality_checker import check_resume  # noqa: E402
from submission_linter import lint_document  # noqa: E402
from run_csv_batch2_draft import (  # noqa: E402
    compile_pdfs,
    force_draft,
    slug,
    verify_company,
)

BUZZWORD_REPLACEMENTS = {
    "leverage": "use",
    "passionate": "focused",
    "dynamic": "fast-moving",
    "innovative": "practical",
    "seamless": "smooth",
    "transformative": "meaningful",
    "synergy": "alignment",
    "tapestry": "mix",
    "revolutionize": "improve",
    "proven track record": "six years of platform PM work",
}

REDRAFT_COMPANIES = {"PerformYard", "Crain Communications", "OpenRouter"}


def folder_state(company: str) -> tuple[str, list[str]]:
    folder = SUB / slug(company)
    if not folder.exists():
        return "empty", []
    pdfs = {f.name for f in folder.glob("*.pdf")}
    if "Resume.pdf" not in pdfs or "CoverLetter.pdf" not in pdfs:
        return "partial" if list(folder.glob("*.md")) else "empty", []
    blocks = []
    for doc in ("Resume.md", "CoverLetter.md"):
        p = folder / doc
        if p.exists():
            r = lint_document(p.read_text(encoding="utf-8"), filename=doc)
            blocks += [b.rule_id for b in r.blocks]
    qa_ok = True
    resume = folder / "Resume.md"
    if resume.exists():
        try:
            qa_ok, _ = check_resume(str(resume))
        except Exception:
            qa_ok = False
    for pdf in ("Resume.pdf", "CoverLetter.pdf"):
        try:
            info = subprocess.run(
                ["pdfinfo", str(folder / pdf)], capture_output=True, text=True, check=True
            )
            if "Pages:           2" in info.stdout or "Pages:           3" in info.stdout:
                return "pdfs_issues", blocks + ["multi_page_pdf"]
        except Exception:
            return "pdfs_issues", blocks + ["pdfinfo_fail"]
    if blocks or not qa_ok:
        return "pdfs_issues", blocks
    return "clean", []


def fix_lint_text(text: str) -> str:
    out = text
    for bad, good in BUZZWORD_REPLACEMENTS.items():
        out = re.sub(re.escape(bad), good, out, flags=re.IGNORECASE)
    out = re.sub(r"I am excited about[^.]*\.", "", out, flags=re.IGNORECASE)
    out = re.sub(r"—|--", ",", out)
    return out


def trim_cover_letter(folder: Path, max_chars: int = 2750) -> None:
    cl = folder / "CoverLetter.md"
    if not cl.exists():
        return
    text = cl.read_text(encoding="utf-8")
    if len(text) <= max_chars:
        return
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    while len("\n\n".join(paras)) > max_chars and len(paras) > 3:
        paras.pop(-2)
    trimmed = "\n\n".join(paras)
    if len(trimmed) > max_chars:
        trimmed = trimmed[: max_chars - 3].rsplit(" ", 1)[0] + "."
    cl.write_text(trimmed, encoding="utf-8")


def lint_fix_company(company: str) -> list[str]:
    folder = SUB / slug(company)
    for doc in ("Resume.md", "CoverLetter.md"):
        path = folder / doc
        if path.exists():
            fixed = fix_lint_text(path.read_text(encoding="utf-8"))
            path.write_text(fixed, encoding="utf-8")
    trim_cover_letter(folder)
    compile_pdfs(company, folder)
    return verify_company(company, folder)


def redraft_company(company: str, job_id: str, score: int, summary: str, jd: str) -> list[str]:
    folder = SUB / slug(company)
    for name in ("Resume.md", "CoverLetter.md", "Resume.pdf", "CoverLetter.pdf"):
        p = folder / name
        if p.exists():
            p.unlink()
    force_draft(company, jd, int(score), summary or "")
    compile_pdfs(company, folder)
    trim_cover_letter(folder)
    compile_pdfs(company, folder)
    return verify_company(company, folder)


def main() -> int:
    assert_applyr_host()
    manifest: list[list] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_company = {m[0]: m for m in manifest}
    conn = sqlite3.connect(DB)

    promoted = []
    fixed = []
    redrafted = []
    still_fail = []

    for company, job_id, score in manifest:
        kind, detail = folder_state(company)
        if kind == "clean":
            conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
            promoted.append(company)

    conn.commit()
    print(f"Promoted {len(promoted)} to Drafted:")
    for c in promoted:
        print(f"  {c}")

    for company in REDRAFT_COMPANIES:
        if company not in by_company:
            continue
        job_id, score = by_company[company][1], by_company[company][2]
        row = conn.execute(
            "SELECT jd_text, summary FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not row or not row[0]:
            still_fail.append((company, "no jd"))
            continue
        print(f"\nRedrafting {company}...")
        try:
            errs = redraft_company(company, job_id, score, row[1] or "", row[0])
            if errs:
                conn.execute("UPDATE jobs SET status='Needs Retry' WHERE id=?", (job_id,))
                still_fail.append((company, "; ".join(errs)))
                print(f"  FAIL: {errs}")
            else:
                conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
                redrafted.append(company)
                print("  OK")
        except Exception as exc:
            conn.execute("UPDATE jobs SET status='Needs Retry' WHERE id=?", (job_id,))
            still_fail.append((company, str(exc)[:200]))
            print(f"  ERROR: {exc}")
        conn.commit()
        time.sleep(1)

    lint_targets = [
        company
        for company, job_id, score in manifest
        if company not in REDRAFT_COMPANIES and folder_state(company)[0] == "pdfs_issues"
    ]

    for company in lint_targets:
        job_id = by_company[company][1]
        print(f"\nLint-fix {company}...")
        try:
            errs = lint_fix_company(company)
            if errs:
                conn.execute("UPDATE jobs SET status='Needs Retry' WHERE id=?", (job_id,))
                still_fail.append((company, "; ".join(errs)))
                print(f"  FAIL: {errs}")
            else:
                conn.execute("UPDATE jobs SET status='Drafted' WHERE id=?", (job_id,))
                fixed.append(company)
                print("  OK")
        except Exception as exc:
            conn.execute("UPDATE jobs SET status='Needs Retry' WHERE id=?", (job_id,))
            still_fail.append((company, str(exc)[:200]))
            print(f"  ERROR: {exc}")
        conn.commit()

    conn.close()
    print(f"\n=== SUMMARY ===")
    print(f"Promoted: {len(promoted)}")
    print(f"Lint-fixed -> Drafted: {len(fixed)}")
    print(f"Redrafted -> Drafted: {len(redrafted)}")
    print(f"Still failing: {len(still_fail)}")
    for c, e in still_fail:
        print(f"  {c}: {e}")
    return 0 if not still_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
