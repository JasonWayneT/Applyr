# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

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
