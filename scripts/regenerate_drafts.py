import os
from drafting_engine import load_file, run_drafting_engine

WORK_EXP_FILE = "data/workExperience.md"

def main():
    work_exp = load_file(WORK_EXP_FILE)
    jobs = [
        "Arcesium - Product Manager", 
        "CentralReach - Product Manager", 
        "InStride Health - Product Manager", 
        "Machinify - Product Manager", 
        "Tailscale - Product Manager"
    ]
    for job in jobs:
        print(f"\n--- Regenerating {job} ---")
        jd_path = f"processed_jobs/{job}.txt"
        if not os.path.exists(jd_path):
            jd_path = f"jobs/{job}.txt"
            
        if os.path.exists(jd_path):
            jd_text = load_file(jd_path)
            run_drafting_engine(job, jd_text, work_exp, {})
        else:
            print(f"Could not find JD for {job}")

if __name__ == "__main__":
    main()
