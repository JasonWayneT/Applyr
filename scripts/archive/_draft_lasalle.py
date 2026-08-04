#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import os
import sqlite3
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from applyr_python import assert_applyr_host
from drafting_engine import run_drafting_engine
from utils import WORK_EXP_FILE, init_pipeline_prefs, load_file

JOB_ID = "64245a1a-403f-483d-a235-7003408e4692"

def main() -> int:
    assert_applyr_host()
    init_pipeline_prefs()
    db = sqlite3.connect(os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite"))
    row = db.execute("SELECT jd_text FROM jobs WHERE id=?", (JOB_ID,)).fetchone()
    db.close()
    jd = row[0]
    work_exp = load_file(WORK_EXP_FILE)
    result = {
        "Score": 78,
        "Decision": "YES",
        "Summary": "User override: healthcare RCM platform PM; B2B SaaS ops and cross-functional delivery.",
    }
    run_drafting_engine("lasalle_network", jd, work_exp, result, display_name="LaSalle Network")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
