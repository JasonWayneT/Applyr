#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Import + extract JDs from applyr_jobs CSV batch for drafting."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
FILES = [
    Path(r"C:\Users\Jason\Downloads\applyr_jobs.csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (3).csv"),
]

# Human-curated from eval — excludes recruiter wrappers, people-mgmt, AI-lead, contract-only
TIER1 = [
    ("Amplify", 78, "Ed-tech classroom platform; contact at company. PK-5 literacy product area."),
    ("Protege", 82, "Data ingestion and quality platform; partner pipelines and catalog readiness."),
    ("Insulet Corporation", 80, "Healthcare cloud/data platform PM for connected devices."),
    ("Follett Software", 78, "Ed-tech K-12 software; senior platform PM."),
    ("IntegriChain", 76, "Pharma commercial data; senior PM."),
    ("Bitsight Technologies", 77, "B2B SaaS ecosystems and technical alliances."),
    ("Affinity.co", 76, "Senior PM CRM; relationship intelligence platform."),
    ("Tekion", 74, "Automotive enterprise cloud; OEM integrations and platform."),
]

TIER2 = [
    ("Globe Life", 68, "Insurance B2B PM II; backlog and roadmap delivery."),
    ("Vector Solutions", 66, "Ed-tech compliance and training software."),
    ("PAR Technology", 68, "Restaurant/hospitality platform PM."),
    ("Acquia", 72, "Senior PM; enterprise SaaS (verify role focus)."),
]


def parse_title(jd: str) -> str:
    m = re.search(r"^Title:\s*(.+)$", jd, re.M)
    return m.group(1).strip() if m else jd.split("\n", 1)[0].strip()[:120]


def load_all() -> dict[str, dict]:
    by_company: dict[str, dict] = {}
    for fp in FILES:
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8-sig", errors="ignore") as f:
            for row in csv.DictReader(f):
                company = (row.get("Company") or "").strip()
                jd = (row.get("Job Description") or "").strip()
                url = (row.get("URL") or "").strip()
                if not company or not jd:
                    continue
                key = company.lower()
                if key not in by_company or len(jd) > len(by_company[key]["jd"]):
                    by_company[key] = {
                        "company": company,
                        "title": parse_title(jd),
                        "url": url,
                        "jd": jd,
                    }
    return by_company


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


def slug(company: str) -> str:
    return re.sub(r"[\W_]+", "_", company).strip("_").lower()


def main() -> None:
    rows = load_all()
    conn = sqlite3.connect(DB)
    sub_base = PROJECT_ROOT / "data" / "submissions"

    for company, score, summary in TIER1 + TIER2:
        data = rows.get(company.lower())
        if not data:
            print(f"MISSING: {company}")
            continue
        existing = conn.execute(
            "SELECT id, rowid, status FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()
        url = data["url"] or f"local://{slug(company)}_{uuid.uuid4().hex[:8]}"
        if existing:
            job_id, rowid, status = existing
            conn.execute(
                """UPDATE jobs SET title=?, url=?, jd_text=?, score=?, summary=?,
                   status=CASE WHEN status IN ('Applied','Closed') THEN status ELSE 'Backlog' END
                   WHERE id=?""",
                (data["title"], url, data["jd"], score, summary, job_id),
            )
            sync_fts(conn, rowid)
            print(f"updated {company} ({status})")
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

        folder = sub_base / slug(company)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Original_JD.txt").write_text(data["jd"], encoding="utf-8")

    conn.commit()
    conn.close()
    print("done")


if __name__ == "__main__":
    main()
