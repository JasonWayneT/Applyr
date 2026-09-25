#!/usr/bin/env python3
"""Batch Stage 0 test runner for the improvement plan validation.

Runs build_stage0_fit_gate against a diverse sample of archived submissions
and collects results: tier, decision, fit_score, timing, errors, and any
anomalies. Outputs a JSON report for analysis.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Force cascade on (the default, but explicit for this test)
os.environ.setdefault("STAGE0_EVIDENCE_CASCADE", "1")

from build_stage0_fit_gate import build_stage0_fit_gate, Stage0NeedsInput
from stage0_confirmations import answer_confirmation, answer_hard_gate_review

_REPO = Path(__file__).resolve().parents[1]
_ARCHIVE = _REPO / "data" / "archive" / "submissions"

# Diverse sample: known SKIP cases, known PASS cases, large JDs,
# many-responsibility JDs, various domains.
SAMPLE = [
    "kintsugi",           # known SKIP (0-to-1 exclusion zone)
    "bazaarvoice",        # known PASS, 8+ responsibilities
    "harbor_compliance",  # exclusion zone in responsibilities
    "practice_tek",       # large JD, many responsibilities (practicetek)
    "limble",             # known test case
    "pinterest",          # large JD
    "metlife",            # enterprise
    "workday",            # enterprise
    "docusign",           # SaaS
    "spotify",            # large company
    "coinbase_-_product_manager",  # fintech
    "dropbox",            # SaaS
    "hubspot",            # SaaS
    "pagerduty",          # SaaS
    "zoominfo",           # SaaS
    "veeva",              # healthcare
    "clover_health",      # healthcare
    "onetrust",           # privacy
    "digicert",           # security
    "expel",              # security
    "camunda",            # process automation
    "pointclickcare",     # healthcare
    "thermo_fisher_scientific",  # enterprise
    "accertify",          # identity verification
    "sony_interactive_entertainment",  # gaming
    "reddit",             # social media
    "yext",               # SEO
    "leantaas",           # healthcare
    "hirevue",            # HR tech
    "fortive",            # industrial
    "stord",              # logistics
]

def run_batch():
    results = []
    for slug in SAMPLE:
        folder = _ARCHIVE / slug
        if not folder.exists():
            # Try alternate naming
            matches = [d for d in _ARCHIVE.iterdir() if d.is_dir() and slug.replace("-", "_") in d.name.lower() or slug in d.name.lower()]
            if matches:
                folder = matches[0]
            else:
                print(f"  SKIP (not found): {slug}")
                continue

        jd_file = folder / "Original_JD.txt"
        if not jd_file.exists():
            print(f"  SKIP (no JD): {slug}")
            continue

        print(f"  Running: {folder.name}...", end=" ", flush=True)
        t0 = time.time()
        entry = {"slug": folder.name, "start_time": t0}
        review_db = str(_REPO / "scripts" / "batch_test_review.sqlite")
        # Clean up any stale review DB from a previous run
        if os.path.exists(review_db):
            os.unlink(review_db)
        # Set the env var so all code paths use this DB
        os.environ["APPLYR_STAGE0_REVIEW_DB"] = review_db

        hard_gate_count = 0
        try:
            for attempt in range(5):
                try:
                    result = build_stage0_fit_gate(
                        folder,
                        db_gate_result={"action": "clear"},
                        prefs={"blocked_companies": []},
                        ignore_skip_ledger=True,
                    )
                    break
                except Stage0NeedsInput as exc:
                    hard_gate_count += len(exc.pending)
                    for pending in exc.pending:
                        # Dispatch on question_type: hard gates take
                        # KEEP_ELIGIBLE, skill confirmations take "yes".
                        if pending.get("question_type") == "hard_gate_review":
                            answer_hard_gate_review(
                                db_path=review_db,
                                review_key=pending["review_key"],
                                answer="KEEP_ELIGIBLE",
                            )
                        else:
                            answer_confirmation(
                                db_path=review_db,
                                review_key=pending["review_key"],
                                answer="CONFIRMED_USE",
                            )
                    continue
            elapsed = time.time() - t0
            entry.update({
                "status": "ok",
                "decision": result.get("decision"),
                "tier": result.get("tier"),
                "fit_score": result.get("fit_score"),
                "stage_signal": result.get("stage_signal"),
                "required_count": len(result.get("required", [])),
                "preferred_count": len(result.get("preferred", [])),
                "responsibilities_count": len(result.get("responsibilities", [])),
                "flagged_gaps_count": len(result.get("flagged_gaps", [])),
                "exclusion_zone_check": result.get("exclusion_zone_check"),
                "skip_reason": result.get("skip_reason"),
                "hard_gate_reviews": hard_gate_count,
                "elapsed_seconds": round(elapsed, 1),
            })
            print(f"{result.get('decision')} / {result.get('tier')} / score={result.get('fit_score')} / {elapsed:.1f}s (reviews={hard_gate_count})")
        except Exception as exc:
            elapsed = time.time() - t0
            entry.update({
                "status": "error",
                "error": str(exc)[:500],
                "elapsed_seconds": round(elapsed, 1),
            })
            print(f"ERROR: {exc!s:.100} ({elapsed:.1f}s)")
        results.append(entry)

    return results


if __name__ == "__main__":
    print("=== Stage 0 Batch Test ===")
    print(f"Archive: {_ARCHIVE}")
    print(f"Sample size: {len(SAMPLE)}")
    print()

    results = run_batch()

    print()
    print("=== Summary ===")
    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]
    passes = [r for r in ok if r.get("decision") == "PASS"]
    skips = [r for r in ok if r.get("decision") == "SKIP"]

    print(f"Total: {len(results)}")
    print(f"OK: {len(ok)} (PASS: {len(passes)}, SKIP: {len(skips)})")
    print(f"Errors: {len(errors)}")
    print(f"Avg time: {sum(r.get('elapsed_seconds', 0) for r in ok) / max(len(ok), 1):.1f}s")
    print(f"Max time: {max((r.get('elapsed_seconds', 0) for r in ok), default=0):.1f}s")

    if errors:
        print("\n=== Errors ===")
        for r in errors:
            print(f"  {r['slug']}: {r['error'][:200]}")

    print("\n=== SKIP cases ===")
    for r in skips:
        print(f"  {r['slug']}: {r.get('skip_reason', '?')[:100]}")

    print("\n=== PASS cases ===")
    for r in passes:
        print(f"  {r['slug']}: tier={r.get('tier')} score={r.get('fit_score')} req={r.get('required_count')} resp={r.get('responsibilities_count')}")

    # Save full report
    report_path = _REPO / "scripts" / "batch_stage0_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull report saved to: {report_path}")
