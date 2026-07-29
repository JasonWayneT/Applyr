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
