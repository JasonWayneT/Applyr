"""
Regenerate Resume.md / Resume.pdf for every submission folder (cover letters unchanged).

Uses compose pipeline with RESUME_BULLET_QUOTAS (default 5/3/3), RESUME_ONLY=1,
and cover_prose theme shortening (no chained 'and' in summary).
"""
import os
import sys

from utils import load_file, WORK_EXP_FILE, SUBMISSIONS_DIR
from draft_compiler import run as run_compiler

os.environ.setdefault("RESUME_ONLY", "1")
os.environ.setdefault("SKIP_PDF_EXPORT", "1")
os.environ.setdefault("DRAFT_MODE", "compose")
os.environ.setdefault("LOCAL_ONLY_MODE", "1")
os.environ.setdefault("JD_PROFILE_MODE", "deterministic")
os.environ.setdefault("RESEARCH_MODE", "skip")


def _folder_to_company(folder: str) -> str:
    """Map submissions folder slug to compiler company_folder name."""
    return folder.replace("-", "_").lower()


def regenerate_all_resumes():
    print("==================================================================")
    print("   REGENERATING RESUMES ONLY (5/3/3 bullets + conversion critique)   ")
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

    for folder in folders:
        folder_path = os.path.join(SUBMISSIONS_DIR, folder)
        jd_path = os.path.join(folder_path, "Original_JD.txt")
        if not os.path.exists(jd_path):
            print(f"  [Skip] {folder} (no Original_JD.txt)")
            continue

        jd_text = load_file(jd_path) or ""
        if jd_text.startswith("URL:"):
            lines = jd_text.splitlines()
            jd_text = "\n".join(lines[1:]) if len(lines) > 1 else jd_text

        if len(jd_text.strip()) < 100:
            print(f"  [Skip] {folder} (JD too short)")
            continue

        company_slug = _folder_to_company(folder)
        from company_slug import resolve_company_display_name

        display = resolve_company_display_name(
            company_slug,
            company_folder=folder_path,
            jd_text=jd_text,
        )
        print(f"\n---> {folder} ({display})")

        evaluation = {
            "Decision": "YES",
            "Score": 87,
            "Summary": "Regenerated resume with employer bullet quotas.",
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
            print(f"  [OK] Resume updated for {folder}")
            ok_count += 1
        except Exception as e:
            print(f"  [ERROR] {folder}: {e}")
            fail_count += 1

    print(f"\n[DONE] {ok_count} succeeded, {fail_count} failed.")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(regenerate_all_resumes())
