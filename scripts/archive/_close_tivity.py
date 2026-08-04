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
c = sqlite3.connect(DB)
c.execute(
    """
    UPDATE jobs SET status = 'Closed', rejection_type = 'Self-Rejected',
    rejection_stage = 'Needs Retry', score = 60,
    outcome_notes = 'Final retry: fit 60 below threshold 72'
    WHERE company = 'Tivity Health'
    """
)
c.commit()
print("Tivity Health -> Closed (fit 60)")
c.close()
