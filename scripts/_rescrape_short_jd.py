import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"
IDS = [
    "53381fed-756c-4b78-bd38-e4a5091009b6",
    "91ac1f28-f232-4e85-8507-4c9ccf2796fa",
    "d7e0a0a5-dd61-4deb-97c2-db7fa3fc2bf3",
]

c = sqlite3.connect(DB)
for job_id in IDS:
    c.execute(
        "UPDATE jobs SET status = 'New', jd_text = NULL WHERE id = ?",
        (job_id,),
    )
    row = c.execute("SELECT company FROM jobs WHERE id = ?", (job_id,)).fetchone()
    print(f"Re-queued {row[0] if row else job_id} -> New")
c.commit()
c.close()
