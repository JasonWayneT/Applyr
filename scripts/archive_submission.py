import os
import sys
import shutil
import datetime
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import move_folder_robust  # noqa: E402
from workflow.invalidate import sha256_file  # noqa: E402
from workflow.receipts import load_receipt  # noqa: E402

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "submissions")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")


def get_timestamp():
    return datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")


def _warn_if_pdfs_stale(folder: str) -> None:
    """CR-092 follow-up (2026-08-15, Jason-supplied): this script was a pure
    file move with no check that the PDFs being archived still match what
    Stage 2 last verified -- confirmed real, twice, the same session
    (recovering two moved folders left their PDFs stale relative to their
    receipts, silently, until --resume happened to catch it). WARN-only, not
    a forced recompile: this is a lightweight mover, not a build step, and
    forcing every archive operation to depend on a working Playwright/
    Chromium install would be a heavier, riskier change than the actual
    problem (silent staleness, not stale-ness itself) calls for. A stage2
    receipt legitimately may not exist yet (a Skip'd/practice folder) --
    that's not a warning case, just nothing to compare against."""
    receipt = load_receipt(folder, "stage2")
    if not receipt:
        return
    output_hashes = receipt.get("output_hashes") or {}
    stale = []
    for name in ("Resume.pdf", "CoverLetter.pdf"):
        expected = output_hashes.get(name)
        if not expected:
            continue
        actual = sha256_file(os.path.join(folder, name))
        if actual and actual != expected:
            stale.append(name)
    if stale:
        print(
            f"[WARNING] {', '.join(stale)} do not match the stage2 receipt's recorded "
            f"hash -- archiving anyway, but this folder's PDFs are stale relative to "
            f"what was last verified. Recompile before relying on them: "
            f"python scripts/compile_single.py {folder}/Resume.md {folder}/Resume.pdf"
        )


def archive_folder(company_slug):
    source_path = os.path.join(SUBMISSIONS_DIR, company_slug)
    target_path = os.path.join(ARCHIVE_DIR, company_slug)

    if not os.path.exists(source_path):
        print(f"[Notice] Folder '{source_path}' does not exist. Skipping.")
        return False

    _warn_if_pdfs_stale(source_path)

    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    if os.path.exists(target_path):
        backup_target = f"{target_path}_backup_{get_timestamp()}"
        print(f"[Archive] Destination exists. Backing up to '{backup_target}'")
        # CR-092 (2026-08-15): plain shutil.move() failed with PermissionError
        # on a real archive operation this session (transient Windows file
        # lock somewhere under the tree) -- move_folder_robust() retries the
        # rename with backoff, then falls back to copy+delete, same recovery
        # this exact failure needed by hand once already.
        move_folder_robust(target_path, backup_target)

    print(f"[Archive] Moving '{source_path}' → '{target_path}'")
    move_folder_robust(source_path, target_path)
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
