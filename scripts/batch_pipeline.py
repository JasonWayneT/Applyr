import os
import json
import glob
import time
from datetime import datetime
from utils import load_file, call_llm, JOBS_DIR, DATA_DIR, WORK_EXP_FILE, FIT_ENGINE_FILE


def evaluate_job_fit(jd_text, work_exp_text, job_fit_rules):
    """
    Stage 1: Job Fit Gatekeeper (Context Firewalled)
    The LLM memory is fresh for this evaluation. Only the current JD and Ground Truth are passed.
    """
    prompt = f"""
    You are the JobAgent Job-Fit Decision Engine.
    
    GROUND TRUTH (Jason Taylor's Profile):
    {work_exp_text}
    
    JOB DESCRIPTION:
    {jd_text}
    
    RULES & SCORING PROTOCOL:
    {job_fit_rules}
    
    Process the above JOB DESCRIPTION using the strictly defined RULES & SCORING PROTOCOL. 
    First, check the Fast Gate (Hard Disqualifiers). If disqualified, return a score < 30 and Decision: NO.
    Next, apply the 100-point scoring criteria.
    Apply the Two-Anchor rule.
    
    Return the response ONLY in a valid JSON object format precisely matching this schema:
    {{
        "Decision": "YES" or "NO",
        "Score": Integer (0-100),
        "Confidence": "High", "Medium", or "Low",
        "Summary": "Brief reasoning...",
        "TopFitReasons": ["reason 1", "reason 2"],
        "RiskFlags": ["risk 1", "risk 2"]
    }}
    Do not output any introductory or concluding text outside the JSON object. Do not format with markdown codeblocks.
    """

    result = call_llm(
        system_prompt="You are the Job-Fit Decision Engine. Output JSON strictly.",
        user_prompt=prompt,
        temperature=0.1,
        response_mime_type="application/json"
    )

    if not result:
        return None

    try:
        # Clean up code blocks if present
        output = result
        if output.startswith("```json"):
            output = output[7:-3].strip()
        elif output.startswith("```"):
            output = output[3:-3].strip()
        return json.loads(output)
    except json.JSONDecodeError as e:
        print(f"  -> Failed to parse LLM JSON output: {e}")
        return None


def process_batch():
    print("====================================")
    print(" JobAgent v3.2 Batch Pipeline Sync  ")
    print("====================================")

    # Context Firewall Reset: Read Source of Truth (and cache it for the loop run)
    work_exp = load_file(WORK_EXP_FILE)
    fit_rules = load_file(FIT_ENGINE_FILE)

    if not work_exp or not fit_rules:
        print("CRITICAL ERROR: Source of Truth or Fit Rules missing. Aborting.")
        return

    # Find jobs to process
    job_files = glob.glob(os.path.join(JOBS_DIR, "*.txt"))
    if not job_files:
        print(f"No job description files (.txt) found in {JOBS_DIR}/ directory.")
        return

    print(f"Found {len(job_files)} jobs in batch queue.")

    for filepath in job_files:
        filename = os.path.basename(filepath)
        company_name = filename.replace(".txt", "").strip()

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing: {company_name}")
        jd_text = load_file(filepath)

        if len(jd_text.strip()) < 100:
            print(f"  -> Skipping. File {filename} seems empty or too short.")
            continue

        # Stage 1: Evaluate
        print("  -> Evaluating fit against v3.2 Rubric...")
        result = evaluate_job_fit(jd_text, work_exp, fit_rules)

        if not result:
            print("  -> Evaluation failed due to an error.")
            continue

        score = result.get("Score", 0)
        decision = result.get("Decision", "NO")
        print(f"  -> Result: {decision} (Score: {score})")
        print(f"  -> Summary: {result.get('Summary')}")

        # Hard stop if < 72
        if decision == "NO" or score < 72:
            print(f"  -> [GATEKEEPER REJECT] JD scored below 72 or triggered hard stop. Moving to next.")
            continue

        # If YES: Log the pass (drafting is handled by the /evaluate workflow)
        print(f"  -> [GATEKEEPER PASS] Score: {score}. Ready for drafting via /evaluate workflow.")

        # "Flush" wait to ensure no API rate limit or cross-pollution
        print("  -> Sleeping for 15 seconds to respect rate limits...")
        time.sleep(15)

if __name__ == "__main__":
    process_batch()
