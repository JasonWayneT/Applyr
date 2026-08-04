#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Import tier-1/tier-2 net-new jobs from applyr_jobs CSV exports."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
PREFS = PROJECT_ROOT / "data" / "candidate_preferences.json"
FILES = [
    Path(r"C:\Users\Jason\Downloads\applyr_jobs.csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (1).csv"),
]

# (company, score, summary) — tier 1/2 net-new; excludes archive + hard skips
BATCH = [
    ("PerformYard", 83, "B2B SaaS HR performance; 100% remote; AI-enabled platform PM."),
    ("Beyond", 75, "Short-term rental revenue management; pricing algorithm + GenAI assistant."),
    ("Ceresti Health", 83, "Healthcare dementia management platform PM."),
    ("Barti", 83, "B2B SaaS platform PM."),
    ("Cardinal Health", 83, "Healthcare specialty pharma platform PM."),
    ("Aderant", 78, "Legal industry B2B SaaS PM."),
    ("Best Egg", 78, "Financial confidence platform; senior PM scope."),
    ("Fleetio", 78, "Fleet management B2B SaaS platform PM."),
    ("Tropic", 78, "Senior PM; B2B SaaS."),
    ("Enlyte", 78, "B2B SaaS; insurance/claims adjacent."),
    ("McGraw Hill", 80, "Ed-tech publishing platform PM."),
    ("CENTEGIX", 80, "Ed-tech safety platform PM."),
    ("Sogeti", 80, "Consulting B2B; AI platform PM — verify employer vs staffing."),
    ("Cityblock Health", 78, "Healthcare senior PM; GTM-adjacent — verify IC scope."),
    ("CollegeVine", 75, "Ed-tech college admissions platform PM."),
    ("Crain Communications", 75, "Media B2B platform PM."),
    ("OpenRouter", 75, "API platform PM."),
    ("StoneEagle", 75, "B2B platform PM."),
    ("Sundayy", 75, "Senior platform PM."),
    ("Tenna", 75, "Ed-tech/construction fleet platform PM."),
    ("Intrado", 72, "Healthcare communications senior PM."),
    ("PagerDuty", 73, "Digital operations B2B SaaS senior PM."),
    ("Bloomerang", 75, "Nonprofit CRM B2B SaaS PM."),
    ("adly", 75, "Ad platform PM."),
    ("Thrivent", 69, "Financial services product manager — tier 2."),
    ("Gigawatt", 68, "Senior PM scope; tier 2."),
    ("Georgia IT, Inc.", 67, "Platform PM; tier 2 logistics stretch."),
    ("Koalafi", 65, "Fintech platform PM; tier 2 payments adjacent."),
]

SKIP_COMPANIES = {
    "Ontra", "RemoteHunter", "DMI", "Amplify", "Protege", "Insulet Corporation",
    "Affinity.co", "Globe Life", "Vector Solutions", "Endava", "Follett Software",
    "IntegriChain", "Bitsight Technologies", "Tekion", "Acquia", "PAR Technology",
    "Comscore, Inc.", "Roo",
}


def parse_title(jd: str, position: str = "") -> str:
    if position.strip():
        return position.strip()
    m = re.search(r"^Title:\s*(.+)$", jd, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r"^Job Title:\s*(.+)$", jd, re.M)
    if m:
        return m.group(1).strip()
    return jd.split("\n", 1)[0].strip()[:120]


def load_all() -> dict[str, dict]:
    by_company: dict[str, dict] = {}
    for fp in FILES:
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8-sig", errors="ignore") as f:
            for row in csv.DictReader(f):
                company = (row.get("Company") or "").strip()
                jd = (row.get("Job Description") or "").strip()
                url = (row.get("URL") or row.get("Url") or "").strip()
                position = (row.get("Position") or "").strip()
                if not company or not jd:
                    continue
                key = company.lower()
                if key not in by_company or len(jd) > len(by_company[key]["jd"]):
                    by_company[key] = {
                        "company": company,
                        "title": parse_title(jd, position),
                        "url": url,
                        "jd": jd,
                    }
    return by_company


def slug(company: str) -> str:
    return re.sub(r"[\W_]+", "_", company).strip("_").lower()


def sync_fts(conn: sqlite3.Connection, rowid: int) -> None:
    row = conn.execute(
        "SELECT company, title, summary, url FROM jobs WHERE rowid = ?", (rowid,)
    ).fetchone()
    if not row:
        return
    conn.execute("DELETE FROM jobs_fts WHERE rowid = ?", (rowid,))
    conn.execute(
        "INSERT INTO jobs_fts(rowid, company, title, summary, url) VALUES (?, ?, ?, ?, ?)",
        (rowid, row[0] or "", row[1] or "", row[2] or "", row[3] or ""),
    )


def main() -> None:
    rows = load_all()
    conn = sqlite3.connect(DB)
    sub_base = PROJECT_ROOT / "data" / "submissions"
    imported = []

    for company, score, summary in BATCH:
        if company in SKIP_COMPANIES:
            continue
        data = rows.get(company.lower())
        if not data:
            print(f"MISSING CSV: {company}")
            continue

        existing = conn.execute(
            "SELECT id, rowid, status FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()

        # Skip if already applied with assets
        folder = sub_base / slug(company)
        has_pdfs = folder.exists() and any(
            f.suffix.lower() == ".pdf" for f in folder.iterdir() if f.is_file()
        )
        if existing and existing[2] == "Applied" and has_pdfs:
            print(f"SKIP (applied): {company}")
            continue

        url = data["url"] or f"local://{slug(company)}_{uuid.uuid4().hex[:8]}"
        if existing:
            job_id, rowid, status = existing
            if status in ("Applied", "Closed"):
                conn.execute(
                    """UPDATE jobs SET title=?, url=?, jd_text=?, score=?, summary=?,
                       status='Backlog', rejection_type=NULL, rejection_stage=NULL, outcome_notes=NULL
                       WHERE id=?""",
                    (data["title"], url, data["jd"], score, summary, job_id),
                )
            else:
                conn.execute(
                    """UPDATE jobs SET title=?, url=?, jd_text=?, score=?, summary=?,
                       status='Backlog' WHERE id=?""",
                    (data["title"], url, data["jd"], score, summary, job_id),
                )
            sync_fts(conn, rowid)
            print(f"updated {company} -> Backlog")
        else:
            job_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
                   VALUES (?, ?, ?, ?, 'Backlog', ?, ?, ?, 0)""",
                (job_id, company, data["title"], url, data["jd"], score, summary),
            )
            rowid = conn.execute("SELECT rowid FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            sync_fts(conn, rowid)
            print(f"added {company}")

        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Original_JD.txt").write_text(data["jd"], encoding="utf-8")
        imported.append((company, job_id if not existing else existing[0], score))

    conn.commit()
    conn.close()
    manifest = PROJECT_ROOT / "data" / "csv_batch2_manifest.json"
    manifest.write_text(json.dumps(imported, indent=2), encoding="utf-8")
    print(f"Imported {len(imported)} jobs. Manifest: {manifest}")


if __name__ == "__main__":
    main()
