#!/usr/bin/env python3
"""Import soft-eval tier 1/2 shortlist from applyr_jobs (4)-(7) CSVs into Backlog."""
from __future__ import annotations

import csv
import re
import sqlite3
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
FILES = [
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (4).csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (5).csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (6).csv"),
    Path(r"C:\Users\Jason\Downloads\applyr_jobs (7).csv"),
]

# Soft-eval shortlist — BOLD explicitly skipped
TIER1 = [
    ("Tilt", 82, "Tier 1 — Platform PM (notifications/workflows); remote B2B SaaS."),
    ("OneStream Software", 80, "Tier 1 — Remote US B2B SaaS IC PM; clear ownership."),
    ("Lumos", 82, "Tier 1 — Integrations/APIs/connectors; strongest craft match."),
    ("MyTime", 78, "Tier 1 — B2B SaaS PM; 5+ years execution."),
    ("Covideo", 76, "Tier 1 — Remote US Senior PM; SaaS video messaging."),
    ("DataGrail", 78, "Tier 1 — Enterprise B2B SaaS; data-heavy product ownership."),
    ("Remote", 77, "Tier 1 — Integrations/API/platform SPM at Remote.com."),
]

TIER2 = [
    ("PAR", 70, "Tier 2 — Remote SaaS PM; pay band light ($90–120K)."),
    ("Buyers Edge Platform", 72, "Tier 2 — Remote PM; verify real product ownership vs BA."),
    ("Redox", 74, "Tier 2 — Healthcare B2B SaaS SPM; domain stretch."),
    ("Ontra", 70, "Tier 2 — Legal-tech SPM; domain stretch."),
    ("ParkingPass.com", 68, "Tier 2 — Proptech SaaS; confirm clean US-remote."),
]

# CSV company name -> shortlist key (when they differ)
ALIASES = {
    "onestream software": "OneStream Software",
    "parkingpass.com": "ParkingPass.com",
    "buyers edge platform": "Buyers Edge Platform",
}


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


def load_all() -> dict[str, dict]:
    want = {c.lower() for c, _, _ in TIER1 + TIER2}
    by_key: dict[str, dict] = {}
    for fp in FILES:
        if not fp.exists():
            print(f"MISSING FILE: {fp}")
            continue
        with open(fp, encoding="utf-8-sig", errors="ignore") as f:
            for row in csv.DictReader(f):
                company = (row.get("Company") or "").strip()
                if not company:
                    continue
                key = ALIASES.get(company.lower(), company).lower()
                if key not in want:
                    continue
                jd = (row.get("Job Description") or "").strip()
                url = (row.get("URL") or "").strip()
                position = (row.get("Position") or "").strip()
                if not jd:
                    continue
                if key not in by_key or len(jd) > len(by_key[key]["jd"]):
                    by_key[key] = {
                        "company": ALIASES.get(company.lower(), company),
                        "title": position or company,
                        "url": url,
                        "jd": jd,
                    }
    return by_key


def main() -> int:
    rows = load_all()
    missing = [c for c, _, _ in TIER1 + TIER2 if c.lower() not in rows]
    if missing:
        print(f"Missing from CSVs: {missing}")
        return 1

    conn = sqlite3.connect(DB)
    sub_base = PROJECT_ROOT / "data" / "submissions"
    jobs_dir = PROJECT_ROOT / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    for company, score, summary in TIER1 + TIER2:
        data = rows[company.lower()]
        existing = conn.execute(
            "SELECT id, rowid, status FROM jobs WHERE lower(company) = ? ORDER BY rowid DESC LIMIT 1",
            (company.lower(),),
        ).fetchone()
        url = data["url"] or f"local://{slug(company)}_{uuid.uuid4().hex[:8]}"
        title = data["title"]

        if existing:
            job_id, rowid, status = existing
            conn.execute(
                """UPDATE jobs SET title=?, url=?, jd_text=?, score=?, summary=?,
                   status=CASE WHEN status IN ('Applied','Closed','Recruiter Screen',
                     'Core Interviews','Offer and Negotiation') THEN status ELSE 'Backlog' END
                   WHERE id=?""",
                (title, url, data["jd"], score, summary, job_id),
            )
            sync_fts(conn, rowid)
            print(f"updated {company} (was {status}) -> Backlog/kept")
        else:
            job_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
                   VALUES (?, ?, ?, ?, 'Backlog', ?, ?, ?, 0)""",
                (job_id, company, title, url, data["jd"], score, summary),
            )
            rowid = conn.execute("SELECT rowid FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            sync_fts(conn, rowid)
            print(f"added {company}")

        folder = sub_base / slug(company)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "Original_JD.txt").write_text(data["jd"], encoding="utf-8")

        staging = jobs_dir / f"{slug(company)}.txt"
        staging.write_text(
            f"Title: {title}\nURL: {url}\n\n{data['jd']}",
            encoding="utf-8",
        )

    conn.commit()
    conn.close()
    print(f"done — {len(TIER1)} tier1 + {len(TIER2)} tier2 (BOLD skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
