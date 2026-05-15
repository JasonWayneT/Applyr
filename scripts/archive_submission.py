import os
import sys
import shutil
import datetime
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "submissions")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "archive", "submissions")
DB_PATH = os.path.join(PROJECT_ROOT, "jobagent.sqlite")


def get_timestamp():
    return datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")


def archive_folder(company_slug):
    source_path = os.path.join(SUBMISSIONS_DIR, company_slug)
    target_path = os.path.join(ARCHIVE_DIR, company_slug)

    if not os.path.exists(source_path):
        print(f"[Notice] Folder '{source_path}' does not exist. Skipping.")
        return False

    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    if os.path.exists(target_path):
        backup_target = f"{target_path}_backup_{get_timestamp()}"
        print(f"[Archive] Destination exists. Backing up to '{backup_target}'")
        shutil.move(target_path, backup_target)

    print(f"[Archive] Moving '{source_path}' → '{target_path}'")
    shutil.move(source_path, target_path)
    return True


def update_db_status(company_name):
    if not os.path.exists(DB_PATH):
        print("[Error] Database file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, status FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
    rows = cursor.fetchall()

    if not rows:
        print(f"[DB] No job matching company '{company_name}' found.")
        conn.close()
        return

    for job_id, title, current_status in rows:
        print(f"[DB] Updating '{company_name}' ({title}) from '{current_status}' → 'Applied'.")
        cursor.execute("UPDATE jobs SET status = 'Applied' WHERE id = ?", (job_id,))

    conn.commit()
    conn.close()


def print_pipeline_summary():
    if not os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n=== Pipeline Current Status ===")
    cursor.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
    for status, count in cursor.fetchall():
        print(f"  - {status}: {count}")

    cursor.execute(
        "SELECT company, title, score, status FROM jobs "
        "WHERE status IN ('New', 'Backlog') ORDER BY created_at DESC LIMIT 5"
    )
    recent = cursor.fetchall()
    if recent:
        print("\nTop Recent Actionable Items (New / Backlog):")
        for company, title, score, status in recent:
            score_str = f"Score: {score}" if score else "Unscored"
            print(f"  - {company} | {title} | {status} ({score_str})")

    conn.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python archive_submission.py <company_slug> [company_slug2 ...]")
        print("Example: python archive_submission.py auxilius softserve")
        sys.exit(1)

    company_slugs = sys.argv[1:]
    for slug in company_slugs:
        print(f"\n--- Archiving {slug} ---")
        archive_folder(slug)
        update_db_status(slug)

    print_pipeline_summary()


if __name__ == "__main__":
    main()
