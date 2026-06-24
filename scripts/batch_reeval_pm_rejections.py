#!/usr/bin/env python3
"""Batch re-evaluate PM rejections (7d) that have JD text. FR-189 / review tooling."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from utils import init_pipeline_prefs, load_file, FIT_ENGINE_FILE, WORK_EXP_SUMMARY_FILE, WORK_EXP_FILE, get_min_fit_score, load_candidate_preferences
from batch_pipeline import evaluate_job_fit, passes_jd_keyword_gate
from seniority_gate import check_years_gate, passes_title_gate
from industry_gate import check_industry_gate
from solo_pm_gate import check_solo_pm_gate
from domain_gate import get_domain_gaps
from utils import passes_keyword_gate
from anchor_gate import check_anchor_gate
from zero_shot_classifier import resolve_location_verdict, classify_onsite

PM = [
    "product manager", "product owner", "technical product manager",
    "platform product manager", "digital product manager", "senior product manager",
    "associate product manager", "lead product manager", "group product manager",
    "product management",
]

ORDER = [
    "llm_fit_score_28",
    "llm_fit_below_threshold",
    "location_gate",
    "zero_token_gate",
    "duplicate_jd",
    "other",
    "rejected_null_score",
]


def looks_pm(title: str) -> bool:
    t = (title or "").lower()
    return any(p in t for p in PM)


def db_category(job: dict) -> str:
    s = (job.get("summary") or "").lower()
    score = job.get("score")
    if "duplicate" in s:
        return "duplicate_jd"
    if "keyword" in s or "title gate" in s or "zero-token" in s or "solo_pm" in s:
        return "zero_token_gate"
    if "on-site" in s or "onsite" in s or ("location" in s and "below" not in s):
        return "location_gate"
    if score == 28:
        return "llm_fit_score_28"
    if score is not None and score < 72:
        return "llm_fit_below_threshold"
    if score is None:
        return "rejected_null_score"
    return "other"


def gate_snapshot(jd_text: str, company: str, prefs: dict) -> dict:
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
    is_onsite, onsite_reason = classify_onsite(jd_text)
    gates["location"] = {"verdict": loc_verdict, "detail": loc_detail, "onsite_reject": is_onsite, "onsite_reason": onsite_reason}
    gates["zero_token_pass"] = passes_jd_keyword_gate(jd_text, prefs, company_name=company)
    return gates


def first_failing_gate(gates: dict) -> str | None:
    if gates.get("location", {}).get("onsite_reject"):
        return f"location:{gates['location'].get('onsite_reason') or 'onsite_reject'}"
    if not gates.get("zero_token_pass"):
        for name in ("title", "years", "solo_pm", "industry", "keywords", "anchors"):
            g = gates.get(name, {})
            if g.get("pass") is False:
                return f"{name}:{g.get('reason', '')}"
        return "zero_token:unknown"
    return None


def queue() -> list[dict]:
    cutoff = (datetime(2026, 6, 2) - timedelta(days=7)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(os.path.join(PROJECT_ROOT, "data", "jobagent.sqlite"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, company, title, url, score, pre_score, summary, jd_text, source_site, created_at
        FROM jobs WHERE status='Rejected' AND date(created_at) >= date(?)
          AND jd_text IS NOT NULL AND LENGTH(TRIM(jd_text)) >= 100
        ORDER BY created_at DESC
        """,
        (cutoff,),
    ).fetchall()
    conn.close()
    out = [dict(r) for r in rows if looks_pm(r["title"])]
    for j in out:
        j["db_category"] = db_category(j)
    out.sort(key=lambda j: (ORDER.index(j["db_category"]) if j["db_category"] in ORDER else 99, j.get("created_at") or ""))
    return out


def main() -> int:
    init_pipeline_prefs()
    prefs = load_candidate_preferences()
    min_score = get_min_fit_score()
    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    fit_rules = load_file(FIT_ENGINE_FILE)

    jobs = queue()
    results = []
    passed = []
    failed = []

    for i, job in enumerate(jobs, 1):
        company = job["company"] or ""
        jd = job["jd_text"] or ""
        gates = gate_snapshot(jd, company, prefs)
        gate_fail = first_failing_gate(gates)

        entry = {
            "index": i,
            "id": job["id"],
            "company": company,
            "title": job["title"],
            "url": job.get("url"),
            "source": job.get("source_site"),
            "db_score": job.get("score"),
            "db_pre_score": job.get("pre_score"),
            "db_summary": job.get("summary"),
            "db_category": job.get("db_category"),
            "jd_len": len(jd),
        }

        if gate_fail:
            entry["passed_now"] = False
            entry["fail_phase"] = "gate"
            entry["fail_reason"] = gate_fail
            entry["gates"] = gates
            failed.append(entry)
        else:
            fit = evaluate_job_fit(jd, work_exp, fit_rules, prefs)
            if not fit:
                entry["passed_now"] = False
                entry["fail_phase"] = "llm_error"
                entry["fail_reason"] = "evaluate_job_fit returned None"
                failed.append(entry)
            else:
                score = int(fit.get("Score", 0))
                decision = str(fit.get("Decision", "NO")).upper()
                entry["score_now"] = score
                entry["decision_now"] = decision
                entry["summary_now"] = fit.get("Summary", "")
                entry["top_fit_reasons"] = fit.get("TopFitReasons", [])
                entry["risk_flags"] = fit.get("RiskFlags", [])
                entry["gates"] = gates
                if decision != "NO" and score >= min_score:
                    entry["passed_now"] = True
                    passed.append(entry)
                else:
                    entry["passed_now"] = False
                    entry["fail_phase"] = "fit"
                    entry["fail_reason"] = fit.get("Summary", "") or f"score {score} < {min_score}"
                    failed.append(entry)

        results.append(entry)
        status = "PASS" if entry.get("passed_now") else "FAIL"
        print(f"[{i:2}/{len(jobs)}] {status} {company} — {job['title'][:50]}", file=sys.stderr)

    summary = {
        "total": len(jobs),
        "passed_now": len(passed),
        "failed_now": len(failed),
        "min_fit_score": min_score,
        "failed_by_phase": {},
    }
    for e in failed:
        phase = e.get("fail_phase", "unknown")
        summary["failed_by_phase"][phase] = summary["failed_by_phase"].get(phase, 0) + 1

    out_path = os.path.join(PROJECT_ROOT, "docs", "reports", "pm-rejection-reeval-2026-06-02.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "passed": passed, "failed": failed, "all": results}, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\n[Wrote] {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
