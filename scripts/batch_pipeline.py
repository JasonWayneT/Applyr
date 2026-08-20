# Implements FR-132, FR-133, FR-149, FR-150 (CR-021); FR-006–FR-009, FR-109 (CR-019).
# Pipeline defaults: FR-131 via pipeline_env / setdefault below.
import re
import sys

from pipeline_env import apply_quality_batch_defaults
from utils import load_candidate_preferences

apply_quality_batch_defaults()


def _resolve_display_company(db_path: str, company_name: str, job_id: str | None = None) -> str:
    """Implements FR-103 (CR-017): use DB company title for cover letter, not folder slug."""
    from company_slug import resolve_company_display_name

    return resolve_company_display_name(
        company_name,
        db_path=db_path,
        job_id=job_id,
    )


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
# __main__ CLI block (--mode single | batch).
# 2026-08-20: also removed leftover evaluate/draft helpers with no live callers
# (_effective_jd_body, get_min_jd_chars_evaluate, _jd_meets_evaluate_threshold,
# _company_submission_dir, _has_required_pdfs). Remaining: keyword gate +
# backlog-summary helpers used by refresh_backlog_summaries.py and tests.
# Fit scoring lives in build_stage0_fit_gate.py + evidence_scale.py via
# run_submission.py.
