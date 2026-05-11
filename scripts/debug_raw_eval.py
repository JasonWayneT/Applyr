import sys
import os
import json
import glob
from utils import load_file, call_llm, FIT_ENGINE_FILE, load_candidate_preferences, WORK_EXP_SUMMARY_FILE, WORK_EXP_FILE, JOBS_DIR, SCORING_JD_MAX_CHARS

def debug_single_evaluation():
    print("=== RAW LLM OUTPUT DIAGNOSTIC ===")
    
    job_files = glob.glob(os.path.join(JOBS_DIR, "*.txt"))
    if not job_files:
        print("No files found!")
        return
        
    filepath = job_files[0]
    jd_text = load_file(filepath)
    print(f"Evaluating: {filepath}")
    
    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    fit_rules = load_file(FIT_ENGINE_FILE)
    prefs = load_candidate_preferences()
    
    truncated_jd = jd_text[:SCORING_JD_MAX_CHARS]
    prefs_str = json.dumps(prefs, indent=2)
    
    prompt = f"""
    You are the JobAgent Job-Fit Decision Engine.
    
    CANDIDATE PREFERENCES:
    {prefs_str}
    GROUND TRUTH:
    {work_exp}
    JOB DESCRIPTION:
    {truncated_jd}
    RULES & SCORING PROTOCOL:
    {fit_rules}
    
    Return response strictly as JSON.
    """
    
    print("Calling Local LLM...")
    raw_result = call_llm(
        system_prompt="You are the Job-Fit Decision Engine. Output JSON strictly.",
        user_prompt=prompt,
        temperature=0.1,
        response_mime_type="application/json"
    )
    
    print("\n--- RAW LLM OUTPUT RECEIVED ---")
    print(raw_result)
    print("-------------------------------\n")
    
    if not raw_result:
        print("FAILED: Received None from call_llm.")
        return

    # Attempt same parsing logic as in batch_pipeline
    try:
        output = raw_result
        if output.startswith("```json"):
            output = output[7:-3].strip()
        elif output.startswith("```"):
            output = output[3:-3].strip()
        
        parsed = json.loads(output)
        print("PARSE SUCCESSFUL!")
        print(json.dumps(parsed, indent=2))
    except Exception as e:
        print(f"PARSE FAILED: {e}")

debug_single_evaluation()
