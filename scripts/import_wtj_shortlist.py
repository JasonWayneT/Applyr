#!/usr/bin/env python3
"""Import WTJ shortlist into jobs DB."""
import csv
import re
import sqlite3
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "data" / "jobagent.sqlite"
CSV_PATH = Path(r"C:\Users\Jason\Downloads\WTJ - Sheet1.csv")
JOBS_DIR = PROJECT_ROOT / "jobs"

KEEP = {
    "Counsel": {"score": 85, "summary": "B2B2C healthcare platform; partner APIs and patient experience."},
    "Guild": {"score": 80, "summary": "Ed-tech B2B enterprise; learner experience and platform delivery."},
    "GoGuardian": {"score": 78, "summary": "Ed-tech B2B SaaS for K-12; transferable platform PM craft."},
    "Clever": {"score": 78, "summary": "Ed-tech experiences platform; integrations and user flows."},
}


def sanitize(name: str) -> str:
    return re.sub(r"[\W_]+", "_", name).strip("_")


def load_wttj_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        for raw in csv.reader(f):
            if not raw or not (raw[0] or "").strip():
                continue
            jd = raw[0].strip()
            first_line = jd.split("\n", 1)[0].strip()
            follow = re.search(r"Follow\s+(\S+)", jd)
            company = follow.group(1) if follow else ""
            if not company and "," in first_line:
                company = first_line.rsplit(",", 1)[-1].strip()
            rows.append(
                {
                    "company": company or "Unknown",
                    "position": first_line,
                    "url": "",
                    "jd": jd,
                }
            )
    return rows


def match_company(row_company: str) -> str | None:
    c = row_company.lower()
    for key in KEEP:
        if key.lower() in c or c.startswith(key.lower()):
            return key
    return None


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
    all_rows = load_wttj_rows(str(CSV_PATH))
    by_key: dict[str, dict] = {}
    for row in all_rows:
        key = match_company(row["company"])
        if key and key not in by_key:
            by_key[key] = {**row, "db_company": key}

    conn = sqlite3.connect(DB)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    for key, meta in KEEP.items():
        row = by_key.get(key)
        if not row:
            print(f"MISSING CSV row: {key}")
            continue
        display = {
            "Counsel": "Counsel Health",
            "Guild": "Guild Education",
            "GoGuardian": "GoGuardian",
            "Clever": "Clever",
        }[key]
        url = row["url"] or f"local://{sanitize(key)}_{uuid.uuid4().hex[:8]}"
        existing = conn.execute(
            "SELECT id, rowid FROM jobs WHERE company = ? OR company = ? ORDER BY rowid DESC LIMIT 1",
            (key, display),
        ).fetchone()
        if existing:
            job_id, rowid = existing
            conn.execute(
                """UPDATE jobs SET company=?, title=?, url=?, jd_text=?, status='Backlog',
                   score=?, summary=? WHERE id=?""",
                (display, row["position"], url, row["jd"], meta["score"], meta["summary"], job_id),
            )
            sync_fts(conn, rowid)
            print(f"updated {display}")
        else:
            job_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO jobs (id, company, title, url, status, jd_text, score, summary, retry_count)
                   VALUES (?, ?, ?, ?, 'Backlog', ?, ?, ?, 0)""",
                (job_id, display, row["position"], url, row["jd"], meta["score"], meta["summary"]),
            )
            rowid = conn.execute("SELECT rowid FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            sync_fts(conn, rowid)
            print(f"added {display}")
        slug = sanitize(display)
        staging = JOBS_DIR / f"{slug}_{job_id[:8]}.txt"
        staging.write_text(
            f"Title: {row['position']}\nURL: {url}\n\n{row['jd']}", encoding="utf-8"
        )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
