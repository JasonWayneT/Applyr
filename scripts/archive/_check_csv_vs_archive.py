#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Cross-check CSV recommendations against DB + submission folders."""
from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
SUBMISSIONS = PROJECT_ROOT / "data" / "submissions"
ARCHIVE = PROJECT_ROOT / "data" / "archive" / "submissions"

RECOMMENDED = [
    ("Amplify", "apply"),
    ("Protege", "apply"),
    ("Insulet Corporation", "apply"),
    ("Affinity.co", "apply"),
    ("Tropic", "apply"),
    ("Fleetio", "apply"),
    ("Aderant", "apply"),
    ("PagerDuty", "apply"),
    ("McGraw Hill", "apply"),
    ("CollegeVine", "apply"),
    ("Bloomerang", "apply"),
    ("Cityblock Health", "apply"),
    ("Ceresti Health", "apply"),
    ("Globe Life", "tier2"),
    ("Vector Solutions", "tier2"),
    ("Gigawatt", "tier2"),
    ("Koalafi", "tier2"),
    ("Best Egg", "apply"),
    ("Enlyte", "apply"),
    ("Beyond", "apply"),
    ("Rithum", "apply"),
    ("StoneEagle", "apply"),
    ("Sundayy", "apply"),
    ("Tenna", "apply"),
    ("OpenRouter", "apply"),
    ("Crain Communications", "apply"),
    ("adly", "apply"),
    ("Intrado", "apply"),
    ("Barti", "apply"),
    ("Cardinal Health", "apply"),
    ("CENTEGIX", "apply"),
    ("Endava", "apply"),
]


def norm(s: str) -> str:
    return (s or "").lower().replace(".", "").replace(",", "").replace("_", " ").strip()


def folder_assets(folder: Path) -> dict:
    if not folder.is_dir():
        return {"exists": False, "pdfs": [], "has_resume": False, "has_cover": False}
    files = list(folder.iterdir())
    pdfs = [f.name for f in files if f.suffix.lower() == ".pdf"]
    mds = [f.name for f in files if f.suffix.lower() == ".md"]
    return {
        "exists": True,
        "pdfs": pdfs,
        "has_resume": any("resume" in f.lower() for f in pdfs + mds),
        "has_cover": any("cover" in f.lower() for f in pdfs + mds),
        "has_jd": any(f.lower() == "original_jd.txt" for f in [x.name for x in files]),
    }


def find_folder(company: str) -> tuple[Path | None, str]:
    slug = company.lower().replace(".", "").replace(" ", "_").replace(",", "")
    candidates = [
        SUBMISSIONS / slug,
        SUBMISSIONS / slug.replace("_", ""),
        ARCHIVE / slug,
        ARCHIVE / slug.replace("_", ""),
    ]
    # fuzzy scan
    for base in (SUBMISSIONS, ARCHIVE):
        if not base.exists():
            continue
        for d in base.iterdir():
            if not d.is_dir():
                continue
            dn = norm(d.name.replace("_", " "))
            if norm(company) in dn or dn in norm(company) or norm(company).split()[0] in dn:
                candidates.insert(0, d)
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if c.exists():
            loc = "submissions" if "submissions" in str(c) else "archive"
            return c, loc
    return None, ""


def match_db(company: str, rows: list[sqlite3.Row]) -> list[dict]:
    nc = norm(company)
    hits = []
    for r in rows:
        rc = norm(r["company"])
        if nc == rc or nc in rc or rc in nc:
            hits.append(dict(r))
        elif nc.split()[0] == rc.split()[0] and len(nc.split()[0]) > 3:
            hits.append(dict(r))
    return hits


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    db_rows = conn.execute(
        "SELECT id, company, title, status, score, url FROM jobs ORDER BY company"
    ).fetchall()
    conn.close()

    print("CSV RECOMMENDATION vs ARCHIVE/DB")
    print("=" * 72)
    already = []
    partial = []
    new = []

    for company, tier in RECOMMENDED:
        db_hits = match_db(company, db_rows)
        folder, loc = find_folder(company)
        assets = folder_assets(folder) if folder else {"exists": False}

        status_note = ""
        if db_hits:
            best = db_hits[0]
            status_note = f"DB: {best['status']} (score {best['score']}) — {best['title'][:45]}"
        if assets.get("exists"):
            pdf_note = ", ".join(assets["pdfs"]) if assets["pdfs"] else "no PDFs"
            status_note += f" | {loc}: {pdf_note}"

        if assets.get("has_resume") and assets.get("has_cover"):
            bucket = already
            label = "HAVE ASSETS"
        elif db_hits and db_hits[0]["status"] in ("Applied", "Backlog", "Drafted"):
            bucket = partial
            label = "IN PIPELINE"
        elif db_hits and db_hits[0]["status"] == "Closed":
            bucket = partial
            label = "CLOSED IN DB"
        else:
            bucket = new
            label = "NEW"

        bucket.append((company, tier, label, status_note or "not in DB / no folder"))
        print(f"[{label:14}] {company:22} ({tier}) — {status_note or 'not found'}")

    print()
    print(f"Summary: {len(already)} have assets | {len(partial)} in pipeline/closed | {len(new)} net-new")

    if SUBMISSIONS.exists():
        print(f"\nAll submission folders ({SUBMISSIONS}):")
        for d in sorted(SUBMISSIONS.iterdir()):
            if d.is_dir():
                a = folder_assets(d)
                print(f"  {d.name}: pdfs={a['pdfs']}")


if __name__ == "__main__":
    main()
