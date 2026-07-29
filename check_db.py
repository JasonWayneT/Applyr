import sqlite3
import os

db_path = os.path.join("data", "jobagent.sqlite")
if not os.path.exists(db_path):
    print("No DB")
else:
    conn = sqlite3.connect(db_path)
    res = conn.execute("SELECT status FROM jobs WHERE lower(company) LIKE '%doppel%'").fetchall()
    print(res)
