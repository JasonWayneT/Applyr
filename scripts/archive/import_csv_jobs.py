# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import csv
import os
import sys
import sqlite3
import uuid
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_id():
    return uuid.uuid4().hex[:8]


def sanitize_filename(name):
    return re.sub(r'[\W_]+', '_', name).strip('_')


def _is_weak_job_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return "linkedin.com/jobs/search" in u or "currentjobid=" in u and "search-results" in u


def _format_staging_jd(position: str, url: str, jd: str) -> str:
    parts = []
    if position:
        parts.append(f"Title: {position}")
    if url:
        parts.append(f"URL: {url}")
    if parts:
        parts.append("")
    parts.append(jd)
    return "\n".join(parts)


def import_jobs(csv_paths):
    """
    Import jobs from one or more CSV files into the pipeline.
    Each CSV must have columns: Company, Position, URL (optional), Job Description
    """
    db_path = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
    jobs_dir = os.path.join(PROJECT_ROOT, "jobs")
    os.makedirs(jobs_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported_count = 0
    weak_urls = 0

    for csv_path in csv_paths:
        if not os.path.exists(csv_path):
            print(f"[Skip] File not found: {csv_path}")
            continue

        print(f"Processing {csv_path}...")
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get('Company', '').strip()
                position = row.get('Position', '').strip()
                url = row.get('URL', '').strip()
                jd = row.get('Job Description', '').strip()

                if not company or not jd:
                    continue

                if not url:
                    url = f"local://{sanitize_filename(company)}_{get_id()}"
                elif _is_weak_job_url(url):
                    weak_urls += 1
                    print(f"  [Warn] Weak job URL (search page?): {company} — {url[:80]}...")

                cursor.execute("SELECT id FROM jobs WHERE url = ?", (url,))
                if cursor.fetchone():
                    continue

                job_id = get_id()
                try:
                    cursor.execute(
                        "INSERT INTO jobs (id, company, title, url, status) VALUES (?, ?, ?, ?, 'New')",
                        (job_id, company, position, url)
                    )
                    slug = sanitize_filename(company)
                    txt_filename = f"{slug}_{job_id}.txt"
                    with open(os.path.join(jobs_dir, txt_filename), 'w', encoding='utf-8') as jf:
                        jf.write(_format_staging_jd(position, url, jd))
                    imported_count += 1
                except sqlite3.IntegrityError:
                    pass

    conn.commit()
    conn.close()
    print(f"Successfully imported {imported_count} new jobs into the pipeline.")
    if weak_urls:
        print(f"  {weak_urls} row(s) had LinkedIn search URLs — consider replacing with direct job links.")


if __name__ == "__main__":
    from applyr_python import assert_applyr_host
    try:
        assert_applyr_host()
    except Exception as exc:
        print(f"CRITICAL: {exc}", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) > 1:
        paths = sys.argv[1:]
    else:
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        candidates = [
            "Job Evaluation 1 - Sheet1.csv",
            "Job Evaluation 1 - Sheet1 (1).csv",
            "Job Evaluation 2 - Sheet1.csv",
        ]
        paths = [os.path.join(downloads, f) for f in candidates if os.path.exists(os.path.join(downloads, f))]
        if not paths:
            print("No CSV files found. Pass file paths as arguments:")
            print('  node scripts/invoke_applyr_python.mjs scripts/import_csv_jobs.py "path/to/jobs.csv"')
            sys.exit(1)

    import_jobs(paths)
