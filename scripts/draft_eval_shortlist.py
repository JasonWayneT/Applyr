#!/usr/bin/env python3
"""Force-draft shortlist tier-1 + Business Wire (user override scores)."""
from __future__ import annotations

import os
import sqlite3
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from applyr_python import assert_applyr_host
from drafting_engine import run_drafting_engine
from utils import WORK_EXP_FILE, init_pipeline_prefs, load_file

DRAFTS = [
    {
        "company": "Business Wire",
        "folder": "business_wire",
        "score": 75,
        "summary": "Network referral — platform PM in media distribution; Cision adjacency.",
    },
    {
        "company": "Avetta",
        "folder": "avetta",
        "score": 78,
        "summary": "B2B compliance/supplier-risk SaaS; discovery and cross-functional platform delivery.",
    },
    {
        "company": "Endava",
        "folder": "endava",
        "score": 88,
        "summary": "Healthcare kidney-care digital platform PM; regulated cross-functional delivery.",
    },
    {
        "company": "Donorbox",
        "folder": "donorbox",
        "score": 76,
        "summary": "Data-model-heavy B2B CRM; segmentation, data quality, and platform stewardship.",
    },
]


def main() -> int:
    assert_applyr_host()
    init_pipeline_prefs()
    db_path = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
    conn = sqlite3.connect(db_path)
    work_exp = load_file(WORK_EXP_FILE)
    ok, fail = [], []

    for item in DRAFTS:
        company = item["company"]
        row = conn.execute(
            "SELECT id, jd_text, url FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1",
            (company,),
        ).fetchone()
        if not row or not row[1]:
            fail.append((company, "missing jd_text"))
            continue
        job_id, jd_text, _url = row
        print(f"\n>>> Drafting {company} (job_id={job_id[:8]})")
        try:
            result = {
                "Score": item["score"],
                "Decision": "YES",
                "Summary": item["summary"],
            }
            run_drafting_engine(company, jd_text, work_exp, result, display_name=company)
            conn.execute(
                "UPDATE jobs SET status = 'Drafted', score = ?, summary = ? WHERE id = ?",
                (item["score"], item["summary"], job_id),
            )
            conn.commit()
            ok.append(company)
        except Exception as exc:
            fail.append((company, str(exc)[:200]))
        time.sleep(2)

    conn.close()
    print(f"\nDone: {len(ok)} ok, {len(fail)} failed")
    for c in ok:
        print(f"  OK   {c}")
    for c, m in fail:
        print(f"  FAIL {c}: {m}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
