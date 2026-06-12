# Implements FR-132, FR-133, FR-149, FR-150 (CR-021); FR-006–FR-009, FR-109 (CR-019).
# Pipeline defaults: FR-131 via pipeline_env / setdefault below.
import os
import json
import glob
import time
import argparse
import sys
import sqlite3
import re
from datetime import datetime
import threading
import concurrent.futures
from utils import (
    load_file, call_llm, check_rate_limits, JOBS_DIR, PROJECT_ROOT, SUBMISSIONS_DIR,
    WORK_EXP_FILE, WORK_EXP_SUMMARY_FILE, FIT_ENGINE_FILE,
    SCORING_JD_MAX_CHARS, load_candidate_preferences,
    get_jd_required_keywords, get_min_fit_score,
    unload_local_models, clean_jd_text, send_notification
)
from local_embeddings import get_embedding, cosine_similarity
from drafting_engine import run_drafting_engine
from generate_cheat_sheet import generate_cheat_sheet
from metadata_tagger import tag_job_metadata
from dom_cleanup import clean_html_to_text
from zero_shot_classifier import classify_onsite

os.environ.setdefault("DRAFT_MODE", "compose")
os.environ.setdefault("LOCAL_ONLY_MODE", "1")
os.environ.setdefault("JD_PROFILE_MODE", "deterministic")
os.environ.setdefault("COVER_HOOK_MODE", "template")
os.environ.setdefault("CHEAT_SHEET_MODE", "template")

from pipeline_env import apply_quality_batch_defaults

apply_quality_batch_defaults()

# CR-011: user-facing pipeline status vocabulary
STATUS_NEEDS_RETRY = "Needs Retry"
STATUS_REJECTED = "Rejected"
MAX_AUTO_RETRIES = 3


GPU_LOCK = threading.Lock()
PRINT_LOCK = threading.Lock()
_orig_print = print
def safe_print(*args, **kwargs):
    with PRINT_LOCK:
        _orig_print(*args, **kwargs)
print = safe_print

def check_is_duplicate_and_get_vector(db_path: str, jd_text: str):
    if not jd_text or len(jd_text) < 100:
        return False, None
    try:
        vector = get_embedding(jd_text[:3000])
        if not vector:
            return False, None
        import sqlite3, json
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("SELECT company, jd_vector FROM jobs WHERE jd_vector IS NOT NULL AND created_at >= datetime('now', '-14 days')")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            company, vec_str = row
            try:
                past_vector = json.loads(vec_str)
                if cosine_similarity(vector, past_vector) > 0.95:
                    return True, vector
            except Exception:
                pass
        return False, vector
    except Exception as e:
        print(f"  -> Error checking duplicate: {e}")
        return False, None

def extract_and_save_salary(db_path: str, job_id_prefix: str, company_name: str, jd_text: str):
    """Uses regex to extract salary from JD and updates SQLite."""
    if not jd_text: return
    try:
        import re
        # Looks for patterns like $120,000 - $150,000, $120k to $150k, 120k - 150k, etc.
        pattern = r'\$[\d,]+[kK]?(?:\s*(?:-|to|and)\s*\$[\d,]+[kK]?)?'
        matches = re.findall(pattern, jd_text)
        if matches:
            salary = matches[0]
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            if job_id_prefix:
                cursor.execute("UPDATE jobs SET salary_range = ? WHERE id LIKE ?", (salary, f"{job_id_prefix}%"))
            else:
                cursor.execute("UPDATE jobs SET salary_range = ? WHERE LOWER(company) = LOWER(?)", (salary, company_name))
            conn.commit()
            conn.close()
    except Exception as e:
        safe_print(f"  -> Error saving salary: {e}")

def ensure_jobs_schema(db_path: str):
    """Idempotent column adds for CR-021 (jd_vector, pre_score, etc.)."""
    if not db_path or not os.path.exists(db_path):
        return
    cols = [
        ("jd_vector", "TEXT"),
        ("pre_score", "INTEGER"),
        ("metadata_vector", "TEXT"),
        ("jd_text", "TEXT"),
        ("metadata_tags", "TEXT"),
    ]
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        for name, typ in cols:
            try:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {typ}")
            except sqlite3.OperationalError:
                pass
        _repair_jobs_fts(conn)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  -> Schema migration warning: {e}")


def _repair_jobs_fts(conn):
    """Standalone FTS index without UPDATE triggers (fixes pre_score/salary save errors)."""
    for trig in (
        "jobs_fts_ai", "jobs_fts_ad", "jobs_fts_au",
        "jobs_ai", "jobs_ad", "jobs_au",
    ):
        conn.execute(f"DROP TRIGGER IF EXISTS {trig}")
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs_fts'"
    ).fetchone()
    fts_sql = (row[0] if row else "") or ""
    needs_rebuild = not row or "content='jobs'" in fts_sql or "url" not in fts_sql
    if not needs_rebuild:
        return
    conn.execute("DROP TABLE IF EXISTS jobs_fts")
    conn.execute(
        """
        CREATE VIRTUAL TABLE jobs_fts USING fts5(
            company, title, summary, url,
            tokenize='porter unicode61'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO jobs_fts(rowid, company, title, summary, url)
        SELECT rowid,
            COALESCE(company, ''),
            COALESCE(title, ''),
            COALESCE(summary, ''),
            COALESCE(url, '')
        FROM jobs
        """
    )
    print("  -> Repaired jobs_fts index (no sync triggers on job UPDATE).")


def save_pre_score(db_path: str, job_id_prefix: str, company_name: str, score: int):
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        if job_id_prefix:
            conn.execute(
                "UPDATE jobs SET pre_score = ? WHERE id LIKE ?",
                (score, f"{job_id_prefix}%"),
            )
        else:
            conn.execute(
                "UPDATE jobs SET pre_score = ? WHERE LOWER(company) = LOWER(?)",
                (score, company_name),
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  -> Error saving pre_score: {e}")


def save_jd_vector(db_path: str, job_id_prefix: str, company_name: str, vector: list):
    if not vector: return
    try:
        import sqlite3, json
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        vec_str = json.dumps(vector)
        if job_id_prefix:
            cursor.execute("UPDATE jobs SET jd_vector = ? WHERE id LIKE ?", (vec_str, f"{job_id_prefix}%"))
        else:
            cursor.execute("UPDATE jobs SET jd_vector = ? WHERE LOWER(company) = LOWER(?)", (vec_str, company_name))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  -> Error saving jd_vector: {e}")


def _company_submission_dir(company_name: str) -> str:
    from company_slug import company_submission_dir
    return company_submission_dir(SUBMISSIONS_DIR, company_name)


def _resolve_display_company(db_path: str, company_name: str, job_id: str | None = None) -> str:
    """Implements FR-103 (CR-017): use DB company title for cover letter, not folder slug."""
    if not db_path or not os.path.exists(db_path):
        if "_" in company_name and " " not in company_name:
            return company_name.replace("_", " ").title()
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
                "SELECT company FROM jobs WHERE LOWER(company) = LOWER(?) OR LOWER(company) = LOWER(?) LIMIT 1",
                (company_name, company_name.replace("_", " ")),
            ).fetchone()
        conn.close()
        if row and row[0] and str(row[0]).strip():
            return str(row[0]).strip()
    except sqlite3.Error:
        pass
    if "_" in company_name and " " not in company_name:
        return company_name.replace("_", " ").title()
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
    """Staging file first, then DB jd_text, then saved Original_JD.txt from a prior draft attempt."""
    jd_text = _find_staging_jd(company, job_id)
    if jd_text and len(jd_text.strip()) >= 100:
        return jd_text
    db_path = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
    if job_id and os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path, timeout=10.0)
            row = conn.execute("SELECT jd_text FROM jobs WHERE id = ?", (job_id,)).fetchone()
            conn.close()
            if row and row[0] and len(str(row[0]).strip()) >= 100:
                return str(row[0])
        except sqlite3.Error:
            pass
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
        if row and row[0] is not None and int(row[0]) >= get_min_fit_score():
            return int(row[0]), (row[1] or ""), row[2]
    except Exception:
        pass
    return None


def save_job_score(db_path: str, job_id: str, score_total: int, score_breakdown_json: str, reason_summary: str, review_state: str = None):
    """Saves score details to job_scores using a 2-step is_latest transaction."""
    import uuid
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        cursor.execute("BEGIN TRANSACTION")
        
        # Step 1: Set is_latest = 0 on all existing scores for this job
        cursor.execute("UPDATE job_scores SET is_latest = 0 WHERE job_id = ?", (job_id,))
        
        # Step 2: Insert new score row with is_latest = 1
        new_id = str(uuid.uuid4())
        scored_at = datetime.utcnow().isoformat() + "Z"
        cursor.execute(
            """
            INSERT INTO job_scores (id, job_id, score_total, score_breakdown_json, reason_summary, review_state, scored_at, is_latest)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (new_id, job_id, score_total, score_breakdown_json, reason_summary, review_state, scored_at)
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  -> Error saving job score to job_scores table: {e}")

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


def passes_jd_keyword_gate(jd_text: str, prefs: dict = None, company_name: str = "") -> bool:
    """Zero-token pre-filter. Rejects JDs with blocked titles, industries, years, keywords, optional anchors."""
    from seniority_gate import check_years_gate, passes_title_gate
    from industry_gate import check_industry_gate
    from anchor_gate import check_anchor_gate
    from solo_pm_gate import check_solo_pm_gate
    from utils import passes_keyword_gate

    prefs = prefs or load_candidate_preferences()

    ok, reason = passes_title_gate(jd_text, prefs)
    if not ok:
        print(f"    [ZERO-TOKEN REJECT] {reason}", file=sys.stderr)
        return False

    ok, reason = check_years_gate(jd_text, prefs)
    if not ok:
        print(f"    [ZERO-TOKEN REJECT] {reason}", file=sys.stderr)
        return False

    # Implements FR-189 (CR-036)
    ok, reason = check_solo_pm_gate(jd_text, prefs)
    if not ok:
        print(f"    [ZERO-TOKEN REJECT] {reason}", file=sys.stderr)
        return False

    # Implements FR-170 (CR-027)
    ok, reason = check_industry_gate(company_name or "", jd_text, prefs=prefs)
    if not ok:
        print(f"    [ZERO-TOKEN REJECT] {reason}", file=sys.stderr)
        return False

    ok, reason = passes_keyword_gate(jd_text, prefs)
    if not ok:
        print(f"    [ZERO-TOKEN REJECT] {reason}", file=sys.stderr)
        return False

    # Implements FR-172 (CR-028) — off unless ANCHOR_GATE_ENABLED=1
    ok, reason = check_anchor_gate(jd_text, prefs)
    if not ok:
        print(f"    [ZERO-TOKEN REJECT] {reason}", file=sys.stderr)
        return False

    return True


def _pruned_work_exp_for_fit(jd_text: str, work_exp_summary: str, k: int = 8) -> str:
    """BM25-select relevant experience paragraphs for fit prompt (CR-021)."""
    from local_embeddings import BM25

    if not work_exp_summary or len(work_exp_summary) < 500:
        return work_exp_summary
    paras = [
        p.strip()
        for p in re.split(r"\n\s*\n", work_exp_summary)
        if len(p.strip()) > 40
    ]
    if not paras:
        lines = [ln for ln in work_exp_summary.splitlines() if ln.strip().startswith("*")]
        paras = lines[:40]
    if not paras:
        return work_exp_summary[:4000]
    bm25 = BM25(paras[:80])
    hits = bm25.get_top_n(jd_text[:3000], n=k)
    picked = [paras[i] for i, _ in hits if i < len(paras)]
    if not picked:
        return work_exp_summary[:4000]
    return "\n\n".join(picked)


def _location_stripped_rubric(job_fit_rules: str) -> str:
    """Remove §2.3 from rubric when location is pre-verified (local LLMs ignore prompt hints)."""
    return re.sub(
        r"### 2\.3 Location & Setting Gate.*?(?=\n---\n\n## 3\))",
        "### 2.3 Location & Setting Gate\n"
        "- **SKIPPED** — PRE-VERIFIED LOCATION POLICY already applied. Do not score or reject on location.\n",
        job_fit_rules,
        count=1,
        flags=re.DOTALL,
    )


def _fit_cites_location_reject(result: dict) -> bool:
    blob = " ".join([
        str(result.get("Summary") or ""),
        " ".join(result.get("TopFitReasons") or []),
        " ".join(result.get("RiskFlags") or []),
    ]).lower()
    phrases = (
        "location", "on-site", "onsite", "not remote", "remote role not",
        "remote requirement", "outside san diego", "san diego", "dallas",
        "atlanta", "hybrid", "in office", "in-office", "geograph",
        "work setting", "preference not met",
    )
    return any(p in blob for p in phrases)


def _fit_score_int(result: dict) -> int | None:
    raw = result.get("Score")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def _looks_like_false_fast_gate(result: dict) -> bool:
    """Local qwen often re-runs Stage A and returns score < 30 despite deterministic gates passing."""
    if not result or str(result.get("Decision", "")).upper() != "NO":
        return False
    score = _fit_score_int(result)
    return score is not None and score <= 35


def _normalize_fit_result(result: dict) -> dict | None:
    """Coerce common local-LLM JSON mistakes into a usable fit payload."""
    if not result or not isinstance(result, dict):
        return None
    decision = result.get("Decision")
    if isinstance(decision, dict):
        decision = next(iter(decision.values()), "NO")
    score = _fit_score_int(result)
    summary = result.get("Summary")
    if isinstance(summary, dict):
        summary = next(iter(summary.values()), "")
    if score is None or not str(decision).strip():
        return None
    out = dict(result)
    out["Decision"] = str(decision).upper()
    out["Score"] = score
    out["Summary"] = str(summary or "").strip()
    return out


def _call_fit_llm(
    truncated_jd,
    work_exp_for_fit,
    job_fit_rules,
    prefs_str,
    location_lock,
    fit_schema,
):
    prompt = f"""
    You are the JobAgent Job-Fit Decision Engine.
    
    CANDIDATE PREFERENCES:
    {prefs_str}
    {location_lock}
    GROUND TRUTH (Jason Taylor's Profile — BM25-pruned):
    {work_exp_for_fit}
    
    JOB DESCRIPTION (first {SCORING_JD_MAX_CHARS} chars):
    {truncated_jd}
    
    RULES & SCORING PROTOCOL:
    {job_fit_rules}
    
    IMPORTANT: Deterministic pre-filters already evaluated title blocklist, years, industry,
    keywords, and location before this call. Do NOT re-run Stage A fast gate.
    Start at Stage B (0-100 scoring). Never return score below 40 for location, title blocklist,
    or remote/hybrid — those gates already passed.
    Senior in the title is allowed when required years are within experience_range.max.
    Do not reject solely for AI tools mentions; reject only for primary AI/ML model ownership roles.
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

    from llm_stages import call_llm_stage
    from pipeline_env import fit_llm_timeout_sec, fit_model_override, fit_num_predict

    fit_model = fit_model_override()
    system_instruction = (
        "You are the Job-Fit Decision Engine. Output JSON strictly.\n"
        "STRICT POLICY: Do NOT penalize the candidate for vertical industry or customer-base (B2C vs B2B) differences. "
        "Score on transferable PM craft skills (platform stability, roadmap, cross-functional delivery, system complexity). "
        "Respect the pre-verified location and years gates. Do not penalize or reject for location or years."
    )
    result = call_llm_stage(
        "fit",
        system_instruction,
        prompt,
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=fit_schema,
        model=fit_model,
        options_override={"num_predict": fit_num_predict()},
        request_timeout=fit_llm_timeout_sec(),
    )

    if not result or not result.strip():
        return None

    try:
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


def _call_fit_scoring_only(
    truncated_jd,
    work_exp_for_fit,
    prefs_str,
    loc_verdict,
    fit_schema,
    scoring_context: str = "",
):
    """Stage-B-only scoring — primary path after deterministic gates pass (CR-035)."""
    prompt = f"""
    You are scoring job fit ONLY. Deterministic gates already passed (title, years, industry, keywords, location).
    Location policy: {loc_verdict}. Ignore city/office/hybrid/remote mentions — location is NOT a scoring factor.

    {scoring_context}

    CANDIDATE PREFERENCES:
    {prefs_str}

    GROUND TRUTH (candidate profile excerpt):
    {work_exp_for_fit}

    JOB DESCRIPTION:
    {truncated_jd}

    Score alignment on: PM title match, years of experience, agile/roadmap/stakeholder work,
    transferable PM skills (platform, cross-functional, data complexity) — not industry
    vertical or B2C/B2B customer base alone, team structure, and required_anchors.
    Product Manager and Senior Product Manager titles match target_role Product Manager when years fit.
    Do NOT reject for location or optional domain/vertical gaps when DOMAIN_REQUIREMENT: OPTIONAL is set.

    Return a single JSON object with string Decision ("YES" or "NO"), integer Score (0-100),
    string Summary, and optional TopFitReasons / RiskFlags arrays. Do not nest values.
    """
    from llm_stages import call_llm_stage
    from pipeline_env import fit_llm_timeout_sec, fit_model_override, fit_num_predict

    fit_model = fit_model_override()
    system_instruction = (
        "You are scoring job fit ONLY. Output JSON strictly.\n"
        "STRICT POLICY: Do NOT penalize or reject the candidate for vertical industry or customer-base (B2C vs B2B) differences. "
        "Score on transferable PM craft skills (platform stability, roadmap, cross-functional delivery, system complexity). "
        "Never cite location or years of experience as a reject reason, as they are pre-verified."
    )
    raw = call_llm_stage(
        "fit",
        system_instruction,
        prompt,
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=fit_schema,
        model=fit_model,
        options_override={"num_predict": fit_num_predict()},
        request_timeout=fit_llm_timeout_sec(),
    )
    if not raw or not raw.strip():
        return None
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = match.group(0).strip() if match else raw.strip()
        return _normalize_fit_result(json.loads(payload))
    except json.JSONDecodeError:
        return None


def evaluate_job_fit(jd_text, work_exp_summary, job_fit_rules, prefs):
    """Uses condensed summary and dynamic candidate preferences to minimize token cost."""
    from zero_shot_classifier import resolve_location_verdict, location_lock_prompt_block
    from fit_policy import (
        apply_anchor_floor,
        build_fit_scoring_context,
        gates_passed_rubric,
        strip_false_years_penalty,
        strip_location_risk_flags,
        _fit_cites_years_reject,
    )

    # Truncate JD — first 1500 chars contain ~90% of signal for scoring
    truncated_jd = jd_text[:SCORING_JD_MAX_CHARS] if len(jd_text) > SCORING_JD_MAX_CHARS else jd_text
    work_exp_for_fit = _pruned_work_exp_for_fit(truncated_jd, work_exp_summary)

    loc_verdict, loc_detail = resolve_location_verdict(jd_text)
    if loc_verdict == "REJECT":
        return {
            "Decision": "NO",
            "Score": 0,
            "Confidence": "High",
            "Summary": loc_detail[:120],
            "TopFitReasons": [],
            "RiskFlags": ["location_policy_reject"],
        }

    location_lock = location_lock_prompt_block(loc_verdict, loc_detail)
    scoring_context = build_fit_scoring_context(
        jd_text, prefs, loc_verdict, loc_detail, location_lock,
    )
    rules_for_fit = gates_passed_rubric(
        _location_stripped_rubric(job_fit_rules)
        if loc_verdict in ("REMOTE_OK", "SD_LOCAL_OK")
        else job_fit_rules,
    )

    prefs_str = json.dumps(prefs, indent=2) if prefs else "{}"
    min_score = get_min_fit_score()

    fit_schema = {
        "type": "object",
        "properties": {
            "Decision": {"type": "string"},
            "Score": {"type": "integer"},
            "Confidence": {"type": "string"},
            "Summary": {"type": "string"},
            "TopFitReasons": {"type": "array", "items": {"type": "string"}},
            "RiskFlags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["Decision", "Score", "Summary"],
    }

    # Primary path: Stage-B scoring only (CR-035)
    print("  -> [FIT] Scoring-only primary path (deterministic gates already passed).", file=sys.stderr)
    result = _call_fit_scoring_only(
        truncated_jd, work_exp_for_fit, prefs_str, loc_verdict, fit_schema, scoring_context,
    )

    if not result:
        print("  -> [FIT] Scoring-only returned no result — fallback to Stage-B rubric LLM.", file=sys.stderr)
        result = _call_fit_llm(
            truncated_jd, work_exp_for_fit, rules_for_fit, prefs_str,
            location_lock + "\n" + scoring_context, fit_schema,
        )

    if (
        result
        and loc_verdict in ("REMOTE_OK", "SD_LOCAL_OK")
        and str(result.get("Decision", "")).upper() == "NO"
        and _fit_cites_location_reject(result)
    ):
        print(
            "  -> [FIT] Model cited location after REMOTE_OK — retry scoring-only.",
            file=sys.stderr,
        )
        result = _call_fit_scoring_only(
            truncated_jd, work_exp_for_fit, prefs_str, loc_verdict, fit_schema,
            scoring_context + "\nRETRY: Do not cite location. Location is satisfied.\n",
        )

    if (
        result
        and str(result.get("Decision", "")).upper() == "NO"
        and _looks_like_false_fast_gate(result)
    ):
        print(
            "  -> [FIT] False fast-gate score detected — retry scoring-only.",
            file=sys.stderr,
        )
        retry = _call_fit_scoring_only(
            truncated_jd, work_exp_for_fit, prefs_str, loc_verdict, fit_schema, scoring_context,
        )
        if retry:
            result = retry

    if (
        result
        and str(result.get("Decision", "")).upper() == "NO"
        and _fit_cites_years_reject(result)
    ):
        print(
            "  -> [FIT] Model cited years/seniority after years gate passed — retry scoring-only.",
            file=sys.stderr,
        )
        retry = _call_fit_scoring_only(
            truncated_jd, work_exp_for_fit, prefs_str, loc_verdict, fit_schema,
            scoring_context + "\nRETRY: Years are within cap. Do not penalize years or Senior title.\n",
        )
        if retry:
            result = retry

    result = _normalize_fit_result(result) if result else result
    result = strip_false_years_penalty(result, truncated_jd, prefs)
    result = strip_location_risk_flags(result, loc_verdict)
    result = apply_anchor_floor(result, jd_text, prefs, min_score)
    return _normalize_fit_result(result) if result else result

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
    if not passes_jd_keyword_gate(jd_text, prefs, company_name=company or ""):
        print(json.dumps({"id": "gate", "status": "done", "summary": "Rejected (zero-token gate: title/years/industry/keywords/anchors)."}))
        print(json.dumps({"score": 0, "passed": False}))
        return

    is_onsite, onsite_reason = classify_onsite(jd_text)
    if is_onsite:
        print(json.dumps({"id": "gate", "status": "done", "summary": f"Rejected (location gate: {onsite_reason})."}))
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
        with GPU_LOCK:
            result = evaluate_job_fit(jd_text, work_exp_summary, fit_rules, prefs)
        if not result:
            print(json.dumps({"id": "fit", "status": "error", "summary": "Evaluation failed."}))
            return

        score = result.get("Score", 0)
        decision = result.get("Decision", "NO")
        summary = result.get("Summary", "")

        if decision == "NO" or score < get_min_fit_score():
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
        with GPU_LOCK:
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
        with GPU_LOCK:
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

    stats = {"processed": 0, "skipped_duplicates": 0, "rejected": 0, "drafted": 0, "errors": 0}

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

    from pre_score_jobs import pre_score_job, _anchor_embedding
    from pipeline_env import (
        batch_fast_mode,
        batch_inter_job_sleep_sec,
        batch_parallel_workers,
        batch_unload_models_between_jobs,
        fit_eval_top_n,
        skip_duplicate_vector_check,
        skip_metadata_tagger,
    )

    anchor_vec = _anchor_embedding(work_exp_summary)
    scored_files = []
    for fp in job_files:
        jd_preview = load_file(fp) or ""
        ps = pre_score_job(jd_preview, work_exp_summary, anchor_vec=anchor_vec)
        scored_files.append((ps, fp))
    scored_files.sort(key=lambda x: x[0], reverse=True)
    job_files = [fp for _, fp in scored_files]
    top_n = fit_eval_top_n()
    if top_n and len(job_files) > top_n:
        print(f"Pre-score cap: evaluating top {top_n} of {len(scored_files)} jobs (FIT_EVAL_TOP_N).")
        job_files = job_files[:top_n]

    print(f"Found {len(scored_files)} jobs in batch queue (sorted by pre-score).")
    if batch_fast_mode():
        print(
            "BATCH_FAST_MODE=1: phi3.5 fit, shorter tokens, no tagger/dedup embed, "
            "no inter-job sleep, models stay loaded."
        )
    elif os.environ.get("LOCAL_ONLY_MODE", "").lower() in ("1", "true", "yes"):
        print(
            "Quality batch profile: qwen fit (unchanged), 768-token fit cap, "
            "2s between jobs, models stay loaded, cached tag embeddings."
        )

    db_path = os.path.join(PROJECT_ROOT, "jobagent.sqlite")
    db_exists = os.path.exists(db_path)
    if db_exists:
        ensure_jobs_schema(db_path)

    total_jobs = len(job_files)
    job_failures = 0
    batch_completed = {"n": 0}

    def _emit_batch_progress(company: str, phase: str):
        print(
            f"[BATCH_PROGRESS] completed={batch_completed['n']} total={total_jobs} "
            f"current={company} phase={phase}"
        )

    print(
        f"[BATCH_PROGRESS] completed=0 total={total_jobs} current=queue phase=starting"
    )

    def process_single_job(idx, filepath):
        job_failures_local = 0
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
        _emit_batch_progress(company_name, "evaluating")
        
        jd_text = load_file(filepath)

        if not jd_text or len(jd_text.strip()) < 100:
            print(f"  -> Skipping. File {filename} seems empty or too short.")
            _cleanup_staging_file(filepath, filename)
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "skipped")
            return job_failures_local

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
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "skipped")
            return job_failures_local

        if status_to_check and status_to_check not in ('New', 'Drafted'):
            print(f"  -> Skipping. Already evaluated (status: {status_to_check}).")
            _cleanup_staging_file(filepath, filename)
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "skipped")
            return job_failures_local

        # DOM Cleanup Pre-Processor
        jd_text = clean_html_to_text(jd_text)

        if db_exists:
            ps = pre_score_job(jd_text, work_exp_summary, anchor_vec=anchor_vec)
            save_pre_score(db_path, job_id_prefix, company_name, ps)
            print(f"  -> Pre-score: {ps}/100")

        if not jd_text or len(jd_text.strip()) < 100:
            print(f"  -> Skipping. File {filename} seems empty or too short after cleanup.")
            _cleanup_staging_file(filepath, filename)
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "skipped")
            return job_failures_local

        # Zero-token keyword gate
        if db_exists:
            extract_and_save_salary(db_path, job_id_prefix, company_name, jd_text)
            
            if not skip_metadata_tagger():
                tag_job_metadata(db_path, job_id_prefix, company_name, jd_text)

            is_dup, vec = (False, None)
            if not skip_duplicate_vector_check():
                is_dup, vec = check_is_duplicate_and_get_vector(db_path, jd_text)
            if is_dup:
                print(f"  -> Skipping. JD is a >95% vector match with a recently processed job (Duplicate/Repost).")
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
                        _mark_job_rejected(db_path, job_id_prefix, company_name, url, title, "Duplicate JD (Vector Similarity)")
                    else:
                        conn.close()
                except Exception as e:
                    pass
                _cleanup_staging_file(filepath, filename)
                batch_completed["n"] += 1
                _emit_batch_progress(company_name, "duplicate")
                return job_failures_local
            if vec:
                save_jd_vector(db_path, job_id_prefix, company_name, vec)

        if not passes_jd_keyword_gate(jd_text, prefs, company_name=company_name):
            print(f"  -> Skipping. JD failed zero-token gate (keyword/title/industry/anchor).")
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
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "keyword_reject")
            return job_failures_local

        # Zero-Shot On-Site Classifier Gate
        is_onsite, reason = classify_onsite(jd_text)
        if is_onsite:
            print(f"  -> Skipping. Zero-Shot Classifier detected stealth on-site/hybrid outside local area: {reason}")
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
                            f"Not a fit — Stealth On-site detected: {reason}",
                        )
                        print(f"  -> Marked as '{STATUS_REJECTED}' (On-site gate).")
                    else:
                        conn.close()
                except Exception as e:
                    print(f"  -> Error handling on-site gate db update: {e}")
            _cleanup_staging_file(filepath, filename)
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "onsite_reject")
            return job_failures_local

        print(f"  -> Evaluating fit against v3.2 Rubric...")
        _emit_batch_progress(company_name, "fit_llm")
        with GPU_LOCK:
            result = evaluate_job_fit(jd_text, work_exp_summary, fit_rules, prefs)

        if not result:
            print("  -> Evaluation failed due to an error.")
            job_failures_local += 1
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
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "fit_error")
            return job_failures_local

        score = result.get("Score", 0)
        decision = result.get("Decision", "NO")
        print(f"  -> Result: {decision} (Score: {score})")
        print(f"  -> Summary: {result.get('Summary')}")

        if decision == "NO" or score < get_min_fit_score():
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
                            f"Not a fit — score {score} below threshold ({get_min_fit_score()})",
                            score=score,
                        )
                        print(f"  -> Marked as '{STATUS_REJECTED}' (low fit score).")
                    else:
                        conn.close()
                except Exception as e:
                    print(f"  -> Error handling low score db update: {e}")
            _cleanup_staging_file(filepath, filename)
            batch_completed["n"] += 1
            _emit_batch_progress(company_name, "rejected")
            return job_failures_local

        # Load full work experience only for YES decisions
        work_exp_full = load_file(WORK_EXP_FILE)
        print(f"[JOB_PROGRESS] Job {idx + 1}/{total_jobs}: Generating assets for {company_name}...")
        _emit_batch_progress(company_name, "drafting")
        print(f"  -> [GATEKEEPER PASS] Score: {score}. Running drafting engine...")
        
        from drafting_errors import SelfCorrectionError
        draft_error = None
        max_retries = 1
        retries = 0
        
        while retries <= max_retries:
            try:
                display = _resolve_display_company(db_path, company_name, job_id_prefix) if db_exists else company_name
                with GPU_LOCK:
                    run_drafting_engine(company_name, jd_text, work_exp_full, result, display_name=display)
                try:
                    with GPU_LOCK:
                        generate_cheat_sheet(company_name, display_name=display)
                except Exception as e:
                    print(f"  -> [Cheat sheet warning] {e}")
                draft_error = None
                break
            except SelfCorrectionError as e:
                if retries < max_retries:
                    print(f"  -> [SELF CORRECTION] Formatting error detected: {e}. Retrying generator...")
                    os.environ["DRAFTING_FEEDBACK"] = str(e)
                    retries += 1
                else:
                    draft_error = e
                    print(f"  -> [DRAFT ERROR] Asset generation failed after retries: {e}")
                    break
            except Exception as e:
                draft_error = e
                print(f"  -> [DRAFT ERROR] Asset generation failed: {e}")
                break

        if draft_error or not _has_required_pdfs(company_name):
            job_failures_local += 1
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
                
                # Fetch full job ID from DB to write score details
                conn = sqlite3.connect(db_path, timeout=30.0)
                cursor = conn.cursor()
                if job_id_prefix:
                    cursor.execute("SELECT id FROM jobs WHERE id LIKE ?", (f"{job_id_prefix}%",))
                else:
                    cursor.execute("SELECT id FROM jobs WHERE LOWER(company) = LOWER(?)", (company_name,))
                db_job_row = cursor.fetchone()
                conn.close()
                if db_job_row:
                    actual_job_id = db_job_row[0]
                    # Route to priority review state based on score
                    review_state = "high_priority" if score >= 85 else ("review_queue" if score >= 70 else ("low_priority" if score >= 50 else "hidden"))
                    
                    # Extract raw component scores or map default breakdown
                    breakdown = {
                        "role_family_match": result.get("role_family_match", int(score * 0.3)),
                        "domain_match": result.get("domain_match", int(score * 0.2)),
                        "seniority_match": result.get("seniority_match", int(score * 0.15)),
                        "work_arrangement": result.get("work_arrangement", int(score * 0.15)),
                        "company_desirability": result.get("company_desirability", int(score * 0.1)),
                        "location_compatibility": result.get("location_compatibility", int(score * 0.05)),
                        "compensation_signal": result.get("compensation_signal", int(score * 0.05)),
                    }
                    save_job_score(
                        db_path,
                        actual_job_id,
                        score,
                        json.dumps(breakdown),
                        result.get("Summary", ""),
                        review_state=review_state
                    )
            except Exception as e:
                print(f"  -> Error updating database: {e}")
                job_failures_local += 1

        _cleanup_staging_file(filepath, filename)

        batch_completed["n"] += 1
        _emit_batch_progress(company_name, "done")
        print(f"[JOB_DONE] {idx + 1}/{total_jobs}: {company_name}")

        if batch_unload_models_between_jobs():
            unload_local_models()

        sleep_s = batch_inter_job_sleep_sec()
        if sleep_s > 0:
            print(f"  -> Sleeping for {sleep_s:g}s before next job...")
            time.sleep(sleep_s)

        return job_failures_local

    workers = batch_parallel_workers()
    print(f"Batch workers: {workers} (set BATCH_PARALLEL_WORKERS to raise; default 1 = sequential).")
    if workers <= 1:
        for idx, filepath in enumerate(job_files):
            job_failures += process_single_job(idx, filepath)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(process_single_job, idx, filepath)
                for idx, filepath in enumerate(job_files)
            ]
            for future in concurrent.futures.as_completed(futures):
                job_failures += future.result()

    if job_failures > 0:
        msg = f"Batch queue drained with {job_failures} job failure(s)."
        print(f"\n[BATCH_SUMMARY] {msg} See logs above.")
        send_notification(msg, "jobagent_alerts")
    else:
        msg = "Batch queue processed successfully."
        print(f"\n[BATCH_SUMMARY] {msg}")
        send_notification(msg, "jobagent_alerts")

if __name__ == "__main__":
    from utils import init_pipeline_prefs
    init_pipeline_prefs()
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
