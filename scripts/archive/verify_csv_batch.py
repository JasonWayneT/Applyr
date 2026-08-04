#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Verify and compile all CSV batch submissions; mark Drafted."""
from __future__ import annotations

import subprocess
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT_ROOT / "scripts"
PY = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"

COMPANIES = [
    ("Amplify", "amplify"),
    ("Protege", "protege"),
    ("Insulet Corporation", "insulet_corporation"),
    ("Follett Software", "follett_software"),
    ("IntegriChain", "integrichain"),
    ("Bitsight Technologies", "bitsight_technologies"),
    ("Affinity.co", "affinity_co"),
    ("Tekion", "tekion"),
    ("Globe Life", "globe_life"),
    ("Vector Solutions", "vector_solutions"),
    ("PAR Technology", "par_technology"),
    ("Acquia", "acquia"),
]


def main() -> None:
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from quality_checker import check_resume
    from submission_linter import lint_document

    conn = sqlite3.connect(DB)
    ok, fail = [], []

    for company, folder in COMPANIES:
        base = PROJECT_ROOT / "data" / "submissions" / folder
        print(f"\n=== {company} ===")
        if not (base / "Resume.md").exists():
            fail.append((company, "missing Resume.md"))
            print("  MISSING files")
            continue
        for doc in ("Resume.md", "CoverLetter.md"):
            text = (base / doc).read_text(encoding="utf-8")
            r = lint_document(text, filename=doc)
            blocks = [b.rule_id for b in r.blocks]
            if blocks:
                print(f"  LINT BLOCK {doc}: {blocks}")
                fail.append((company, f"lint {doc} {blocks}"))
        qa_ok, qa_msg = check_resume(str(base / "Resume.md"))
        if not qa_ok:
            print(f"  QA FAIL: {qa_msg}")
            fail.append((company, qa_msg))
        else:
            print("  QA pass")
        for md, pdf in (("Resume.md", "Resume.pdf"), ("CoverLetter.md", "CoverLetter.pdf")):
            subprocess.run(
                [str(PY), str(SCRIPTS / "compile_single.py"), str(base / md), str(base / pdf)],
                check=True,
                cwd=str(SCRIPTS),
            )
            info = subprocess.run(
                ["pdfinfo", str(base / pdf)], capture_output=True, text=True, check=True
            )
            pages = [l for l in info.stdout.splitlines() if "Pages" in l]
            print(f"  {pdf}: {pages[0] if pages else '?'}")
            if "Pages:           2" in info.stdout or "Pages:           3" in info.stdout:
                fail.append((company, f"{pdf} multi-page"))
        conn.execute("UPDATE jobs SET status = 'Drafted' WHERE company = ?", (company,))
        ok.append(company)

    conn.commit()
    conn.close()
    print(f"\nOK: {len(ok)} | FAIL: {len(fail)}")
    for f in fail:
        print(" ", f)


if __name__ == "__main__":
    main()
