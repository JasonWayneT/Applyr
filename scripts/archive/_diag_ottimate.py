# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import sqlite3
from pathlib import Path
from seniority_gate import extract_job_title_line, passes_title_gate, title_blocked
from utils import load_candidate_preferences, init_pipeline_prefs

init_pipeline_prefs()
prefs = load_candidate_preferences()
c = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite")
row = c.execute(
    "SELECT company, title, substr(jd_text,1,500) FROM jobs WHERE company='Ottimate' ORDER BY rowid DESC LIMIT 1"
).fetchone()
print("DB title:", row[1])
print("Title line:", extract_job_title_line(row[2] if row else ""))
if row and row[2]:
    jd = c.execute("SELECT jd_text FROM jobs WHERE company='Ottimate' ORDER BY rowid DESC LIMIT 1").fetchone()[0]
    print("extract:", repr(extract_job_title_line(jd)))
    print("blocked:", title_blocked(extract_job_title_line(jd), prefs))
    print("gate:", passes_title_gate(jd, prefs))
    for i, line in enumerate(jd.splitlines()[:15]):
        print(f"  {i}: {line[:100]}")
c.close()
