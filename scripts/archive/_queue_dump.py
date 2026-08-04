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
for label, q in [
    ("Drafted", "SELECT company, title, length(coalesce(jd_text,'')) FROM jobs WHERE status='Drafted'"),
    ("Backlog", "SELECT company, title, length(coalesce(jd_text,'')) FROM jobs WHERE status='Backlog'"),
    ("Needs Retry", "SELECT company, title, length(coalesce(jd_text,'')) FROM jobs WHERE status='Needs Retry'"),
]:
    print(label + ":")
    for r in c.execute(q):
        print(" ", r)
c.close()
