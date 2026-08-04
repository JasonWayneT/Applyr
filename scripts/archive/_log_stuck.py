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
names = ["hackajob", "Ottimate", "Tivity Health", "UKG", "Securly"]
for name in names:
    print(f"\n=== {name} ===")
    rows = c.execute(
        "SELECT timestamp, level, substr(message,1,250) FROM activity_log "
        "WHERE message LIKE ? ORDER BY id DESC LIMIT 8",
        (f"%{name}%",),
    ).fetchall()
    for r in rows:
        print(r)
c.close()
