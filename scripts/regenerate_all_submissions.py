import os
import sys
from utils import load_file, WORK_EXP_FILE, SUBMISSIONS_DIR
from drafting_engine import run_drafting_engine

def regenerate_all():
    print("==================================================================")
    print("      REGENERATING ALL SUBMISSIONS WITH SAFETY FIXES & CODES      ")
    print("==================================================================")
    
    work_exp = load_file(WORK_EXP_FILE)
    if not work_exp:
        print("CRITICAL ERROR: workExperience.md is empty or missing.")
        return
        
    folders = [f for f in os.listdir(SUBMISSIONS_DIR) if os.path.isdir(os.path.join(SUBMISSIONS_DIR, f))]
    if "carefull_-_product_manager" in folders:
        folders.remove("carefull_-_product_manager")
        folders.insert(0, "carefull_-_product_manager")
    print(f"Found {len(folders)} folders in {SUBMISSIONS_DIR}.")
    
    for folder in folders:
        folder_path = os.path.join(SUBMISSIONS_DIR, folder)
        jd_path = os.path.join(folder_path, "Original_JD.txt")
        if not os.path.exists(jd_path):
            print(f"  [Skip] {folder} (No Original_JD.txt found)")
            continue
            
        print(f"\n---> Regenerating: {folder}")
        jd_text = load_file(jd_path)
        
        # Strip URL prefix if saved
        if jd_text.startswith("URL:"):
            lines = jd_text.splitlines()
            if len(lines) > 1:
                jd_text = "\n".join(lines[1:])
                
        fake_evaluation = {
            "Decision": "YES",
            "Score": 90,
            "Confidence": "High",
            "Summary": "Regenerated to apply robust formatting and style compliance."
        }
        
        try:
            # We use the folder name as the company name
            company_name = folder.replace("_", " ").title()
            run_drafting_engine(company_name, jd_text, work_exp, fake_evaluation)
            print(f"  [SUCCESS] Regenerated all assets for {folder}")
        except Exception as e:
            print(f"  [ERROR] Failed to regenerate {folder}: {e}")

if __name__ == "__main__":
    regenerate_all()
