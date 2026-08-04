# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

import sqlite3
import time
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from applyr_python import assert_applyr_host
from batch_pipeline import _has_required_pdfs, process_single

assert_applyr_host()
DB = Path(__file__).resolve().parent.parent / "data" / "jobagent.sqlite"

jobs = [
    ("Cambridge Spark", "53381fed-756c-4b78-bd38-e4a5091009b6", False),
    ("Ottimate", "b5d6e3f3", True),
]

conn = sqlite3.connect(DB)
for company, job_id, draft_only in jobs:
    row = conn.execute(
        "SELECT id, url, jd_text, score FROM jobs WHERE id LIKE ? ORDER BY rowid DESC LIMIT 1",
        (f"{job_id}%",),
    ).fetchone()
    if not row:
        print(f"SKIP {company}: not found")
        continue
    jid, url, jd_text, score = row
    if draft_only:
        conn.execute(
            "UPDATE jobs SET retry_count = 0, status = 'Drafted' WHERE id = ?",
            (jid,),
        )
        conn.commit()
    print(f"\n>>> {company} draft_only={draft_only} jd_len={len(jd_text or '')}")
    process_single(company, url=url or "", jd_text=jd_text or "", job_id=jid, draft_only=draft_only)
    print("PDFs:", _has_required_pdfs(company))
    time.sleep(2)
conn.close()
