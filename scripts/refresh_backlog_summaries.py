"""
One-time refresh of Backlog job summaries (FR-107 / CR-018).
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_pipeline import _draft_success_summary, _resolve_display_company

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
SUBMISSIONS = os.path.join(PROJECT_ROOT, "data", "submissions")


def _fit_from_manifest(company_slug: str) -> str:
    manifest_path = os.path.join(SUBMISSIONS, company_slug, "draft_manifest.json")
    if not os.path.exists(manifest_path):
        return ""
    try:
        with open(manifest_path, encoding="utf-8") as f:
            m = json.load(f)
        themes = (m.get("jd_profile") or {}).get("priority_themes") or []
        if themes:
            return f"JD themes: {', '.join(themes[:2])}."
    except (json.JSONDecodeError, OSError):
        pass
    return ""


def main():
    if not os.path.exists(DB):
        print("No jobagent.sqlite")
        return
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT id, company, score, summary FROM jobs WHERE status = 'Backlog'"
    ).fetchall()
    updated = 0
    for job_id, company, score, old_summary in rows:
        display = _resolve_display_company(DB, company, job_id)
        slug = company.lower().replace(" ", "_")
        fit_hint = _fit_from_manifest(slug)
        if not fit_hint and old_summary and "Asset drafting failed" not in old_summary:
            fit_hint = (old_summary or "")[:200]
        new_summary = _draft_success_summary(int(score or 0), display, fit_hint)
        conn.execute(
            "UPDATE jobs SET summary = ? WHERE id = ?",
            (new_summary, job_id),
        )
        updated += 1
        print(f"  {company}: {new_summary[:80]}...")
    conn.commit()
    conn.close()
    print(f"Updated {updated} Backlog summaries.")


if __name__ == "__main__":
    main()
