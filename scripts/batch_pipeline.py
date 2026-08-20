# Implements FR-132, FR-133, FR-149, FR-150 (CR-021); FR-006–FR-009, FR-109 (CR-019).
# Pipeline defaults: FR-131 via pipeline_env / setdefault below.
import os
import sys
import re
from utils import SUBMISSIONS_DIR, load_candidate_preferences

from pipeline_env import apply_quality_batch_defaults

apply_quality_batch_defaults()


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
