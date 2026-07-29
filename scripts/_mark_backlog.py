import sqlite3
from pathlib import Path

c = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite")
for co in ["Ladders", "Tillster", "Guidehealth", "hackajob", "Ottimate"]:
    r = c.execute(
        "SELECT id FROM jobs WHERE company = ? ORDER BY rowid DESC LIMIT 1", (co,)
    ).fetchone()
    if r:
        c.execute(
            "UPDATE jobs SET status = 'Backlog', score = COALESCE(score, 88) WHERE id = ?",
            (r[0],),
        )
        print(f"{co} -> Backlog ({r[0]})")
c.commit()
c.close()
