"""
Regenerate drafts for all jobs currently in 'Drafted' status.
Reads dynamically from job_database.json instead of a hardcoded list.
"""
import os
import json
from utils import load_file, DB_FILE, WORK_EXP_FILE, JOBS_DIR
from drafting_engine import run_drafting_engine


def main():
    work_exp = load_file(WORK_EXP_FILE)
    if not work_exp:
        print("CRITICAL: Could not load workExperience.md")
        return

    if not os.path.exists(DB_FILE):
        print(f"Database not found: {DB_FILE}")
        return

    with open(DB_FILE, 'r') as f:
        db = json.load(f)

    # Find all 'Drafted' jobs that have JD files
    drafted_jobs = {k: v for k, v in db.items()
                    if v['status'].startswith('Drafted')}

    if not drafted_jobs:
        print("No drafted jobs found to regenerate.")
        return

    print(f"Found {len(drafted_jobs)} drafted jobs to regenerate.")

    for job_id, job in drafted_jobs.items():
        company_name = job['company']
        print(f"\n--- Regenerating {company_name} ---")

        # Try to find the JD file
        folder_path = job.get('folder_path', '')
        jd_path = os.path.join(folder_path, "Original_JD.txt") if folder_path else None

        if not jd_path or not os.path.exists(jd_path):
            # Fallback: check jobs/ directory
            for f in os.listdir(JOBS_DIR):
                if company_name.lower() in f.lower():
                    jd_path = os.path.join(JOBS_DIR, f)
                    break

        if jd_path and os.path.exists(jd_path):
            jd_text = load_file(jd_path)
            run_drafting_engine(company_name, jd_text, work_exp, {})
        else:
            print(f"Could not find JD for {company_name}")


if __name__ == "__main__":
    main()
