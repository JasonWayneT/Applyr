# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

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
