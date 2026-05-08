import sqlite3
import os

db_path = "jobagent.sqlite"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE company LIKE '%Case IQ%'")
    conn.commit()
    print(f"Deleted {cursor.rowcount} jobs related to Case IQ from database.")
    conn.close()
else:
    print("No SQLite DB found.")
