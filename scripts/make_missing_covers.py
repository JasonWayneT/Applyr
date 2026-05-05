import os
import sys
from utils import load_file, WORK_EXP_FILE
from drafting_engine import run_drafting_engine

def make_for(company):
    print(f"Generating missing assets/cover for: {company}")
    jd_path = os.path.join("jobs", f"{company.replace(' ', '_').capitalize()}.txt")
    if not os.path.exists(jd_path):
        jd_path = os.path.join("jobs", f"{company.capitalize()}.txt")
    
    if not os.path.exists(jd_path):
        # try lowercase or raw
        for f in os.listdir("jobs"):
            if f.lower().startswith(company.lower()):
                jd_path = os.path.join("jobs", f)
                break

    if not os.path.exists(jd_path):
        print(f"JD text not found for {company}")
        return

    jd_text = load_file(jd_path)
    work_exp = load_file(WORK_EXP_FILE)
    
    # Dummy evaluation result enough for drafting_engine to start
    evaluation_result = {
        "Score": 85,
        "Decision": "YES",
        "Summary": "Manually triggered draft.",
        "TopFitReasons": ["Good platform fit", "Strong B2B matching"],
        "RiskFlags": []
    }
    
    run_drafting_engine(company, jd_text, work_exp, evaluation_result)
    print(f"Finished generating assets for {company}")

for c in ["case_iq"]:
    try:
        make_for(c)
    except Exception as e:
        print(f"Error for {c}: {e}")
