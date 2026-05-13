import os
import sys
from utils import load_file, WORK_EXP_FILE, SUBMISSIONS_DIR
from drafting_engine import run_drafting_engine

CORRUPTED_FOLDERS = [
    "bitso",
    "onedigital_health",
    "randstad_digital",
    "reveille_technologies",
    "sun_technologies_inc_",
    "visionaire_partners",
    "vistance_networks"
]

def main():
    print("==================================================================")
    print("   SURGICALLY REGENERATING 7 IDENTIFIED CORRUPTED SUBMISSIONS    ")
    print("==================================================================")
    
    work_exp = load_file(WORK_EXP_FILE)
    if not work_exp:
        print("CRITICAL ERROR: workExperience.md is empty or missing.")
        return

    import time
    for folder in CORRUPTED_FOLDERS:
        folder_path = os.path.join(SUBMISSIONS_DIR, folder)
        if not os.path.exists(folder_path):
            print(f"[Skip] {folder} does not exist.")
            continue
            
        jd_path = os.path.join(folder_path, "Original_JD.txt")
        if not os.path.exists(jd_path):
            print(f"[Skip] {folder} has no Original_JD.txt")
            continue
            
        print(f"\n>>> REGENERATING: {folder} <<<")
        jd_text = load_file(jd_path)
        
        # Strip potential URL prefix
        if jd_text.startswith("URL:"):
            lines = jd_text.splitlines()
            if len(lines) > 1:
                jd_text = "\n".join(lines[1:])
                
        fake_evaluation = {
            "Decision": "YES",
            "Score": 90,
            "Confidence": "High",
            "Summary": "Regenerated using working Gemini API key to erase local LLM hallucinations."
        }
        
        # Derive company name from folder
        company_name = folder.replace("_", " ").title()
        
        # Robust Rate Limit Loop (Up to 3 attempts per company)
        for attempt in range(1, 4):
            try:
                # Inject substantial buffer time to clear Gemini API rate limit window
                wait_time = 20 * attempt
                print(f"  [Rate Limit Safety] Sleeping for {wait_time}s before calling Gemini...")
                time.sleep(wait_time)
                
                print(f"  Calling Gemini-2.5-Flash drafting engine for {company_name} (Attempt {attempt}/3)...")
                
                # Before running, record last modified time of Resume.md to verify success
                resume_path = os.path.join(folder_path, "Resume.md")
                mtime_before = os.path.getmtime(resume_path) if os.path.exists(resume_path) else 0
                
                run_drafting_engine(company_name, jd_text, work_exp, fake_evaluation)
                
                # Verify if Resume.md was actually overwritten
                mtime_after = os.path.getmtime(resume_path) if os.path.exists(resume_path) else 0
                if mtime_after > mtime_before:
                    print(f"  [SUCCESS] Successfully regenerated {folder}!")
                    break
                else:
                    print(f"  [WARNING] Drafting completed but Resume.md was not updated (likely Gemini Rate Limit). Retrying...")
            except Exception as e:
                print(f"  [ERROR] Attempt {attempt} failed for {folder}: {e}")
        
        # Extra buffer between companies to completely clear the 15-RPM window
        time.sleep(10)

    print("\n==================================================================")
    print("          REGENERATION FINISHED FOR CORRUPTED BATCH               ")
    print("==================================================================")

if __name__ == "__main__":
    main()
