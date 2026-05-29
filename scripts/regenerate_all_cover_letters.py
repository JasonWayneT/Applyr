"""
Regenerate CoverLetter.md / CoverLetter.pdf for every submission folder (resumes unchanged).

Uses CR-024 independent cover engine (JD + claim catalog only, COVER_ENGINE=v1).
Run regenerate_all_resumes.py first if resumes are stale.
"""
import os
import sys

from utils import load_file, WORK_EXP_FILE, SUBMISSIONS_DIR
from draft_compiler import run as run_compiler

os.environ.pop("RESUME_ONLY", None)
os.environ["COVER_ONLY"] = "1"
os.environ.setdefault("DRAFT_MODE", "compose")
os.environ.setdefault("LOCAL_ONLY_MODE", "1")
os.environ.setdefault("JD_PROFILE_MODE", "deterministic")
os.environ.setdefault("RESEARCH_MODE", "skip")
os.environ.setdefault("COVER_ENGINE", "v1")


def _folder_to_company(folder: str) -> str:
    return folder.replace("-", "_").lower()


def regenerate_all_cover_letters():
    print("==================================================================")
    print("   REGENERATING COVER LETTERS (CR-024 engine v1 + FR-096 tone guard)   ")
    print("==================================================================")

    work_exp = load_file(WORK_EXP_FILE)
    if not work_exp:
        print("CRITICAL ERROR: workExperience.md is empty or missing.")
        return 1

    folders = sorted(
        f for f in os.listdir(SUBMISSIONS_DIR)
        if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f))
    )
    print(f"Found {len(folders)} submission folders.")

    ok_count = 0
    fail_count = 0
    skip_count = 0

    for folder in folders:
        folder_path = os.path.join(SUBMISSIONS_DIR, folder)
        jd_path = os.path.join(folder_path, "Original_JD.txt")
        resume_path = os.path.join(folder_path, "Resume.md")

        if not os.path.exists(jd_path):
            print(f"  [Skip] {folder} (no Original_JD.txt)")
            skip_count += 1
            continue
        if not os.path.exists(resume_path):
            print(f"  [Skip] {folder} (no Resume.md — run regenerate_all_resumes.py first)")
            skip_count += 1
            continue

        jd_text = load_file(jd_path) or ""
        if jd_text.startswith("URL:"):
            lines = jd_text.splitlines()
            jd_text = "\n".join(lines[1:]) if len(lines) > 1 else jd_text

        if len(jd_text.strip()) < 100:
            print(f"  [Skip] {folder} (JD too short)")
            skip_count += 1
            continue

        cache_path = os.path.join(folder_path, "jd_profile_cache.json")
        if os.path.exists(cache_path):
            os.remove(cache_path)

        company_slug = _folder_to_company(folder)
        display = folder.replace("_", " ").title()
        print(f"\n---> {folder} ({display})")

        evaluation = {
            "Decision": "YES",
            "Score": 87,
            "Summary": "Regenerated cover letter with tone guard and JD-tailored proofs.",
        }

        try:
            run_compiler(
                company_slug,
                jd_text,
                work_exp,
                evaluation,
                company_folder=folder_path,
                display_name=display,
            )
            print(f"  [OK] Cover letter updated for {folder}")
            ok_count += 1
        except Exception as e:
            print(f"  [ERROR] {folder}: {e}")
            fail_count += 1

    print(f"\n[DONE] {ok_count} succeeded, {fail_count} failed, {skip_count} skipped.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(regenerate_all_cover_letters())
