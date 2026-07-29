#!/usr/bin/env python3
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sub = ROOT / "data/submissions"
conn = sqlite3.connect(ROOT / "data/jobagent.sqlite")
conn.row_factory = sqlite3.Row

ss = conn.execute("SELECT * FROM system_status WHERE id='global'").fetchone()
print("=== SYSTEM ===")
print(f"  status: {ss['status']}")
print(f"  current: {ss['current_item']}")

print("\n=== QUEUE COUNTS ===")
for row in conn.execute(
    "SELECT status, COUNT(*) c FROM jobs GROUP BY status ORDER BY c DESC"
):
    if row["status"] in (
        "Backlog", "Drafted", "Needs Retry", "Applied", "Rejected", "Closed"
    ):
        print(f"  {row['status']}: {row['c']}")

manifest = []
mp = ROOT / "data/csv_batch2_manifest.json"
if mp.exists():
    manifest = json.loads(mp.read_text())

sys.path.insert(0, str(ROOT / "scripts"))
from submission_linter import lint_document
from quality_checker import check_resume

def folder_state(company):
    slug = re.sub(r"[\W_]+", "_", company).strip("_").lower()
    folder = sub / slug
    if not folder.exists():
        return folder, "empty", []
    pdfs = {f.name for f in folder.glob("*.pdf")}
    if "Resume.pdf" in pdfs and "CoverLetter.pdf" in pdfs:
        blocks = []
        for doc in ("Resume.md", "CoverLetter.md"):
            p = folder / doc
            if p.exists():
                r = lint_document(p.read_text(encoding="utf-8"), filename=doc)
                blocks += [b.rule_id for b in r.blocks]
        qa_ok = True
        if (folder / "Resume.md").exists():
            try:
                qa_ok, _ = check_resume(str(folder / "Resume.md"))
            except Exception:
                qa_ok = False
        if blocks or not qa_ok:
            return folder, "pdfs_issues", blocks
        return folder, "clean", []
    if list(folder.glob("*.md")):
        return folder, "partial", []
    return folder, "empty", []

if manifest:
    clean, pdf_issues, partial, empty = [], [], [], []
    print(f"\n=== BATCH2 ({len(manifest)} jobs) ===")
    for company, jid, score in manifest:
        st = conn.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()
        status = st["status"] if st else "?"
        _, kind, detail = folder_state(company)
        if kind == "clean":
            clean.append((company, status, score))
        elif kind == "pdfs_issues":
            pdf_issues.append((company, status, score, detail))
        elif kind == "partial":
            partial.append((company, status, score))
        else:
            empty.append((company, status, score))

    print(f"  Clean apply-ready: {len(clean)}")
    for c in clean:
        print(f"    {c[0]} (DB:{c[1]}, score {c[2]})")
    print(f"  PDFs but lint/QA issues: {len(pdf_issues)}")
    for c in pdf_issues:
        print(f"    {c[0]} (DB:{c[1]}) lint={c[3]}")
    print(f"  Partial (no full PDFs): {len(partial)}")
    for c in partial:
        print(f"    {c[0]} (DB:{c[1]})")
    print(f"  Empty / failed: {len(empty)}")
    for c in empty:
        print(f"    {c[0]} (DB:{c[1]})")

conn.close()
