# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""
Fleet document QA ranker (FR-246 / CR-050).

Scores every submission folder against conversion critique, advisory signals,
CW-016 overlap, and rubric — reports balanced exit bar status.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List

from utils import SUBMISSIONS_DIR, load_file, init_pipeline_prefs

init_pipeline_prefs()

BALANCED_CRITIQUE_PASS = True
BALANCED_CW001_MAX = 5
BALANCED_CW016_MAX = 0
BALANCED_RUBRIC_MIN = 65.0


def _load_jd(folder: str) -> str:
    jd = load_file(os.path.join(folder, "Original_JD.txt")) or ""
    if jd.startswith("URL:"):
        lines = jd.splitlines()
        jd = "\n".join(lines[1:]) if len(lines) > 1 else jd
    return jd


def _count_codes(warnings: List[str], prefix: str) -> int:
    return sum(1 for w in warnings if w.startswith(f"[{prefix}]"))


def scan_folder(name: str, root: str) -> Dict[str, Any]:
    folder = os.path.join(root, name)
    resume_path = os.path.join(folder, "Resume.md")
    row: Dict[str, Any] = {
        "folder": name,
        "has_resume": os.path.isfile(resume_path),
        "pass": None,
        "blocking_codes": [],
        "cw001": 0,
        "cw003": 0,
        "cw016": 0,
        "rubric_overall": None,
        "rubric_summary": None,
        "rubric_exp": None,
        "rank_score": 9999,
    }
    if not row["has_resume"]:
        row["rank_score"] = 10000
        return row

    md = load_file(resume_path) or ""
    jd = _load_jd(folder)

    from resume_conversion_eval import evaluate_resume_conversion, check_summary_bullet_overlap
    from quality_checker import check_conversion_signals
    from resume_rubric import score_resume
    from critique_retry import extract_failing_codes

    critique = evaluate_resume_conversion(md, pdf_path=None, jd_text=jd)
    row["pass"] = critique.get("pass")
    row["blocking_codes"] = extract_failing_codes(critique.get("issues") or [])

    cw016_issues = check_summary_bullet_overlap(md)
    row["cw016"] = len(cw016_issues)

    signals = check_conversion_signals(md, {}, jd_text=jd)
    row["cw001"] = _count_codes(signals, "CW-001")
    row["cw003"] = _count_codes(signals, "CW-003")

    try:
        rubric = score_resume(md, jd)
        row["rubric_overall"] = rubric.get("overall")
        row["rubric_summary"] = rubric.get("summary", {}).get("score")
        row["rubric_exp"] = rubric.get("experience", {}).get("score")
    except Exception as exc:
        row["rubric_error"] = str(exc)

    fail_boost = 0 if row["pass"] else 1000
    row["rank_score"] = (
        fail_boost
        + row["cw016"] * 100
        + len(row["blocking_codes"]) * 50
        + row["cw001"] * 5
        + row["cw003"] * 3
        + max(0, BALANCED_RUBRIC_MIN - (row["rubric_overall"] or 0))
    )
    return row


def balanced_bar_status(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    evaluated = [r for r in rows if r.get("has_resume")]
    pass_count = sum(1 for r in evaluated if r.get("pass"))
    cw001_folders = sum(1 for r in evaluated if r.get("cw001", 0) > 0)
    cw016_total = sum(r.get("cw016", 0) for r in evaluated)
    rubric_fail = [
        r["folder"]
        for r in evaluated
        if r.get("rubric_overall") is not None and r["rubric_overall"] < BALANCED_RUBRIC_MIN
    ]
    return {
        "folders": len(evaluated),
        "critique_pass": pass_count,
        "critique_pass_rate": pass_count / max(1, len(evaluated)),
        "cw001_folders": cw001_folders,
        "cw016_total": cw016_total,
        "rubric_below_min": rubric_fail,
        "met": (
            pass_count == len(evaluated)
            and cw001_folders <= BALANCED_CW001_MAX
            and cw016_total <= BALANCED_CW016_MAX
            and not rubric_fail
        ),
    }


def run_scan(root: str = SUBMISSIONS_DIR, report_path: str = "") -> int:
    if not report_path:
        report_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reports",
            "fleet_qa_latest.json",
        )

    folders = sorted(
        f for f in os.listdir(root) if os.path.isdir(os.path.join(root, f))
    )
    rows = [scan_folder(name, root) for name in folders]
    rows.sort(key=lambda r: (-r.get("rank_score", 0), r["folder"]))

    status = balanced_bar_status(rows)
    payload = {"balanced_bar": status, "rows": rows}

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print("=" * 60)
    print("  FLEET DOCUMENT QA (CR-050)")
    print("=" * 60)
    print(f"Folders:           {status['folders']}")
    print(f"Critique pass:     {status['critique_pass']}/{status['folders']}")
    print(f"CW-001 folders:    {status['cw001_folders']} (max {BALANCED_CW001_MAX})")
    print(f"CW-016 total:      {status['cw016_total']} (max {BALANCED_CW016_MAX})")
    print(f"Rubric < {BALANCED_RUBRIC_MIN}:    {len(status['rubric_below_min'])}")
    print(f"Balanced bar met:  {'YES' if status['met'] else 'NO'}")
    print()
    print("Worst 5:")
    for r in rows[:5]:
        codes = ",".join(r.get("blocking_codes") or []) or "-"
        print(
            f"  {r['folder']}: pass={r.get('pass')} codes={codes} "
            f"cw001={r.get('cw001')} cw016={r.get('cw016')} "
            f"rubric={r.get('rubric_overall')}"
        )
    print(f"\nReport: {report_path}")
    return 0 if status["met"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Fleet document QA ranker")
    parser.add_argument("--root", default=SUBMISSIONS_DIR)
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    return run_scan(args.root, args.report)


if __name__ == "__main__":
    sys.exit(main())
