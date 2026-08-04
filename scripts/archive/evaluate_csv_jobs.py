# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Evaluate jobs from a CSV (Company, Position, Job Description, URL) through Applyr gates + fit."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from utils import (  # noqa: E402
    FIT_ENGINE_FILE,
    WORK_EXP_FILE,
    WORK_EXP_SUMMARY_FILE,
    get_min_fit_score,
    init_pipeline_prefs,
    load_candidate_preferences,
    load_file,
)
from batch_pipeline import evaluate_job_fit, passes_jd_keyword_gate  # noqa: E402
from seniority_gate import check_years_gate, passes_title_gate  # noqa: E402
from industry_gate import check_industry_gate  # noqa: E402
from anchor_gate import check_anchor_gate  # noqa: E402
from solo_pm_gate import check_solo_pm_gate  # noqa: E402
from utils import passes_keyword_gate  # noqa: E402
from zero_shot_classifier import classify_onsite, resolve_location_verdict  # noqa: E402


def load_csv_rows(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        for row in csv.DictReader(f):
            company = (row.get("Company") or "").strip()
            position = (row.get("Position") or "").strip()
            url = (row.get("URL") or "").strip()
            jd = (row.get("Job Description") or "").strip()
            if not company or not jd:
                continue
            rows.append(
                {
                    "company": company,
                    "position": position,
                    "url": url,
                    "jd": jd,
                }
            )
    return rows


def first_gate_failure(jd: str, company: str, prefs: dict) -> str | None:
    ok, reason = passes_title_gate(jd, prefs)
    if not ok:
        return f"title: {reason}"
    ok, reason = check_years_gate(jd, prefs)
    if not ok:
        return f"years: {reason}"
    ok, reason = check_solo_pm_gate(jd, prefs)
    if not ok:
        return f"solo_pm: {reason}"
    ok, reason = check_industry_gate(company, jd, prefs=prefs)
    if not ok:
        return f"industry: {reason}"
    ok, reason = passes_keyword_gate(jd, prefs)
    if not ok:
        return f"keywords: {reason}"
    ok, reason = check_anchor_gate(jd, prefs)
    if not ok:
        return f"anchors: {reason}"
    return None


_REMOTE_PREFIX = "Location: Remote, United States\n\n"


def evaluate_row(
    row: dict,
    prefs: dict,
    fit_rules: str,
    work_exp: str,
    min_score: int,
    *,
    assume_remote: bool = False,
) -> dict:
    jd = row["jd"]
    if assume_remote:
        jd = _REMOTE_PREFIX + jd
    company = row["company"]
    out: dict = {
        "company": company,
        "position": row["position"],
        "url": row["url"],
        "verdict": "REJECT",
        "score": None,
        "decision": None,
        "summary": "",
        "gate": "",
        "risk_flags": [],
        "top_fit_reasons": [],
    }

    gate_fail = first_gate_failure(jd, company, prefs)
    if gate_fail:
        out["gate"] = gate_fail
        out["summary"] = gate_fail
        return out

    if not passes_jd_keyword_gate(jd, prefs, company_name=company):
        out["gate"] = "zero_token_composite"
        out["summary"] = "Failed composite zero-token gate"
        return out

    is_onsite, onsite_reason = classify_onsite(jd)
    if is_onsite:
        out["gate"] = "onsite"
        out["summary"] = onsite_reason
        return out

    loc_verdict, loc_detail = resolve_location_verdict(jd)
    out["location"] = loc_verdict

    result = evaluate_job_fit(jd, work_exp, fit_rules, prefs)
    if not result:
        out["gate"] = "llm_error"
        out["summary"] = "Fit evaluation returned no result"
        return out

    score = int(result.get("Score", 0))
    decision = str(result.get("Decision", "NO")).upper()
    out["score"] = score
    out["decision"] = decision
    out["summary"] = str(result.get("Summary", ""))[:500]
    out["risk_flags"] = result.get("RiskFlags") or []
    out["top_fit_reasons"] = result.get("TopFitReasons") or []

    if decision != "NO" and score >= min_score:
        out["verdict"] = "PASS"
        out["gate"] = "fit_pass"
    else:
        out["gate"] = "fit_below_threshold"
        if not out["summary"]:
            out["summary"] = f"Score {score} below threshold {min_score}"
    return out


def write_report(results: list[dict], csv_path: str, out_path: str, min_score: int) -> None:
    passed = [r for r in results if r["verdict"] == "PASS"]
    rejected = [r for r in results if r["verdict"] != "PASS"]
    passed.sort(key=lambda x: (-(x["score"] or 0), x["company"]))
    rejected.sort(key=lambda x: (x["company"].lower()))

    lines = [
        "# CSV Job Evaluation Report",
        "",
        f"**Source:** `{csv_path}`",
        f"**Evaluated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Threshold:** score >= {min_score}",
        f"**Total:** {len(results)} | **Pass:** {len(passed)} | **Reject:** {len(rejected)}",
        "",
        "## Pass (apply-worthy)",
        "",
    ]
    if not passed:
        lines.append("_None met threshold._")
    else:
        lines.append("| Score | Company | Role | Summary |")
        lines.append("|------:|---------|------|---------|")
        for r in passed:
            pos = (r["position"] or "")[:60].replace("|", "/")
            summ = (r["summary"] or "")[:120].replace("|", "/")
            lines.append(f"| {r['score']} | {r['company']} | {pos} | {summ} |")

    lines.extend(["", "## Reject — summary", ""])
    from collections import Counter

    gate_counts = Counter(r["gate"] for r in rejected)
    for gate, n in gate_counts.most_common():
        lines.append(f"- `{gate}`: {n}")

    lines.extend(["", "## Reject — detail", ""])
    for r in rejected:
        lines.append(f"### {r['company']}")
        lines.append(f"- **Role:** {r['position'][:100]}")
        if r.get("score") is not None:
            lines.append(f"- **Score:** {r['score']}")
        lines.append(f"- **Gate:** `{r['gate']}`")
        lines.append(f"- **Reason:** {r['summary'][:300]}")
        if r.get("url"):
            lines.append(f"- **URL:** {r['url'][:120]}")
        lines.append("")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _reclaim_fit_vram() -> None:
    """Stop fit models so the next job sees free VRAM above the primary threshold."""
    import subprocess

    for model in ("llama3.1:8b-instruct-q5_K_M", "phi3.5:3.8b-mini-instruct-q8_0"):
        try:
            subprocess.run(
                ["ollama", "stop", model],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception:
            pass


def main() -> int:
    from applyr_python import assert_applyr_host
    try:
        assert_applyr_host()
    except Exception as exc:
        print(f"CRITICAL: {exc}", file=sys.stderr)
        return 1

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=r"C:\Users\Jason\Downloads\Job Evaluation 1 - Sheet1.csv",
    )
    parser.add_argument(
        "--json",
        default=os.path.join(PROJECT_ROOT, "docs", "reports", "csv-job-evaluation-1-results.json"),
    )
    parser.add_argument(
        "--md",
        default=os.path.join(PROJECT_ROOT, "docs", "reports", "csv-job-evaluation-1-report.md"),
    )
    parser.add_argument(
        "--assume-remote",
        action="store_true",
        help="Prepend Remote, United States to each JD (skip stealth on-site rejection)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"CSV not found: {args.csv_path}", file=sys.stderr)
        return 1

    init_pipeline_prefs()
    prefs = load_candidate_preferences()
    min_score = get_min_fit_score()
    fit_rules = load_file(FIT_ENGINE_FILE)
    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    rows = load_csv_rows(args.csv_path)

    print(f"Evaluating {len(rows)} jobs from {args.csv_path} (min_score={min_score})...")
    results = []
    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {row['company']}...", flush=True)
        results.append(
            evaluate_row(
                row,
                prefs,
                fit_rules,
                work_exp,
                min_score,
                assume_remote=args.assume_remote,
            )
        )
        # Reclaim VRAM so the next job can use the primary model (llama), not phi fallback.
        if results[-1].get("score") is not None:
            _reclaim_fit_vram()

    _reclaim_fit_vram()
    write_report(results, args.csv_path, args.md, min_score)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    print(f"\nDone: {passed}/{len(results)} pass. Report: {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
