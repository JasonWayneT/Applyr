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
