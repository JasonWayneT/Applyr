import shutil
import sqlite3
import os

folder_path = "submissions/cenosco"
if os.path.exists(folder_path):
    shutil.rmtree(folder_path, ignore_errors=True)
    print("Successfully removed Cenosco folder.")

db_path = "jobagent.sqlite"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE company LIKE '%Cenosco%'")
    conn.commit()
    print(f"Deleted {cursor.rowcount} jobs related to Cenosco from database.")
    conn.close()
else:
    print("No SQLite DB found.")
