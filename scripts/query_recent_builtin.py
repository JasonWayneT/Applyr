import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("jobagent.sqlite")
rows = conn.execute(
    """
    SELECT company, title, status, score, pre_score,
           length(jd_text) as jd_len, extraction_confidence,
           substr(summary,1,120) as summary,
           created_at
    FROM jobs
    WHERE source_site = 'Built In'
    ORDER BY created_at DESC
    LIMIT 15
    """
).fetchall()
print("Recent Built In jobs (last 15):")
for r in rows:
    print(r)
conn.close()
