import os
import json
import glob
import time
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Paths configuration
JOBS_DIR = "jobs"
DATA_DIR = "data"
AGENT_DIR = ".agent"
RULES_DIR = os.path.join(AGENT_DIR, "rules")
SUBMISSIONS_DIR = "submissions"

WORK_EXP_FILE = os.path.join(DATA_DIR, "workExperience.md")
FIT_ENGINE_FILE = os.path.join(RULES_DIR, "job_fit_engine.md")

def load_file(filepath):
    """Utility to read a text file safely."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

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
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="You are the Job-Fit Decision Engine. Output JSON strictly.",
                    temperature=0.1,
                    response_mime_type="application/json"
                )
            )
            
            output = response.text.strip()
            # Clean up code blocks if present
            if output.startswith("```json"):
                output = output[7:-3].strip()
            elif output.startswith("```"):
                output = output[3:-3].strip()
                
            return json.loads(output)
        except Exception as e:
            err_str = str(e)
            if "retryDelay" in err_str or "429" in err_str or "quota" in err_str.lower() or "exhausted" in err_str.lower():
                print(f"  -> Rate limit hit. Waiting 45s before retry {attempt+1}/{max_retries}...")
                time.sleep(45)
            else:
                print(f"Error evaluating job fit via LLM: {e}")
                return None
    return None

def process_batch():
    print("====================================")
    print(" JobAgent v2.5 Batch Pipeline Sync  ")
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
        print("  -> Evaluating fit against v2.5 Rubric...")
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
            
        # If YES: Proceed to Research and Drafting
        print(f"  -> [GATEKEEPER PASS] Skipping Drafting Engine (Manual mode) for {company_name}")
        
        # Pass control to drafting engine bypassed
        # from drafting_engine import run_drafting_engine
        # run_drafting_engine(company_name, jd_text, work_exp, result)
        
        # "Flush" wait to ensure no API rate limit or cross-pollution
        print("  -> Sleeping for 15 seconds to respect rate limits...")
        time.sleep(15)

if __name__ == "__main__":
    process_batch()
