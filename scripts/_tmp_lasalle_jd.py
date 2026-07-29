#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
conn = sqlite3.connect(DB)
row = conn.execute(
    "SELECT jd_text FROM jobs WHERE company LIKE '%LaSalle%'"
).fetchone()
if row:
    print(row[0])
conn.close()
