# Implements FR-132, FR-133, FR-149, FR-150 (CR-021); FR-006–FR-009, FR-109 (CR-019).
# Pipeline defaults: FR-131 via pipeline_env / setdefault below.
import os
import json
import glob
import sys
import sqlite3
import re
from datetime import datetime
import threading
from utils import (
    load_file, JOBS_DIR, PROJECT_ROOT, SUBMISSIONS_DIR,
    load_candidate_preferences,
)
from local_embeddings import get_embedding, cosine_similarity

from pipeline_env import apply_quality_batch_defaults

apply_quality_batch_defaults()

# CR-011: user-facing pipeline status vocabulary
STATUS_NEEDS_RETRY = "Needs Retry"
STATUS_REJECTED = "Rejected"
MAX_AUTO_RETRIES = 3


def _effective_jd_body(jd_text: str) -> str:
    """Strip staging headers (Title:/URL:) for length checks and DB persistence."""
    if not jd_text:
        return ""
    lines = jd_text.strip().splitlines()
    body_lines = []
    past_headers = False
    for line in lines:
        stripped = line.strip()
        if not past_headers:
            if stripped.startswith("Title:") or stripped.startswith("URL:") or not stripped:
                continue
            past_headers = True
        body_lines.append(line)
    if body_lines:
        return "\n".join(body_lines).strip()
    return jd_text.strip()


def get_min_jd_chars_evaluate(prefs=None) -> int:
    prefs = prefs or load_candidate_preferences()
    raw = prefs.get("min_jd_chars_evaluate", 800)
    try:
        return max(200, int(raw))
    except (TypeError, ValueError):
        return 800


def _jd_meets_evaluate_threshold(jd_text: str, prefs=None) -> bool:
    return len(_effective_jd_body(jd_text or "")) >= get_min_jd_chars_evaluate(prefs)


def _persist_jd_text_if_missing(db_path, job_id_prefix, company_name, jd_text: str) -> None:
    body = _effective_jd_body(jd_text or "")
    if len(body) < 200:
        return
    conn = sqlite3.connect(db_path, timeout=30.0)
    cursor = conn.cursor()
    if job_id_prefix:
        cursor.execute(
            """
            UPDATE jobs SET jd_text = ?
            WHERE id LIKE ? AND (jd_text IS NULL OR LENGTH(TRIM(jd_text)) < 200)
            """,
            (body, f"{job_id_prefix}%"),
        )
    else:
        cursor.execute(
            """
            UPDATE jobs SET jd_text = ?
            WHERE LOWER(company) = LOWER(?) AND (jd_text IS NULL OR LENGTH(TRIM(jd_text)) < 200)
            """,
            (body, company_name),
        )
    conn.commit()
    conn.close()


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
    from company_slug import resolve_company_display_name

    return resolve_company_display_name(
        company_name,
        db_path=db_path,
        job_id=job_id,
    )


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


def _load_job_title(db_path: str, company: str, job_id: str | None = None) -> str:
    if not os.path.exists(db_path):
        return ""
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        if job_id:
            row = conn.execute("SELECT title FROM jobs WHERE id = ?", (job_id,)).fetchone()
        elif job_id is None and company:
            row = conn.execute(
                "SELECT title FROM jobs WHERE LOWER(company) = LOWER(?) ORDER BY rowid DESC LIMIT 1",
                (company,),
            ).fetchone()
        else:
            row = None
        conn.close()
        if row and row[0]:
            return str(row[0]).strip()
    except sqlite3.Error:
        pass
    return ""


def _load_jd_for_job(company: str, job_id: str | None = None) -> str:
    """Staging file first, then DB jd_text, then saved Original_JD.txt from a prior draft attempt."""
    jd_text = _find_staging_jd(company, job_id)
    if jd_text and len(jd_text.strip()) >= 100:
        return jd_text
    db_path = os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite")
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


def _set_backlog(db_path, job_id_prefix, company_name, score, summary: str, jd_text: str | None = None):
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
    if jd_text:
        _persist_jd_text_if_missing(db_path, job_id_prefix, company_name, jd_text)


def _cleanup_staging_file(filepath: str, filename: str):
    try:
        os.remove(filepath)
        print(f"  -> Cleaned up staging file: {filename}")
    except Exception:
        pass


def passes_jd_keyword_gate(jd_text: str, prefs: dict = None, company_name: str = "", job_title: str = "") -> bool:
    """Zero-token pre-filter. Rejects JDs with blocked titles, industries, years, keywords, optional anchors."""
    from seniority_gate import check_years_gate, passes_title_gate
    from industry_gate import check_industry_gate
    from anchor_gate import check_anchor_gate
    from solo_pm_gate import check_solo_pm_gate
    from utils import passes_keyword_gate

    prefs = prefs or load_candidate_preferences()

    blocked = [c.strip().lower() for c in (prefs.get("blocked_companies") or []) if c.strip()]
    if blocked and company_name:
        company_key = company_name.strip().lower()
        for entry in blocked:
            if entry in company_key or company_key in entry:
                print(f"    [ZERO-TOKEN REJECT] company_blocked:{entry}", file=sys.stderr)
                return False

    ok, reason = passes_title_gate(jd_text, prefs, fallback_title=job_title)
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


# CR-093 (2026-08-19): removed the entire old fit-scoring + single/batch CLI
# orchestration surface that used to live below this point --
# _pruned_work_exp_for_fit, _location_stripped_rubric, _fit_cites_location_reject,
# _fit_score_int, _looks_like_false_fast_gate, _normalize_fit_result, _call_fit_llm,
# _call_fit_scoring_only, evaluate_job_fit, process_single, process_batch, and the
# __main__ CLI block (--mode single | batch). Jason: "we need to get out of the
# habit of replacing things and keeping the old stuff... erase any mention of the
# old fit." Confirmed dead: the only live triggers were server/routes/pipeline.ts's
# /api/evaluate route (Find New Jobs page, confirmed dead by Jason) and
# server/scout.ts's Sync EVALUATE stage (already removed 2026-08-04, see
# SESSION-HANDOFF-2026-08-04-URGENT-disable-silent-autodraft.md). The real fit-
# scoring engine now lives entirely in scripts/build_stage0_fit_gate.py +
# scripts/evidence_scale.py (CR-093), reached via scripts/run_submission.py --
# see docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md.
# This module is now a pure helper library (DB/JD/keyword-gate utilities used by
# other scripts) -- no longer directly executable; the CLI entry point is gone.
