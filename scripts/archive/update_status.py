"""
Update the status of a job in the database.
Supports the new schema with rejection_reason and date_applied fields.
"""
import os
import json
import sys
from datetime import datetime

# Use relative import if available, otherwise fall back
try:
    from utils import DB_FILE
except ImportError:
    DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "job_database.json")


def update_status(job_id_query, new_status, reason=None):
    if not os.path.exists(DB_FILE):
        print(f"Error: Database {DB_FILE} not found.")
        return

    with open(DB_FILE, 'r') as f:
        db = json.load(f)

    # Search for job (fuzzy match on ID or company name)
    match = None
    for job_id in db:
        if job_id_query.lower() in job_id.lower() or job_id_query.lower() in db[job_id]['company'].lower():
            match = job_id
            break

    if not match:
        print(f"No job matching '{job_id_query}' found.")
        return

    old_status = db[match]['status']
    db[match]['status'] = new_status

    # Update rejection_reason if transitioning to Rejected
    if new_status == "Rejected" and reason:
        db[match]['rejection_reason'] = reason

    # Update date_applied if transitioning to Applied
    if new_status == "Applied":
        db[match]['date_applied'] = datetime.now().strftime("%Y-%m-%d")

    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

    print(f"Updated '{match}': {old_status} -> {new_status}")
    if reason:
        print(f"  Reason: {reason}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python update_status.py 'Query' 'New Status' ['Rejection Reason']")
        print("Example: python scripts/update_status.py 'Atlassian' 'Applied'")
        print("Example: python scripts/update_status.py 'Coinbase' 'Rejected' 'No crypto fit'")
        sys.exit(1)

    reason_arg = sys.argv[3] if len(sys.argv) > 3 else None
    update_status(sys.argv[1], sys.argv[2], reason_arg)
