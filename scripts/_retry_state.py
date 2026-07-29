import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite")
for co in ["Tivity Health", "UKG", "Ottimate"]:
    r = c.execute(
        "SELECT id, company, title, url, status, length(coalesce(jd_text,'')), score, retry_count FROM jobs WHERE company=? ORDER BY rowid DESC LIMIT 1",
        (co,),
    ).fetchone()
    print(r)
c.close()
