import os
import json
import glob
import time
import argparse
import sys
from datetime import datetime
from utils import (
    load_file, call_llm, JOBS_DIR, PROJECT_ROOT,
    WORK_EXP_FILE, WORK_EXP_SUMMARY_FILE, FIT_ENGINE_FILE,
    SCORING_JD_MAX_CHARS, JD_REQUIRED_KEYWORDS, MIN_FIT_SCORE, load_candidate_preferences,
    unload_local_models
)
from drafting_engine import run_drafting_engine
from generate_cheat_sheet import generate_cheat_sheet


def passes_jd_keyword_gate(jd_text: str, prefs: dict = None) -> bool:
    """Zero-token pre-filter. Rejects JDs that have no relevant keywords or hit blocked titles."""
    lower = jd_text.lower()
    
    # 1. Blocked Titles Check (First 200 chars are typically the title/header)
    if prefs and "blocked_titles" in prefs:
        title_chunk = lower[:200]
        for blocked in prefs["blocked_titles"]:
            if blocked.lower() in title_chunk:
                print(f"    [ZERO-TOKEN REJECT] Title chunk contains blocked keyword: '{blocked}'", file=sys.stderr)
                return False

    # 2. Required Keywords Check
    return any(kw in lower for kw in JD_REQUIRED_KEYWORDS)


def evaluate_job_fit(jd_text, work_exp_summary, job_fit_rules, prefs):
    """Uses condensed summary and dynamic candidate preferences to minimize token cost."""
    # Truncate JD — first 1500 chars contain ~90% of signal for scoring
    truncated_jd = jd_text[:SCORING_JD_MAX_CHARS] if len(jd_text) > SCORING_JD_MAX_CHARS else jd_text

    prefs_str = json.dumps(prefs, indent=2) if prefs else "{}"

    prompt = f"""
    You are the JobAgent Job-Fit Decision Engine.
    
    CANDIDATE PREFERENCES:
    {prefs_str}

    GROUND TRUTH (Jason Taylor's Profile):
    {work_exp_summary}
    
    JOB DESCRIPTION (first {SCORING_JD_MAX_CHARS} chars):
    {truncated_jd}
    
    RULES & SCORING PROTOCOL:
    {job_fit_rules}
    
    Process the above JOB DESCRIPTION using the strictly defined RULES & SCORING PROTOCOL. 
    First, check the Fast Gate (Hard Disqualifiers) based on the CANDIDATE PREFERENCES. If disqualified, return a score < 30 and Decision: NO.
    Next, apply the 100-point scoring criteria.
    Apply the Two-Anchor rule using the anchors defined in CANDIDATE PREFERENCES.
    
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
        output = result
        if output.startswith("```json"):
            output = output[7:-3].strip()
        elif output.startswith("```"):
            output = output[3:-3].strip()
        return json.loads(output)
    except json.JSONDecodeError as e:
        print(json.dumps({"stage": "fit", "status": "error", "summary": f"Failed to parse LLM JSON: {e}"}))
        return None

def process_single(company, url, jd_text):
    print(json.dumps({"id": "gate", "status": "running", "summary": "Checking keyword signals..."}))

    fit_rules = load_file(FIT_ENGINE_FILE)
    prefs = load_candidate_preferences()

    if not jd_text:
        jd_path = os.path.join(JOBS_DIR, f"{company}.txt")
        if os.path.exists(jd_path):
            jd_text = load_file(jd_path)

    if not jd_text:
        print(json.dumps({"id": "gate", "status": "error", "summary": "No JD text provided or found."}))
        return

    # Zero-token keyword gate before any LLM call
    if not passes_jd_keyword_gate(jd_text, prefs):
        print(json.dumps({"id": "gate", "status": "done", "summary": "Rejected (keyword/title gate: blocked or no relevant signals)."}))
        print(json.dumps({"score": 0, "passed": False}))
        return

    print(json.dumps({"id": "gate", "status": "done", "summary": "Signals detected."}))
    print(json.dumps({"id": "fit", "status": "running", "summary": f"Evaluating '{company}'..."}))

    # Implements FR-064: summary auto-generated on save; fall back to full file if not yet generated
    work_exp_summary = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    result = evaluate_job_fit(jd_text, work_exp_summary, fit_rules, prefs)
    if not result:
        print(json.dumps({"id": "fit", "status": "error", "summary": "Evaluation failed."}))
        return

    score = result.get("Score", 0)
    decision = result.get("Decision", "NO")
    summary = result.get("Summary", "")
    
    if decision == "NO" or score < MIN_FIT_SCORE:
        print(json.dumps({"id": "fit", "status": "done", "summary": f"Rejected (Score: {score}). {summary}"}))
        print(json.dumps({"score": score, "passed": False}))
        return

    print(json.dumps({"id": "fit", "status": "done", "summary": f"Passed (Score: {score}). {summary}"}))

    # Load FULL work experience only now that we have a YES decision
    work_exp_full = load_file(WORK_EXP_FILE)

    # 2. Start drafting
    print(json.dumps({"id": "research", "status": "running", "summary": "Extracting intelligence..."}))

    try:
        run_drafting_engine(company, jd_text, work_exp_full, result)
        print(json.dumps({"id": "resume", "status": "done", "summary": "ATS-Optimized PDF Generated"}))
        print(json.dumps({"id": "cover", "status": "done", "summary": "PDF Generated"}))
    except Exception as e:
        print(json.dumps({"id": "resume", "status": "error", "summary": f"Drafting failed: {e}"}))
        
    try:
        generate_cheat_sheet(company)
    except Exception as e:
        pass
        
    print(json.dumps({
        "score": score, 
        "passed": True, 
        "company": company, 
        "title": result.get("Title", "Product Manager"), # Fit engine might return title
        "url": url,
        "summary": summary
    }))

def process_batch():
    import sqlite3
    print("====================================")
    print(" JobAgent v3.2 Batch Pipeline Sync  ")
    print("====================================")

    # Implements FR-064: summary auto-generated on save; fall back to full file if not yet generated
    work_exp_summary = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    fit_rules = load_file(FIT_ENGINE_FILE)
    prefs = load_candidate_preferences()

    if not work_exp_summary or not fit_rules:
        print("CRITICAL ERROR: workExperience.md and Fit Rules must both exist. Aborting.")
        return

    job_files = glob.glob(os.path.join(JOBS_DIR, "*.txt"))
    if not job_files:
        print(f"No job description files (.txt) found in {JOBS_DIR}/ directory.")
        return

    print(f"Found {len(job_files)} jobs in batch queue.")

    db_path = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
    db_exists = os.path.exists(db_path)

    for filepath in job_files:
        filename = os.path.basename(filepath)
        name_part = filename.replace(".txt", "").strip()

        job_id_prefix = None
        company_name = name_part
        if "_" in name_part:
            parts = name_part.rsplit("_", 1)
            if len(parts[1]) == 8:
                company_name = parts[0]
                job_id_prefix = parts[1]

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing: {company_name}")
        
        status_to_check = None
        if db_exists:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                if job_id_prefix:
                    cursor.execute("SELECT status FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                else:
                    cursor.execute("SELECT status FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                row = cursor.fetchone()
                if row:
                    status_to_check = row[0]
                conn.close()
            except Exception as e:
                print(f"  -> Error querying database: {e}")

        if status_to_check and status_to_check not in ['New', 'Drafted']:
            print(f"  -> Skipping. Already evaluated (status: {status_to_check}).")
            continue

        jd_text = load_file(filepath)

        if len(jd_text.strip()) < 100:
            print(f"  -> Skipping. File {filename} seems empty or too short.")
            continue

        # Zero-token keyword gate
        if not passes_jd_keyword_gate(jd_text, prefs):
            print(f"  -> Skipping. JD failed keyword pre-filter (no relevant signals).")
            if db_exists:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    if job_id_prefix:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                    else:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                    row = cursor.fetchone()
                    if row:
                        url, company, title = row
                        cursor.execute(
                            "INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)",
                            (url, company, title)
                        )
                        if job_id_prefix:
                            cursor.execute("DELETE FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                        else:
                            cursor.execute("DELETE FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                        conn.commit()
                        print(f"  -> Added to 'stale_jobs' and deleted from 'jobs' (Failed Keyword Gate) to avoid clutter.")
                    conn.close()
                except Exception as e:
                    print(f"  -> Error handling keyword gate db update: {e}")
            continue

        print(f"  -> Evaluating fit against v3.2 Rubric...")
        result = evaluate_job_fit(jd_text, work_exp_summary, fit_rules, prefs)

        if not result:
            print("  -> Evaluation failed due to an error.")
            continue

        score = result.get("Score", 0)
        decision = result.get("Decision", "NO")
        print(f"  -> Result: {decision} (Score: {score})")
        print(f"  -> Summary: {result.get('Summary')}")

        if decision == "NO" or score < MIN_FIT_SCORE:
            print(f"  -> [GATEKEEPER REJECT] JD scored below 72 or triggered hard stop.")
            if db_exists:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    if job_id_prefix:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                    else:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                    row = cursor.fetchone()
                    if row:
                        url, company, title = row
                        cursor.execute(
                            "INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)",
                            (url, company, title)
                        )
                        if job_id_prefix:
                            cursor.execute("DELETE FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                        else:
                            cursor.execute("DELETE FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                        conn.commit()
                        print(f"  -> Added to 'stale_jobs' and deleted from 'jobs' (Low Score) to avoid clutter.")
                    conn.close()
                except Exception as e:
                    print(f"  -> Error handling low score db update: {e}")
            continue

        # Load full work experience only for YES decisions
        work_exp_full = load_file(WORK_EXP_FILE)
        print(f"  -> [GATEKEEPER PASS] Score: {score}. Running drafting engine...")
        run_drafting_engine(company_name, jd_text, work_exp_full, result)
        try:
            generate_cheat_sheet(company_name)
        except Exception as e:
            pass

        if db_exists:
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                if job_id_prefix:
                    cursor.execute(
                        "UPDATE jobs SET status = 'Backlog', score = ?, summary = ? WHERE id LIKE ?",
                        (score, result.get("Summary", ""), f"{job_id_prefix}%")
                    )
                else:
                    cursor.execute(
                        "UPDATE jobs SET status = 'Backlog', score = ?, summary = ? WHERE LOWER(company) = LOWER(?)",
                        (score, result.get("Summary", ""), company_name)
                    )
                conn.commit()
                conn.close()
                print(f"  -> Database status updated to 'Backlog' (Ready to Apply) with score {score}.")
            except Exception as e:
                print(f"  -> Error updating database: {e}")
            
        print("  -> Sleeping for 15 seconds to respect rate limits...")
        time.sleep(15)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['batch', 'single'], default='batch')
    parser.add_argument('--company', type=str, help='Company name for single mode')
    parser.add_argument('--url', type=str, help='URL for single mode')
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'single':
            # the Node server passes JD via stdin for robust parsing
            jd_input = ""
            if not sys.stdin.isatty():
                jd_input = sys.stdin.read().strip()
                
            process_single(args.company, args.url, jd_input)
        else:
            process_batch()
    finally:
        # Implements auto-reclaim to clear VRAM when python process ends
        unload_local_models()
