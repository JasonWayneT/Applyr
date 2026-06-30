"""
Batch submission evaluator and fixer.

Finds all submissions with Resume.md + CoverLetter.md + Original_JD.txt,
scores each against the R1-R8 / C1-C5 rubric, prints a ranked summary table,
and optionally applies one-pass fixes.

Usage:
    python scripts/eval_all.py                     # eval all complete submissions
    python scripts/eval_all.py --fix               # eval + fix NEEDS-ONE-PASS
    python scripts/eval_all.py --fix --dry-run     # preview fixes only
    python scripts/eval_all.py --only hubspot gtt  # run specific companies
    python scripts/eval_all.py --skip-existing     # skip slugs with existing eval_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import SUBMISSIONS_DIR
from eval_submission import evaluate, fix_document

VERDICT_ORDER = {"CONVERT-READY": 0, "NEEDS-ONE-PASS": 1, "NEEDS-REWORK": 2, "?": 3}
VERDICT_EMOJI = {"CONVERT-READY": "PASS", "NEEDS-ONE-PASS": "FIX ", "NEEDS-REWORK": "FAIL", "?": " ?  "}


def find_complete_slugs() -> list[str]:
    """Return slugs that have all three required files."""
    if not os.path.isdir(SUBMISSIONS_DIR):
        return []
    slugs = []
    for name in sorted(os.listdir(SUBMISSIONS_DIR)):
        folder = os.path.join(SUBMISSIONS_DIR, name)
        if not os.path.isdir(folder) or name.startswith("."):
            continue
        has_resume = os.path.isfile(os.path.join(folder, "Resume.md"))
        has_cl = os.path.isfile(os.path.join(folder, "CoverLetter.md"))
        has_jd = os.path.isfile(os.path.join(folder, "Original_JD.txt"))
        if has_resume and has_cl and has_jd:
            slugs.append(name)
    return slugs


def _verdict_sort_key(row: dict) -> tuple:
    r = VERDICT_ORDER.get(row.get("resume_verdict", "?"), 3)
    c = VERDICT_ORDER.get(row.get("cl_verdict", "?"), 3)
    r_total = -(row.get("resume_total", 0))
    c_total = -(row.get("cl_total", 0))
    return (r + c, r, c, r_total, c_total)


def print_summary(rows: list[dict]) -> None:
    print()
    print(f"{'Company':<30}  {'Resume':>8}  {'Verdict':<16}  {'CL':>6}  {'Verdict':<16}  {'Status'}")
    print("-" * 95)
    rows_sorted = sorted(rows, key=_verdict_sort_key)
    for row in rows_sorted:
        r_v = row.get("resume_verdict", "?")
        c_v = row.get("cl_verdict", "?")
        r_t = row.get("resume_total", 0)
        c_t = row.get("cl_total", 0)
        overall = "READY" if r_v == "CONVERT-READY" and c_v == "CONVERT-READY" else "BLOCKED"
        r_tag = VERDICT_EMOJI.get(r_v, " ?  ")
        c_tag = VERDICT_EMOJI.get(c_v, " ?  ")
        slug = row["slug"][:28]
        print(f"{slug:<30}  {r_t:>5}/100  [{r_tag}] {r_v:<12}  {c_t:>3}/100  [{c_tag}] {c_v:<12}  {overall}")

    total = len(rows)
    ready = sum(1 for r in rows if r.get("resume_verdict") == "CONVERT-READY"
                and r.get("cl_verdict") == "CONVERT-READY")
    needs_fix = sum(1 for r in rows if (r.get("resume_verdict") == "NEEDS-ONE-PASS"
                                         or r.get("cl_verdict") == "NEEDS-ONE-PASS")
                    and r.get("resume_verdict") != "NEEDS-REWORK"
                    and r.get("cl_verdict") != "NEEDS-REWORK")
    needs_rework = sum(1 for r in rows if r.get("resume_verdict") == "NEEDS-REWORK"
                       or r.get("cl_verdict") == "NEEDS-REWORK")
    print()
    print(f"TOTAL: {total}   READY: {ready}   NEEDS-ONE-PASS: {needs_fix}   NEEDS-REWORK: {needs_rework}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Batch eval and fix all complete submissions")
    parser.add_argument("--fix", action="store_true",
                        help="Auto-fix NEEDS-ONE-PASS documents after eval")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview fixes without writing files")
    parser.add_argument("--only", nargs="+", metavar="SLUG",
                        help="Limit to specific company slugs")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip slugs that already have eval_report.json")
    parser.add_argument("--fix-only", action="store_true",
                        help="Skip eval, load existing eval_report.json and apply fixes directly")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show blocking issues for each submission")
    args = parser.parse_args()

    if args.only:
        slugs = args.only
        missing = [s for s in slugs if not os.path.isdir(os.path.join(SUBMISSIONS_DIR, s))]
        if missing:
            print(f"[WARN] Not found: {', '.join(missing)}")
        slugs = [s for s in slugs if s not in missing]
    else:
        slugs = find_complete_slugs()

    # --fix-only: read existing reports and apply fixes, no re-eval
    if args.fix_only:
        fixable_slugs = []
        rows_from_reports = []
        for slug in slugs:
            report_path = os.path.join(SUBMISSIONS_DIR, slug, "eval_report.json")
            if not os.path.isfile(report_path):
                continue
            try:
                with open(report_path) as f:
                    result = json.load(f)
            except Exception:
                continue
            r_v = result.get("resume", {}).get("verdict", "?")
            c_v = result.get("cover_letter", {}).get("verdict", "?")
            r_t = result.get("resume", {}).get("total", 0)
            c_t = result.get("cover_letter", {}).get("total", 0)
            rows_from_reports.append({
                "slug": slug, "resume_verdict": r_v, "cl_verdict": c_v,
                "resume_total": r_t, "cl_total": c_t,
                "status": "READY" if r_v == "CONVERT-READY" and c_v == "CONVERT-READY" else "BLOCKED",
            })
            if r_v == "NEEDS-ONE-PASS" or c_v == "NEEDS-ONE-PASS":
                fixable_slugs.append((slug, result))

        print_summary(rows_from_reports)

        if not fixable_slugs:
            print("Nothing to fix.")
            return

        print(f"Applying one-pass fixes to {len(fixable_slugs)} submission(s)...\n")
        for slug, result in fixable_slugs:
            r_v = result.get("resume", {}).get("verdict", "?")
            c_v = result.get("cover_letter", {}).get("verdict", "?")
            if r_v == "NEEDS-ONE-PASS":
                fix_document(slug, "resume", result, dry_run=args.dry_run)
            if c_v == "NEEDS-ONE-PASS":
                fix_document(slug, "cover_letter", result, dry_run=args.dry_run)

        if not args.dry_run:
            print(f"\nRe-evaluating after fixes...\n")
            for slug, _ in fixable_slugs:
                evaluate(slug, verbose=args.verbose)
        return

    if args.skip_existing:
        before = len(slugs)
        slugs = [s for s in slugs
                 if not os.path.isfile(os.path.join(SUBMISSIONS_DIR, s, "eval_report.json"))]
        print(f"[skip-existing] {before - len(slugs)} already have eval_report.json, skipping.")

    if not slugs:
        print("No submissions to evaluate.")
        sys.exit(0)

    print(f"\nEvaluating {len(slugs)} submission(s)...\n")

    rows = []
    for slug in slugs:
        result = evaluate(slug, verbose=args.verbose)
        if result is None:
            continue
        meta = result.get("_meta", {})
        rows.append({
            "slug": slug,
            "resume_verdict": meta.get("resume_verdict", "?"),
            "cl_verdict": meta.get("cover_letter_verdict", "?"),
            "resume_total": meta.get("resume_total", 0),
            "cl_total": meta.get("cover_letter_total", 0),
            "status": meta.get("status", "?"),
        })

    print_summary(rows)

    if args.fix:
        fixable = [
            r for r in rows
            if r["resume_verdict"] == "NEEDS-ONE-PASS" or r["cl_verdict"] == "NEEDS-ONE-PASS"
        ]
        if not fixable:
            print("Nothing to fix — all documents are CONVERT-READY or NEEDS-REWORK.")
            return

        print(f"Applying one-pass fixes to {len(fixable)} submission(s)...\n")
        for row in fixable:
            slug = row["slug"]
            report_path = os.path.join(SUBMISSIONS_DIR, slug, "eval_report.json")
            try:
                with open(report_path) as f:
                    result = json.load(f)
            except Exception:
                print(f"  [fix] {slug}: cannot read eval_report.json, skipping")
                continue
            if row["resume_verdict"] == "NEEDS-ONE-PASS":
                fix_document(slug, "resume", result, dry_run=args.dry_run)
            if row["cl_verdict"] == "NEEDS-ONE-PASS":
                fix_document(slug, "cover_letter", result, dry_run=args.dry_run)

        if not args.dry_run:
            print(f"\nRe-evaluating fixed submissions...\n")
            fixed_rows = []
            for row in fixable:
                re_result = evaluate(row["slug"], verbose=args.verbose)
                if re_result is None:
                    continue
                meta = re_result.get("_meta", {})
                fixed_rows.append({
                    "slug": row["slug"],
                    "resume_verdict": meta.get("resume_verdict", "?"),
                    "cl_verdict": meta.get("cover_letter_verdict", "?"),
                    "resume_total": meta.get("resume_total", 0),
                    "cl_total": meta.get("cover_letter_total", 0),
                    "status": meta.get("status", "?"),
                })
            if fixed_rows:
                print("\nPost-fix results:")
                print_summary(fixed_rows)


if __name__ == "__main__":
    main()
