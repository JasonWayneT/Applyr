import sys
import json
import sqlite3
import argparse
from utils import load_file, call_llm, WORK_EXP_SUMMARY_FILE, WORK_EXP_FILE

def run_skill_gap(db_path, job_id):
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute("SELECT company, title, url FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(json.dumps({"error": "Job not found"}))
        return
        
    company, title, url = row
    
    # We need to find the JD file.
    import glob, os
    from utils import JOBS_DIR
    matches = glob.glob(os.path.join(JOBS_DIR, f"{job_id}*.txt"))
    if not matches:
        # Fallback to company name
        matches = glob.glob(os.path.join(JOBS_DIR, f"{company.replace(' ', '_')}*.txt"))
        
    if not matches:
        print(json.dumps({"error": "JD text not found"}))
        return
        
    jd_text = load_file(matches[0])
    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    
    system_prompt = (
        "You are an expert career coach and technical recruiter. "
        "Analyze the provided Job Description against the candidate's Work Experience. "
        "Identify the top 3 critical 'Skill Gaps' (tools, domains, or specific experiences requested in the JD but missing from the resume). "
        "For each gap, provide a 1-sentence bridging strategy (how the candidate can pivot existing experience to address it). "
        "Output ONLY a JSON array of objects with keys 'gap' and 'strategy'."
    )
    
    user_prompt = f"JD:\n{jd_text}\n\nCandidate Experience:\n{work_exp}"
    
    try:
        result = call_llm(system_prompt, user_prompt, response_schema="json", temperature=0.1)
        if not result:
            print(json.dumps({"error": "LLM returned empty"}))
        else:
            # We just print the raw JSON from the LLM, assuming it correctly formatted it.
            print(result)
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    parser.add_argument("job_id")
    args = parser.parse_args()
    
    run_skill_gap(args.db_path, args.job_id)
