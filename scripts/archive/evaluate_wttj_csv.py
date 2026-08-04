#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""Evaluate Welcome to the Jungle single-column CSV exports."""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from applyr_python import assert_applyr_host  # noqa: E402
from evaluate_csv_jobs import evaluate_row, write_report  # noqa: E402
from utils import (  # noqa: E402
    FIT_ENGINE_FILE,
    WORK_EXP_FILE,
    WORK_EXP_SUMMARY_FILE,
    get_min_fit_score,
    init_pipeline_prefs,
    load_candidate_preferences,
    load_file,
)


def load_wttj_rows(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        for raw in csv.reader(f):
            if not raw or not (raw[0] or "").strip():
                continue
            jd = raw[0].strip()
            first_line = jd.split("\n", 1)[0].strip()
            follow = re.search(r"Follow\s+(\S+)", jd)
            company = follow.group(1) if follow else ""
            if not company and "," in first_line:
                company = first_line.rsplit(",", 1)[-1].strip()
            position = first_line
            rows.append(
                {
                    "company": company or "Unknown",
                    "position": position,
                    "url": "",
                    "jd": jd,
                }
            )
    return rows


def main() -> int:
    assert_applyr_host()
    csv_path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Jason\Downloads\WTTJ - Sheet1.csv"
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    stem = os.path.splitext(os.path.basename(csv_path))[0].lower().replace(" ", "-")
    json_path = os.path.join(PROJECT_ROOT, "docs", "reports", f"{stem}-results.json")
    md_path = os.path.join(PROJECT_ROOT, "docs", "reports", f"{stem}-report.md")

    init_pipeline_prefs()
    prefs = load_candidate_preferences()
    min_score = get_min_fit_score()
    fit_rules = load_file(FIT_ENGINE_FILE)
    work_exp = load_file(WORK_EXP_SUMMARY_FILE) or load_file(WORK_EXP_FILE)
    rows = load_wttj_rows(csv_path)

    print(f"Evaluating {len(rows)} jobs from {csv_path} (min_score={min_score})...")
    results = []
    for i, row in enumerate(rows, 1):
        print(f"  [{i}/{len(rows)}] {row['company']}...", flush=True)
        results.append(evaluate_row(row, prefs, fit_rules, work_exp, min_score))

    write_report(results, csv_path, md_path, min_score)
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    passed = [r for r in results if r["verdict"] == "PASS"]
    print(f"\nDone: {len(passed)}/{len(results)} pass.")
    print(f"Report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
