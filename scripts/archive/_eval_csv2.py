#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import json
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from eval_applyr_jobs_csv import load_csv, quality_row, human_fit

fp = Path(r"C:\Users\Jason\Downloads\applyr_jobs (2).csv")
OUT = PROJECT_ROOT / "docs" / "reports" / "applyr-jobs-csv2-eval.md"
prefs = json.loads((PROJECT_ROOT / "data/candidate_preferences.json").read_text(encoding="utf-8"))
rows = load_csv(fp)

# Manual overrides after heuristic (Jason profile)
MANUAL_SKIP = {
    "Arcadia": "Payments/fintech PM — 3+ yrs payments required; exclusion zone",
    "Cleerly": "Clinical AI SaMD / 8+ yrs / imaging — exclusion zone",
    "RemoteHunter": "Recruiter wrapper",
    "Insight Global": "Staffing",
    "Kforce": "Staffing",
    "Ladders": "Job board / not direct employer",
}

MANUAL_TIER2 = {}

evaluated = []
for r in rows:
    q = quality_row(r["company"], r["url"], r["jd"])
    tier, score, reason = human_fit(r["company"], r["position"], r["jd"], prefs)
    co = r["company"]
    if co in MANUAL_SKIP:
        tier, reason = "skip", MANUAL_SKIP[co]
    evaluated.append({**r, **q, "tier": tier, "score": score, "fit_reason": reason})

evaluated.sort(key=lambda x: (-x["score"], x["company"]))

# Archive check
sub = PROJECT_ROOT / "data/submissions"
conn = sqlite3.connect(PROJECT_ROOT / "data/jobagent.sqlite")
conn.row_factory = sqlite3.Row

def archive_note(company: str) -> str:
    slug = re.sub(r"[\W_]+", "_", company).strip("_").lower()
    folder = sub / slug
    pdfs = folder.exists() and any(f.suffix.lower() == ".pdf" for f in folder.iterdir())
    row = conn.execute(
        "SELECT status, score FROM jobs WHERE LOWER(company) LIKE ? ORDER BY rowid DESC LIMIT 1",
        (f"%{company.split()[0].lower()}%",),
    ).fetchone()
    parts = []
    if pdfs:
        parts.append("has assets")
    if row and company.lower() in (row["status"] or "").lower() or True:
        rows2 = conn.execute(
            "SELECT status, score FROM jobs WHERE LOWER(company) = LOWER(?) ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()
        if rows2:
            parts.append(f"DB:{rows2['status']}({rows2['score']})")
    return " | ".join(parts) if parts else ""

lines = [
    "# applyr_jobs (2).csv Evaluation",
    "",
    f"**Rows:** {len(rows)}",
    "",
]
for tier_name in ("apply", "tier2", "skip"):
    bucket = [e for e in evaluated if e["tier"] == tier_name]
    lines.append(f"## {tier_name.upper()} ({len(bucket)})")
    lines.append("")
    for e in bucket:
        arch = archive_note(e["company"])
        flags = f" ⚠ `{','.join(e['issues'])}`" if e["issues"] else ""
        arch_s = f" _(archive: {arch})_" if arch else ""
        lines.append(
            f"- **{e['company']}** — {e['title'][:70]} (score ~{e['score']}) — {e['fit_reason']}{flags}{arch_s}"
        )
    lines.append("")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
for tier_name in ("apply", "tier2", "skip"):
    bucket = [e for e in evaluated if e["tier"] == tier_name]
    print(f"{tier_name}: {len(bucket)}")
    for e in bucket:
        print(f"  {e['score']} {e['company']} | {e['title'][:50]}")

conn.close()
