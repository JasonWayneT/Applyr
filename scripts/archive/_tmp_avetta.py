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
