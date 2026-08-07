"""
CR-073 batch review report.

Consolidates every data/submissions/{company}/verification_receipt.json into one
readable Markdown summary -- reading-order guard (Epic 1) + JD literal-term coverage
(Epic 2), plus the pre-existing mechanical-verification status, so Jason can review
the whole submission set in one pass instead of opening 14 separate JSON files.

Assumes verify_submission.py has already been run against each folder (this script
only reads the receipts, it doesn't regenerate them). Re-run verify_submission.py
first if a submission's Resume.md/CoverLetter.md changed since its last receipt.

Usage:
    python scripts/cr073_batch_report.py > docs/reports/cr073-term-coverage-review.md
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_SUBMISSIONS_DIR = os.path.join(_REPO_ROOT, "data", "submissions")


def _load_receipt(company: str) -> dict | None:
    path = os.path.join(_SUBMISSIONS_DIR, company, "verification_receipt.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def main() -> None:
    companies = sorted(
        d for d in os.listdir(_SUBMISSIONS_DIR)
        if os.path.isdir(os.path.join(_SUBMISSIONS_DIR, d)) and not d.startswith(".")
    )

    rows = []
    sections = []
    skipped = []

    for company in companies:
        receipt = _load_receipt(company)
        if receipt is None:
            skipped.append(company)
            continue

        reading_order = receipt.get("reading_order", {})
        term_gaps = receipt.get("jd_literal_term_gaps") or {}
        mech_ok = receipt.get("mechanically_verified")
        missing = term_gaps.get("missing_from_resume", [])
        cover_only = term_gaps.get("cover_letter_only_mentions", [])
        ro_ok = reading_order.get("ok")
        ro_label = "OK" if ro_ok else ("n/a" if not reading_order.get("checked") else "ISSUE")

        rows.append(
            f"| {company} | {'PASS' if mech_ok else 'FAIL'} | {ro_label} | {len(missing)} | {len(cover_only)} |"
        )

        lines = [f"## {company}", ""]
        lines.append(f"- Mechanically verified: {'yes' if mech_ok else 'NO -- see receipt for lint/QA blocks'}")
        lines.append(f"- Reading order: {ro_label}" + (f" ({reading_order.get('reason')})" if not reading_order.get("checked") else ""))
        if missing:
            lines.append(f"- **Missing from resume** ({len(missing)}): {', '.join(missing)}")
        else:
            lines.append("- Missing from resume: none")
        if cover_only:
            lines.append(
                f"  - Of those, already mentioned in the cover letter only (informational, not counted as covered): {', '.join(cover_only)}"
            )
        lines.append("")
        sections.append("\n".join(lines))

    print("# CR-073 Term-Coverage Review — All Submissions")
    print()
    print(f"Generated from {len(rows)} submission(s) currently in `data/submissions/`. Read-only review --")
    print("no document content was changed to produce this report.")
    print()
    print("| Company | Mech. verified | Reading order | Missing from resume | Cover-letter-only mentions |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(r)
    print()
    if skipped:
        print(f"_Skipped (no verification_receipt.json yet -- run `verify_submission.py` first): {', '.join(skipped)}_")
        print()
    print("---")
    print()
    for s in sections:
        print(s)


if __name__ == "__main__":
    main()
