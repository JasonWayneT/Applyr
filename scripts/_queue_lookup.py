import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "jobagent.sqlite"
terms = ["beacon", "spex", "clever", "daxquia", "daxko", "par tech", "acquia", "apex"]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
for term in terms:
    cur.execute(
        """
        SELECT id, company, title, score, status, summary, url, created_at
        FROM jobs
        WHERE LOWER(company) LIKE ? OR LOWER(title) LIKE ?
        ORDER BY created_at DESC
        """,
        (f"%{term}%", f"%{term}%"),
    )
    rows = cur.fetchall()
    if rows:
        print(f"--- {term} ---")
        for r in rows:
            print(dict(r))

# Also show all scout-queue candidates
print("\n--- ALL SCOUT QUEUE (Drafted, no assets) ---")
cur.execute(
    """
    SELECT id, company, title, score, status, created_at
    FROM jobs
    WHERE status IN ('Backlog', 'Drafted', 'Needs Retry')
    ORDER BY company
    """
)
for r in cur.fetchall():
    print(dict(r))

conn.close()
