# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("data/jobagent.sqlite")
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
