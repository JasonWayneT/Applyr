import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
names = ["Counsel Health", "Guild Education", "GoGuardian"]
conn = sqlite3.connect(DB)
for n in names:
    conn.execute("UPDATE jobs SET status = ? WHERE company = ?", ("Drafted", n))
    print("Drafted:", n)
rows = conn.execute(
    "SELECT company, status, score FROM jobs WHERE company IN (?,?,?,?)",
    (*names, "Clever"),
).fetchall()
print("DB:", rows)
conn.commit()
conn.close()
