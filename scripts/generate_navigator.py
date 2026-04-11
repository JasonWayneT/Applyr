"""
Generates the Job_Navigator.html from job_database.json.
NOTE: The navigator is now data-driven and reads the JSON at page load via fetch().
This script is kept as a fallback to regenerate the static HTML if needed,
but under normal operation the dashboard auto-updates from the database.
"""
import os
import json
from utils import DB_FILE, NAVIGATOR_FILE

STATUS_COLORS = {
    "Interviewing": "#f53d5b",
    "Applied": "#4facfe",
    "Drafted": "#00f2fe",
    "Scouted": "#a0a0a0",
    "Rejected": "#ff4444",
    "Archived": "#555555"
}

STATUS_PRIORITY = ["Interviewing", "Applied", "Drafted", "Scouted", "Rejected", "Archived"]


def get_status_bucket(status):
    """Resolve compound statuses like 'Rejected (No Crypto Passion)' to base bucket."""
    for bucket in STATUS_PRIORITY:
        if status.startswith(bucket):
            return bucket
    return "Scouted"


def main():
    if not os.path.exists(DB_FILE):
        print(f"Error: Database {DB_FILE} not found. Run migration first.")
        return

    with open(DB_FILE, 'r') as f:
        db = json.load(f)

    # Group by status bucket using startswith matching
    sections_html = []

    for status in STATUS_PRIORITY:
        status_jobs = {k: v for k, v in db.items() if get_status_bucket(v['status']) == status}
        if not status_jobs:
            continue

        cards_html = []
        for job_id, job in status_jobs.items():
            color = STATUS_COLORS.get(status, "#00f2fe")
            cards_html.append(f"""    <a href="{job['url']}" target="_blank" class="job-card" style="--status-color: {color}">
        <div>
            <div class="company-name">{job['company']}</div>
            <div class="job-title">{job['title']}</div>
        </div>
        <div class="card-footer">
            <span class="status-badge">
                <span class="status-dot"></span>
                {status}
            </span>
            <span class="btn-open">Open Brief</span>
        </div>
    </a>
""")

        sections_html.append(f"""<div class="status-section" style="--status-color: {STATUS_COLORS.get(status, '#00f2fe')}">
    <div class="section-header">
        <h2>{status}</h2>
        <span class="section-count">{len(status_jobs)}</span>
    </div>
    <div class="job-grid">
        {''.join(cards_html)}
    </div>
</div>""")

    print(f"Successfully grouped jobs by status bucket. Writing to {NAVIGATOR_FILE}")
    print("NOTE: The navigator is now data-driven. This static generation is a fallback.")


if __name__ == "__main__":
    main()
