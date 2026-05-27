"""Re-queue Needs Retry jobs (Python fallback when tsx/better-sqlite3 unavailable)."""
import os
import re
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
JOBS_DIR = os.path.join(PROJECT_ROOT, "jobs")
SUBMISSIONS_DIR = os.path.join(PROJECT_ROOT, "submissions")
MAX_AUTO_RETRIES = 3


def resolve_folder(company: str) -> str | None:
    slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    direct = os.path.join(SUBMISSIONS_DIR, slug)
    if os.path.isdir(direct):
        return direct
    if not os.path.isdir(SUBMISSIONS_DIR):
        return None
    stripped = re.sub(r"[^a-z0-9]", "", company.lower())
    for name in os.listdir(SUBMISSIONS_DIR):
        full = os.path.join(SUBMISSIONS_DIR, name)
        if os.path.isdir(full) and re.sub(r"[^a-z0-9]", "", name.lower()) == stripped:
            return full
    return None


def main():
    conn = sqlite3.connect(DB_PATH)
    jobs = conn.execute(
        "SELECT id, company, title, url, COALESCE(retry_count, 0) FROM jobs WHERE status = 'Needs Retry'"
    ).fetchall()

    if not jobs:
        print("No jobs marked Needs Retry.")
        return

    os.makedirs(JOBS_DIR, exist_ok=True)
    to_drafted = to_new = skipped = 0

    for job_id, company, title, url, retry_count in jobs:
        if retry_count >= MAX_AUTO_RETRIES:
            print(f"  -> Skip {company} — max auto-retries ({MAX_AUTO_RETRIES}) reached.")
            skipped += 1
            continue

        folder = resolve_folder(company)
        original_jd = os.path.join(folder, "Original_JD.txt") if folder else None
        slug = re.sub(r"[^a-z0-9]+", "_", company, flags=re.I).strip("_")
        staging = os.path.join(JOBS_DIR, f"{slug}_{job_id[:8]}.txt")

        if original_jd and os.path.isfile(original_jd):
            content = open(original_jd, encoding="utf-8-sig").read()
            if url and not content.strip().startswith("URL:"):
                content = f"URL: {url}\n\n{content}"
            with open(staging, "w", encoding="utf-8") as f:
                f.write(content)
            conn.execute("UPDATE jobs SET status = 'Drafted' WHERE id = ?", (job_id,))
            print(f"  -> {company}: restored JD -> Drafted ({os.path.basename(staging)})")
            to_drafted += 1
        elif url and not str(url).startswith("local://"):
            conn.execute("UPDATE jobs SET status = 'New' WHERE id = ?", (job_id,))
            print(f"  -> {company}: will re-scrape -> New")
            to_new += 1
        else:
            print(f"  -> Skip {company} — no saved JD or URL to requeue.")
            skipped += 1

    conn.commit()
    conn.close()
    print(f"[REQUEUE_DONE] {to_drafted} -> Drafted, {to_new} -> New, {skipped} skipped.")


if __name__ == "__main__":
    main()
