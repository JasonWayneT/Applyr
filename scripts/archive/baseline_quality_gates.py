#!/usr/bin/env python3
# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""
Phase 0/1 quality gate baseline — reports pass/fail without changing pipeline behavior.

Usage:
  python scripts/baseline_quality_gates.py
  python scripts/baseline_quality_gates.py --submissions submissions/acxiom
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from approved_metrics import find_unapproved_metrics, metric_integrity_message
from catalog_validator import load_anti_claim_hints, validate_catalog
from cover_letter_audit import audit_cover_letter
from cover_letter_plan import CoverLetterPlan
from claim_catalog import load_catalog
from pipeline_env import strict_anti_claims, strict_cover_audit, strict_metrics
from utils import PROJECT_ROOT, SUBMISSIONS_DIR
from verification_chain import check_anti_claims

SUBMISSIONS = os.path.join(PROJECT_ROOT, "data", "submissions")


def _load_text(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def check_submission(folder: str) -> dict:
    name = os.path.basename(folder.rstrip("/\\"))
    report = {"folder": name, "checks": {}, "ok": True}

    resume = _load_text(os.path.join(folder, "Resume.md"))
    cover = _load_text(os.path.join(folder, "CoverLetter.md"))
    jd = _load_text(os.path.join(folder, "Original_JD.txt"))
    plan_path = os.path.join(folder, "cover_letter_plan.json")

    # Metrics
    bad = find_unapproved_metrics(resume + "\n" + cover)
    report["checks"]["metrics"] = {"ok": not bad, "unapproved": bad}
    if bad:
        report["ok"] = False

    # Cover audit
    cover_audit_ok = True
    cover_grade = "n/a"
    if cover and os.path.isfile(plan_path):
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan_data = json.load(f)
            plan = CoverLetterPlan.from_dict(plan_data)
            catalog = load_catalog()
            corpus = "\n".join(catalog.raw_truth_lines.values())
            audit = audit_cover_letter(cover, plan, jd, corpus)
            cover_grade = audit.grade
            cover_audit_ok = audit.passed
            report["checks"]["cover_audit"] = {
                "ok": cover_audit_ok,
                "grade": audit.grade,
                "score": audit.score,
                "issues": audit.issues[:5],
            }
            if strict_cover_audit() and not cover_audit_ok:
                report["ok"] = False
        except Exception as exc:
            report["checks"]["cover_audit"] = {"ok": False, "error": str(exc)}
            report["ok"] = False
    else:
        report["checks"]["cover_audit"] = {"ok": True, "skipped": True}

    # Anti-claims (dry-run detection)
    hints = load_anti_claim_hints()
    anti_hit = check_anti_claims(resume + "\n" + cover, hints) if hints else None
    report["checks"]["anti_claims"] = {
        "ok": anti_hit is None,
        "hint_count": len(hints),
        "violation": anti_hit,
    }
    if hints and anti_hit and strict_anti_claims():
        report["ok"] = False

    # Manifest
    manifest_path = os.path.join(folder, "draft_manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        report["checks"]["manifest"] = {
            "verification_passed": manifest.get("verification_passed"),
            "claim_strength_count": len(manifest.get("claim_strength") or {}),
        }

    if strict_metrics() and bad:
        report["ok"] = False

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline quality gate report")
    parser.add_argument("--submissions", default=SUBMISSIONS, help="Submissions root or single folder")
    args = parser.parse_args()

    catalog_result = validate_catalog()
    print("=== CATALOG VALIDATION ===")
    print("OK" if catalog_result.ok else "FAIL")
    for err in catalog_result.errors[:15]:
        print(f"  - {err}")

    print("\n=== STRICT FLAGS ===")
    print(f"  STRICT_COVER_AUDIT={strict_cover_audit()}")
    print(f"  STRICT_METRICS={strict_metrics()}")
    print(f"  STRICT_ANTI_CLAIMS={strict_anti_claims()}")

    targets: list[str] = []
    if os.path.isdir(args.submissions):
        if os.path.isfile(os.path.join(args.submissions, "Resume.md")):
            targets = [args.submissions]
        else:
            targets = [
                os.path.join(args.submissions, d)
                for d in sorted(os.listdir(args.submissions))
                if os.path.isdir(os.path.join(args.submissions, d))
            ]

    print(f"\n=== SUBMISSIONS ({len(targets)}) ===")
    fail = 0
    for folder in targets:
        rep = check_submission(folder)
        status = "OK" if rep["ok"] else "ISSUES"
        if not rep["ok"]:
            fail += 1
        metrics = rep["checks"].get("metrics", {})
        ca = rep["checks"].get("cover_audit", {})
        print(
            f"  [{status}] {rep['folder']:28}  metrics={len(metrics.get('unapproved') or [])} unapproved  "
            f"cover={ca.get('grade', 'n/a')}"
        )
        for u in (metrics.get("unapproved") or [])[:3]:
            print(f"         metric: {u}")

    if not catalog_result.ok:
        fail += 1
    print(f"\nSummary: {len(targets) - fail}/{len(targets)} submission folders clean; catalog={'OK' if catalog_result.ok else 'FAIL'}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
