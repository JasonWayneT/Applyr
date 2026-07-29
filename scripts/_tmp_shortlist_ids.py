#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
conn = sqlite3.connect(DB)
for name in ("Business Wire", "Avetta", "Endava", "Donorbox"):
    row = conn.execute(
        "SELECT id, company, title, status, score, LENGTH(jd_text) FROM jobs WHERE company = ?",
        (name,),
    ).fetchone()
    print(row)
conn.close()
