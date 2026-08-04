# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Evaluate a single JD through gates + LLM fit only (no drafting)."""
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from utils import (
    init_pipeline_prefs,
    load_file,
    FIT_ENGINE_FILE,
    WORK_EXP_SUMMARY_FILE,
    WORK_EXP_FILE,
    get_min_fit_score,
    load_candidate_preferences,
)
from batch_pipeline import evaluate_job_fit, passes_jd_keyword_gate
from seniority_gate import check_years_gate, passes_title_gate
from industry_gate import check_industry_gate
from utils import passes_keyword_gate
from anchor_gate import check_anchor_gate
from solo_pm_gate import check_solo_pm_gate
from domain_gate import get_domain_gaps
from zero_shot_classifier import resolve_location_verdict, classify_onsite


def main() -> int:
    init_pipeline_prefs()
    if len(sys.argv) < 2:
        print("Usage: evaluate_jd_only.py <jd_file> [company]", file=sys.stderr)
        return 2

    jd_path = sys.argv[1]
    company = sys.argv[2] if len(sys.argv) > 2 else "Brown & Brown"
    jd_text = open(jd_path, encoding="utf-8").read()
    prefs = load_candidate_preferences()
    min_score = get_min_fit_score()

    gates = {}
    ok, reason = passes_title_gate(jd_text, prefs)
    gates["title"] = {"pass": ok, "reason": reason}
    ok, reason = check_years_gate(jd_text, prefs)
    gates["years"] = {"pass": ok, "reason": reason}
    ok, reason = check_solo_pm_gate(jd_text, prefs)
    gates["solo_pm"] = {"pass": ok, "reason": reason}
    gates["domain_gaps"] = get_domain_gaps(jd_text, prefs)
    ok, reason = check_industry_gate(company, jd_text, prefs=prefs)
    gates["industry"] = {"pass": ok, "reason": reason}
    ok, reason = passes_keyword_gate(jd_text, prefs)
    gates["keywords"] = {"pass": ok, "reason": reason}
    ok, reason = check_anchor_gate(jd_text, prefs)
    gates["anchors"] = {"pass": ok, "reason": reason}

    loc_verdict, loc_detail = resolve_location_verdict(jd_text)
    gates["location"] = {"verdict": loc_verdict, "detail": loc_detail}
    is_onsite, onsite_reason = classify_onsite(jd_text)
    gates["location"]["onsite_reject"] = is_onsite

    zero_token_pass = passes_jd_keyword_gate(jd_text, prefs, company_name=company)
    print(json.dumps({"stage": "gates", "zero_token_pass": zero_token_pass, "gates": gates}, indent=2))

    if is_onsite:
        print(json.dumps({"passed": False, "score": 0, "decision": "LOCATION_REJECT", "summary": onsite_reason}))
        return 0

    if not zero_token_pass:
        print(json.dumps({"passed": False, "score": None, "decision": "GATE_REJECT"}))
        return 0

    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    fit_rules = load_file(FIT_ENGINE_FILE)
    result = evaluate_job_fit(jd_text, work_exp, fit_rules, prefs)
    if not result:
        print(json.dumps({"passed": False, "score": None, "decision": "LLM_ERROR"}))
        return 1

    score = int(result.get("Score", 0))
    decision = result.get("Decision", "NO")
    passed = decision != "NO" and score >= min_score
    out = {
        "passed": passed,
        "score": score,
        "decision": decision,
        "min_fit_score": min_score,
        "summary": result.get("Summary", ""),
        "top_fit_reasons": result.get("TopFitReasons", []),
        "risk_flags": result.get("RiskFlags", []),
        "confidence": result.get("Confidence", ""),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
