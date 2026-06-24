"""
One-shot / manual reconciliation of submissions/ vs job statuses (FR-030).
Archives folders for Applied+ jobs; removes orphan stubs without full PDFs.
"""
import os
import re
import shutil
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "data", "submissions")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "data", "archive", "submissions")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
ACTIVE = {"Backlog", "Drafted"}


def slug(c):
    return re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_")


def names_match(a, b):
    return a == b or a.replace("_", "") == b.replace("_", "")


def has_full_pdfs(folder):
    try:
        pdfs = [f.lower() for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    except OSError:
        return False
    return any("resume" in f for f in pdfs) and any("cover" in f for f in pdfs)


def merge_into(src, dest):
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(src):
        s, d = os.path.join(src, name), os.path.join(dest, name)
        if os.path.isdir(s):
            merge_into(s, d)
        else:
            shutil.copy2(s, d)


def archive_folder(folder_name, company_hint=None):
    src = os.path.join(SUBMISSIONS_DIR, folder_name)
    if not os.path.isdir(src):
        return False
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    dest = os.path.join(ARCHIVE_DIR, folder_name)
    if company_hint:
        alt = os.path.join(ARCHIVE_DIR, slug(company_hint))
        if os.path.isdir(alt) and alt != dest:
            dest = alt
    if os.path.isdir(dest):
        merge_into(src, dest)
        shutil.rmtree(src)
    else:
        shutil.move(src, dest)
    return True


def main():
    jobs = []
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        jobs = conn.execute("SELECT company, status FROM jobs").fetchall()
        conn.close()

    archived, removed = [], []
    if not os.path.isdir(SUBMISSIONS_DIR):
        print("submissions/ does not exist — nothing to do.")
        return

    for folder_name in sorted(os.listdir(SUBMISSIONS_DIR)):
        active = os.path.join(SUBMISSIONS_DIR, folder_name)
        if not os.path.isdir(active):
            continue

        matches = [(c, s) for c, s in jobs if names_match(slug(c), folder_name)]
        full_pdfs = has_full_pdfs(active)

        if matches and all(s not in ACTIVE for _, s in matches):
            company = matches[0][0]
            archive_folder(folder_name, company)
            archived.append(folder_name)
            print(f"[archive] {folder_name} (DB: {matches[0][1]})")
            continue

        if not matches and not full_pdfs:
            shutil.rmtree(active)
            removed.append(folder_name)
            print(f"[remove] {folder_name} (orphan stub)")
            continue

        if not matches and full_pdfs:
            archive_folder(folder_name)
            archived.append(folder_name)
            print(f"[archive] {folder_name} (orphan with PDFs)")
            continue

        print(f"[keep] {folder_name} (active pipeline)")

    remaining = (
        sorted(
            d
            for d in os.listdir(SUBMISSIONS_DIR)
            if os.path.isdir(os.path.join(SUBMISSIONS_DIR, d))
        )
        if os.path.isdir(SUBMISSIONS_DIR)
        else []
    )
    print(f"\nDone. archived={len(archived)}, removed={len(removed)}")
    print(f"Remaining in submissions/: {remaining or '(empty)'}")


if __name__ == "__main__":
    main()
