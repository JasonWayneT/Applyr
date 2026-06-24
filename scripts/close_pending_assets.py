"""Close all Pending Assets jobs (Backlog/New/Needs Retry/Drafted without full PDFs)."""
import os
import re
import shutil
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "jobagent.sqlite")
SUB = os.path.join(ROOT, "submissions")
ACTIVE = {"Backlog", "New", "Needs Retry", "Drafted"}


def slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def resolve_folder(company: str) -> str | None:
    target = slug(company).replace("_", "")
    if not os.path.isdir(SUB):
        return None
    for name in os.listdir(SUB):
        path = os.path.join(SUB, name)
        if os.path.isdir(path) and name.replace("_", "") == target:
            return path
    std = os.path.join(SUB, slug(company))
    return std if os.path.isdir(std) else None


def has_full_pdfs(company: str) -> bool:
    folder = resolve_folder(company)
    if not folder:
        return False
    pdfs = [f.lower() for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    return any("resume" in f for f in pdfs) and any("cover" in f for f in pdfs)


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, title, status, score FROM jobs ORDER BY company, title"
    ).fetchall()

    to_close = []
    for r in rows:
        if r["status"] not in ACTIVE:
            continue
        if has_full_pdfs(r["company"]):
            continue
        to_close.append(r)

    print(f"Closing {len(to_close)} Pending Assets job(s):\n")
    note = "Listing unavailable — removed from pipeline (pending assets cleanup)"
    removed_folders = []

    for r in to_close:
        print(f"  [{r['status']}] {r['company']} — {r['title'][:50]} (score={r['score']})")
        conn.execute(
            """
            UPDATE jobs SET status = 'Closed', rejection_stage = ?,
            rejection_type = 'No Longer Available', outcome_notes = ?
            WHERE id = ?
            """,
            (r["status"], note, r["id"]),
        )
        folder = resolve_folder(r["company"])
        if folder and os.path.isdir(folder):
            shutil.rmtree(folder, ignore_errors=True)
            removed_folders.append(os.path.basename(folder))

    conn.commit()
    conn.close()

    print(f"\nClosed {len(to_close)} job(s).")
    if removed_folders:
        print(f"Removed {len(removed_folders)} stub folder(s) from submissions/: {', '.join(sorted(set(removed_folders)))}")


if __name__ == "__main__":
    main()
