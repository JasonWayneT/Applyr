"""
One-time migration: Add new schema fields to job_database.json.
Adds: date_scouted, date_applied, rejection_reason, fit_summary, source
Extracts rejection_reason from compound status strings and normalizes status to base bucket.
"""
import json
import os
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                       "data", "job_database.json")

STATUS_BUCKETS = ["Interviewing", "Applied", "Drafted", "Scouted", "Rejected", "Archived"]


def get_bucket_and_reason(status):
    """Split 'Rejected (No Crypto Passion)' into bucket='Rejected', reason='No Crypto Passion'"""
    for bucket in STATUS_BUCKETS:
        if status.startswith(bucket):
            reason = ""
            if "(" in status and ")" in status:
                reason = status[status.index("(") + 1:status.index(")")]
            return bucket, reason
    return status, ""


def migrate():
    if not os.path.exists(DB_FILE):
        print(f"Database not found: {DB_FILE}")
        return

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        db = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")
    migrated = 0

    for job_id, job in db.items():
        changed = False

        # Extract rejection_reason from compound status
        bucket, reason = get_bucket_and_reason(job.get("status", ""))

        # Normalize status to base bucket
        if job["status"] != bucket:
            job["status"] = bucket
            changed = True

        # Add new fields with sensible defaults
        if "date_scouted" not in job:
            job["date_scouted"] = today
            changed = True

        if "date_applied" not in job:
            job["date_applied"] = None
            changed = True

        if "rejection_reason" not in job:
            job["rejection_reason"] = reason if reason else None
            changed = True

        if "fit_summary" not in job:
            job["fit_summary"] = None
            changed = True

        if "source" not in job:
            # Infer source from URL
            url = job.get("url", "#")
            if "linkedin.com" in url:
                source = "LinkedIn"
            elif "greenhouse.io" in url:
                source = "Greenhouse"
            elif "ashbyhq.com" in url:
                source = "Ashby"
            elif "workday" in url.lower():
                source = "Workday"
            elif url == "#":
                source = None
            else:
                source = "Direct"
            job["source"] = source
            changed = True

        if changed:
            migrated += 1

    # Write back
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

    print(f"Migration complete. Updated {migrated}/{len(db)} records.")
    print(f"New schema fields: date_scouted, date_applied, rejection_reason, fit_summary, source")


if __name__ == "__main__":
    migrate()
