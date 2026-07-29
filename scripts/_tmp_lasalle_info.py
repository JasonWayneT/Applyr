#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
conn = sqlite3.connect(DB)
c = conn.cursor()
for row in c.execute(
    "SELECT id, company, title, status, score, url, length(COALESCE(jd_text,'')) "
    "FROM jobs WHERE company LIKE '%LaSalle%'"
):
    print(row)
conn.close()
