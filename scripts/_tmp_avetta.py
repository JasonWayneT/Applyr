import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite")
r = c.execute(
    "SELECT title, status, score, summary, jd_text FROM jobs WHERE company LIKE '%Avetta%'"
).fetchone()
if r:
    print("title:", r[0])
    print("status:", r[1])
    print("score:", r[2])
    print("summary:", r[3])
    print("---JD---")
    print(r[4][:3500] if r[4] else "none")
c.close()
