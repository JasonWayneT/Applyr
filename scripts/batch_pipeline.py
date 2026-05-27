import os
import json
import glob
import time
import argparse
import sys
import sqlite3
import re
from datetime import datetime
from utils import (
    load_file, call_llm, check_rate_limits, JOBS_DIR, PROJECT_ROOT, SUBMISSIONS_DIR,
    WORK_EXP_FILE, WORK_EXP_SUMMARY_FILE, FIT_ENGINE_FILE,
    SCORING_JD_MAX_CHARS, JD_REQUIRED_KEYWORDS, MIN_FIT_SCORE, load_candidate_preferences,
    unload_local_models
)
from drafting_engine import run_drafting_engine
from generate_cheat_sheet import generate_cheat_sheet

# CR-011: user-facing pipeline status vocabulary
STATUS_NEEDS_RETRY = "Needs Retry"
STATUS_REJECTED = "Rejected"
MAX_AUTO_RETRIES = 3


def _company_submission_dir(company_name: str) -> str:
    return os.path.join(SUBMISSIONS_DIR, company_name.lower().replace(" ", "_"))


def _resolve_display_company(db_path: str, company_name: str, job_id: str | None = None) -> str:
    """Implements FR-103 (CR-017): use DB company title for cover letter, not folder slug."""
    if not db_path or not os.path.exists(db_path):
        return company_name
    try:
        conn = sqlite3.connect(db_path)
        if job_id:
            row = conn.execute(
                "SELECT company FROM jobs WHERE id LIKE ? LIMIT 1",
                (f"{job_id[:8]}%",),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT company FROM jobs WHERE LOWER(company) = LOWER(?) LIMIT 1",
                (company_name,),
            ).fetchone()
        conn.close()
        if row and row[0] and str(row[0]).strip():
            return str(row[0]).strip()
    except sqlite3.Error:
        pass
    return company_name


def _has_required_pdfs(company_name: str) -> bool:
    """Implements FR-045 / BUG-003: Backlog only when resume + cover letter PDFs exist."""
    folder = _company_submission_dir(company_name)
    if not os.path.isdir(folder):
        return False
    pdfs = [f.lower() for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    has_resume = any("resume" in f for f in pdfs)
    has_cover = any("cover" in f for f in pdfs)
    return has_resume and has_cover


def _find_staging_jd(company: str, job_id: str | None = None) -> str:
    """Locate scraped JD file (Company_uuidprefix.txt) for single/draft mode."""
    if job_id:
        prefix = job_id[:8]
        matches = glob.glob(os.path.join(JOBS_DIR, f"*_{prefix}.txt"))
        if matches:
            return load_file(matches[0])
    safe = company.replace(" ", "_")
    for name in (f"{company}.txt", f"{safe}.txt"):
        path = os.path.join(JOBS_DIR, name)
        if os.path.exists(path):
            return load_file(path)
    matches = glob.glob(os.path.join(JOBS_DIR, f"{safe}_*.txt"))
    if matches:
        return load_file(matches[0])
    return ""


def _load_jd_for_job(company: str, job_id: str | None = None) -> str:
    """Staging file first, then saved Original_JD.txt from a prior draft attempt."""
    jd_text = _find_staging_jd(company, job_id)
    if jd_text and len(jd_text.strip()) >= 100:
        return jd_text
    original = os.path.join(_company_submission_dir(company), "Original_JD.txt")
    if os.path.exists(original):
        return load_file(original)
    return ""


def _load_job_fit_from_db(db_path: str, job_id: str):
    """Return (score, summary) when job already passed fit — for draft-only mode."""
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        row = conn.execute(
            "SELECT score, summary, status FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        conn.close()
        if row and row[0] is not None and int(row[0]) >= MIN_FIT_SCORE:
            return int(row[0]), (row[1] or ""), row[2]
    except Exception:
        pass
    return None


def _update_job_row(db_path, job_id_prefix, company_name, status, score=None, summary=None):
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    if job_id_prefix:
        if score is not None:
            cursor.execute(
                "UPDATE jobs SET status = ?, score = ?, summary = ? WHERE id LIKE ?",
                (status, score, summary or "", f"{job_id_prefix}%"),
            )
        else:
            cursor.execute(
                "UPDATE jobs SET status = ?, summary = ? WHERE id LIKE ?",
                (status, summary or "", f"{job_id_prefix}%"),
            )
    else:
        if score is not None:
            cursor.execute(
                "UPDATE jobs SET status = ?, score = ?, summary = ? WHERE LOWER(company) = LOWER(?)",
                (status, score, summary or "", company_name),
            )
        else:
            cursor.execute(
                "UPDATE jobs SET status = ?, summary = ? WHERE LOWER(company) = LOWER(?)",
                (status, summary or "", company_name),
            )
    conn.commit()
    conn.close()


def _mark_job_needs_retry(db_path, job_id_prefix, company_name, summary: str):
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    if job_id_prefix:
        cursor.execute(
            """
            UPDATE jobs SET status = ?, summary = ?,
            retry_count = COALESCE(retry_count, 0) + 1
            WHERE id LIKE ?
            """,
            (STATUS_NEEDS_RETRY, summary[:500], f"{job_id_prefix}%"),
        )
    else:
        cursor.execute(
            """
            UPDATE jobs SET status = ?, summary = ?,
            retry_count = COALESCE(retry_count, 0) + 1
            WHERE LOWER(company) = LOWER(?)
            """,
            (STATUS_NEEDS_RETRY, summary[:500], company_name),
        )
    conn.commit()
    conn.close()


def _mark_job_rejected(db_path, job_id_prefix, company_name, url, title, summary: str, score=None):
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    if url:
        cursor.execute(
            "INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)",
            (url, company_name, title),
        )
    if job_id_prefix:
        if score is not None:
            cursor.execute(
                "UPDATE jobs SET status = ?, score = ?, summary = ? WHERE id LIKE ?",
                (STATUS_REJECTED, score, summary[:500], f"{job_id_prefix}%"),
            )
        else:
            cursor.execute(
                "UPDATE jobs SET status = ?, summary = ? WHERE id LIKE ?",
                (STATUS_REJECTED, summary[:500], f"{job_id_prefix}%"),
            )
    else:
        if score is not None:
            cursor.execute(
                "UPDATE jobs SET status = ?, score = ?, summary = ? WHERE LOWER(company) = LOWER(?)",
                (STATUS_REJECTED, score, summary[:500], company_name),
            )
        else:
            cursor.execute(
                "UPDATE jobs SET status = ?, summary = ? WHERE LOWER(company) = LOWER(?)",
                (STATUS_REJECTED, summary[:500], company_name),
            )
    conn.commit()
    conn.close()


def _draft_success_summary(score, display_company: str, fit_summary: str) -> str:
    """Implements FR-107 (CR-018): never re-persist stale audit error text."""
    fit_line = (fit_summary or "")[:200]
    if "Asset drafting failed" in fit_line or "numeric audit" in fit_line:
        fit_line = ""
    if "Ready to apply" in fit_line:
        theme = re.search(r"JD themes:.+", fit_line)
        fit_line = theme.group(0).strip() if theme else ""
    base = f"Ready to apply — {display_company} (score {score}, CR-018)."
    return f"{base} {fit_line}".strip() if fit_line else base


def _set_backlog(db_path, job_id_prefix, company_name, score, summary: str):
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    if job_id_prefix:
        cursor.execute(
            """
            UPDATE jobs SET status = 'Backlog', score = ?, summary = ?, retry_count = 0
            WHERE id LIKE ?
            """,
            (score, summary or "", f"{job_id_prefix}%"),
        )
    else:
        cursor.execute(
            """
            UPDATE jobs SET status = 'Backlog', score = ?, summary = ?, retry_count = 0
            WHERE LOWER(company) = LOWER(?)
            """,
            (score, summary or "", company_name),
        )
    conn.commit()
    conn.close()


def _cleanup_staging_file(filepath: str, filename: str):
    try:
        os.remove(filepath)
        print(f"  -> Cleaned up staging file: {filename}")
    except Exception:
        pass


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

    from llm_stages import local_only_mode

    provider_override = ["local"] if local_only_mode() else ["local", "gemini"]
    result = call_llm(
        system_prompt="You are the Job-Fit Decision Engine. Output JSON strictly.",
        user_prompt=prompt,
        temperature=0.1,
        response_mime_type="application/json",
        provider_override=provider_override,
    )

    if not result or not result.strip():
        return None

    try:
        import re
        # Extract the JSON object robustly from free-form response text
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            output = match.group(0).strip()
            return json.loads(output)
            
        output = result.strip()
        if output.startswith("```json"):
            output = output[7:-3].strip()
        elif output.startswith("```"):
            output = output[3:-3].strip()
        return json.loads(output)
    except json.JSONDecodeError as e:
        print(json.dumps({"stage": "fit", "status": "error", "summary": f"Failed to parse LLM JSON: {e}"}))
        return None

def process_single(company, url, jd_text, job_id=None, draft_only=False):
    print(json.dumps({"id": "gate", "status": "running", "summary": "Checking keyword signals..."}))

    fit_rules = load_file(FIT_ENGINE_FILE)
    prefs = load_candidate_preferences()
    db_path = os.path.join(PROJECT_ROOT, "jobagent.sqlite")

    if not jd_text:
        jd_text = _load_jd_for_job(company, job_id)

    if not jd_text:
        print(json.dumps({"id": "gate", "status": "error", "summary": "No JD text found. Run sync or open the job posting to scrape first."}))
        return

    cached_fit = None
    if draft_only and job_id and os.path.exists(db_path):
        cached_fit = _load_job_fit_from_db(db_path, job_id)
        if not cached_fit:
            print(json.dumps({"id": "fit", "status": "error", "summary": "Draft-only requires an existing fit score ≥ 72 on this job."}))
            return
    # Zero-token keyword gate before any LLM call
    if not passes_jd_keyword_gate(jd_text, prefs):
        print(json.dumps({"id": "gate", "status": "done", "summary": "Rejected (keyword/title gate: blocked or no relevant signals)."}))
        print(json.dumps({"score": 0, "passed": False}))
        return

    print(json.dumps({"id": "gate", "status": "done", "summary": "Signals detected."}))

    if cached_fit:
        score, summary, _prior_status = cached_fit
        print(json.dumps({"id": "fit", "status": "done", "summary": f"Using saved fit score {score} (draft-only, skipped re-evaluation)."}))
        result = {"Score": score, "Decision": "YES", "Summary": summary}
    else:
        print(json.dumps({"id": "fit", "status": "running", "summary": f"Evaluating '{company}'..."}))
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
        display = _resolve_display_company(db_path, company, job_id)
        run_drafting_engine(company, jd_text, work_exp_full, result, display_name=display)
        print(json.dumps({"id": "resume", "status": "done", "summary": "ATS-Optimized PDF Generated"}))
        print(json.dumps({"id": "cover", "status": "done", "summary": "PDF Generated"}))
    except Exception as e:
        print(json.dumps({"id": "resume", "status": "error", "summary": f"Drafting failed: {e}"}))
        if os.path.exists(db_path) and job_id:
            try:
                _mark_job_needs_retry(db_path, job_id[:8], company, f"Asset drafting failed: {e}")
            except Exception:
                pass
        print(json.dumps({"score": score, "passed": False, "summary": str(e)}))
        return

    try:
        generate_cheat_sheet(company, display_name=display)
    except Exception as e:
        print(json.dumps({"id": "cheat_sheet", "status": "warning", "summary": str(e)[:200]}))

    if not _has_required_pdfs(company):
        msg = "Drafting finished but required PDFs (resume + cover letter) are missing."
        print(json.dumps({"id": "resume", "status": "error", "summary": msg}))
        if os.path.exists(db_path) and job_id:
            try:
                _mark_job_needs_retry(db_path, job_id[:8], company, msg)
            except Exception:
                pass
        print(json.dumps({"score": score, "passed": False, "summary": msg}))
        return

    success_summary = _draft_success_summary(score, display, summary)
    if os.path.exists(db_path) and job_id:
        try:
            _set_backlog(db_path, job_id[:8], company, score, success_summary)
        except Exception as e:
            print(json.dumps({"id": "fit", "status": "error", "summary": f"Could not update database: {e}"}))

    print(json.dumps({
        "score": score,
        "passed": True,
        "company": company,
        "title": result.get("Title", "Product Manager"),
        "url": url,
        "summary": success_summary
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

    total_jobs = len(job_files)
    job_failures = 0
    for idx, filepath in enumerate(job_files):
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
        print(f"[JOB_PROGRESS] Job {idx + 1}/{total_jobs}: Evaluating {company_name}...")
        
        jd_text = load_file(filepath)

        if not jd_text or len(jd_text.strip()) < 100:
            print(f"  -> Skipping. File {filename} seems empty or too short.")
            _cleanup_staging_file(filepath, filename)
            continue

        file_url = None
        first_line = jd_text.strip().split('\n')[0].strip()
        if first_line.startswith('URL:'):
            file_url = first_line.replace('URL:', '').strip()

        status_to_check = None
        is_stale = False
        if db_exists:
            try:
                conn = sqlite3.connect(db_path, timeout=30.0)
                cursor = conn.cursor()
                if file_url:
                    cursor.execute("SELECT 1 FROM stale_jobs WHERE url = ?", (file_url,))
                    if cursor.fetchone():
                        is_stale = True
                
                if not is_stale:
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

        if is_stale:
            print(f"  -> Skipping. Job already present in 'stale_jobs'.")
            _cleanup_staging_file(filepath, filename)
            continue

        if status_to_check and status_to_check not in ('New', 'Drafted'):
            print(f"  -> Skipping. Already evaluated (status: {status_to_check}).")
            _cleanup_staging_file(filepath, filename)
            continue

        # Zero-token keyword gate
        if not passes_jd_keyword_gate(jd_text, prefs):
            print(f"  -> Skipping. JD failed keyword pre-filter (no relevant signals).")
            if db_exists:
                try:
                    conn = sqlite3.connect(db_path, timeout=30.0)
                    cursor = conn.cursor()
                    if job_id_prefix:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                    else:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                    row = cursor.fetchone()
                    if row:
                        url, company, title = row
                        conn.close()
                        _mark_job_rejected(
                            db_path, job_id_prefix, company_name, url, title,
                            "Not a fit — keyword or title gate",
                        )
                        print(f"  -> Marked as '{STATUS_REJECTED}' (keyword/title gate).")
                    else:
                        conn.close()
                except Exception as e:
                    print(f"  -> Error handling keyword gate db update: {e}")
            _cleanup_staging_file(filepath, filename)
            continue

        print(f"  -> Evaluating fit against v3.2 Rubric...")
        result = evaluate_job_fit(jd_text, work_exp_summary, fit_rules, prefs)

        if not result:
            print("  -> Evaluation failed due to an error.")
            job_failures += 1
            if db_exists:
                try:
                    _mark_job_needs_retry(
                        db_path, job_id_prefix, company_name,
                        "LLM evaluation failed (JSON or API error)",
                    )
                    print(f"  -> Database status updated to '{STATUS_NEEDS_RETRY}' (will auto-requeue on next sync).")
                except Exception as e:
                    print(f"  -> Error marking failure in database: {e}")
            _cleanup_staging_file(filepath, filename)
            continue

        score = result.get("Score", 0)
        decision = result.get("Decision", "NO")
        print(f"  -> Result: {decision} (Score: {score})")
        print(f"  -> Summary: {result.get('Summary')}")

        if decision == "NO" or score < MIN_FIT_SCORE:
            print(f"  -> [GATEKEEPER REJECT] JD scored below 72 or triggered hard stop.")
            if db_exists:
                try:
                    conn = sqlite3.connect(db_path, timeout=30.0)
                    cursor = conn.cursor()
                    if job_id_prefix:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                    else:
                        cursor.execute("SELECT url, company, title FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                    row = cursor.fetchone()
                    if row:
                        url, company, title = row
                        conn.close()
                        _mark_job_rejected(
                            db_path, job_id_prefix, company_name, url, title,
                            f"Not a fit — score {score} below threshold ({MIN_FIT_SCORE})",
                            score=score,
                        )
                        print(f"  -> Marked as '{STATUS_REJECTED}' (low fit score).")
                    else:
                        conn.close()
                except Exception as e:
                    print(f"  -> Error handling low score db update: {e}")
            _cleanup_staging_file(filepath, filename)
            continue

        # Load full work experience only for YES decisions
        work_exp_full = load_file(WORK_EXP_FILE)
        print(f"[JOB_PROGRESS] Job {idx + 1}/{total_jobs}: Generating assets for {company_name}...")
        print(f"  -> [GATEKEEPER PASS] Score: {score}. Running drafting engine...")
        draft_error = None
        try:
            display = _resolve_display_company(db_path, company_name, job_id_prefix) if db_exists else company_name
            run_drafting_engine(company_name, jd_text, work_exp_full, result, display_name=display)
            try:
                generate_cheat_sheet(company_name, display_name=display)
            except Exception as e:
                print(f"  -> [Cheat sheet warning] {e}")
        except Exception as e:
            draft_error = e
            print(f"  -> [DRAFT ERROR] Asset generation failed: {e}")

        if draft_error or not _has_required_pdfs(company_name):
            job_failures += 1
            if db_exists:
                try:
                    reason = str(draft_error) if draft_error else "PDF assets missing after drafting"
                    _mark_job_needs_retry(db_path, job_id_prefix, company_name, reason[:500])
                    print(f"  -> Database status updated to '{STATUS_NEEDS_RETRY}' (draft did not complete).")
                except Exception as e:
                    print(f"  -> Error marking draft failure in database: {e}")
        elif db_exists:
            try:
                _set_backlog(
                    db_path,
                    job_id_prefix,
                    company_name,
                    score,
                    _draft_success_summary(
                        score,
                        display,
                        result.get("Summary", ""),
                    ),
                )
                print(f"  -> Database status updated to 'Backlog' (Ready to Apply) with score {score}.")
            except Exception as e:
                print(f"  -> Error updating database: {e}")
                job_failures += 1

        _cleanup_staging_file(filepath, filename)

        # Force immediate model unload to prevent swapping / stacked VRAM usage during sequential processing
        unload_local_models()

        print("  -> Sleeping for 15 seconds to respect rate limits...")
        time.sleep(15)

    if job_failures:
        print(f"\n[BATCH_SUMMARY] Queue drained with {job_failures} job failure(s). See logs above.")
    else:
        print("\n[BATCH_SUMMARY] Batch queue processed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['batch', 'single'], default='batch')
    parser.add_argument('--company', type=str, help='Company name for single mode')
    parser.add_argument('--url', type=str, help='URL for single mode')
    parser.add_argument('--job-id', type=str, help='Job UUID for single mode (locates scraped JD file)')
    parser.add_argument('--draft-only', action='store_true', help='Skip fit re-evaluation; draft using saved score')
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'single':
            # the Node server passes JD via stdin for robust parsing
            jd_input = ""
            if not sys.stdin.isatty():
                jd_input = sys.stdin.read().strip()
                
            process_single(
                args.company, args.url, jd_input,
                job_id=args.job_id, draft_only=args.draft_only,
            )
        else:
            process_batch()
    finally:
        # Implements auto-reclaim to clear VRAM when python process ends
        unload_local_models()
