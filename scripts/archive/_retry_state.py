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
for co in ["Tivity Health", "UKG", "Ottimate"]:
    r = c.execute(
        "SELECT id, company, title, url, status, length(coalesce(jd_text,'')), score, retry_count FROM jobs WHERE company=? ORDER BY rowid DESC LIMIT 1",
        (co,),
    ).fetchone()
    print(r)
c.close()
