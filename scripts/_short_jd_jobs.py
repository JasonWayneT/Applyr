import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite")
rows = c.execute(
    """
    SELECT company, title, url, status, length(coalesce(jd_text,'')) as jd_len, id
    FROM jobs
    WHERE status = 'Drafted' AND length(coalesce(jd_text,'')) < 800
    ORDER BY company
    """
).fetchall()
for r in rows:
    print(r)
c.close()
