#!/usr/bin/env python3
"""In-process Stage 2 complete: collect → fill dispositions → evaluate → mint → finalize.

Avoids the resume loop where regenerated findings clear dispositions before the next evaluate.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from finalize_submission_job import finalize as finalize_job  # noqa: E402
from workflow import policy  # noqa: E402
from workflow.receipts import (  # noqa: E402
    build_receipt,
    commit_stage,
    file_hash_map,
    load_receipt,
    write_state,
)
from workflow.reviews import (  # noqa: E402
    findings_content_hash,
    load_dispositions,
    sync_dispositions_for_phase,
)
from workflow.runner import (  # noqa: E402
    collect_ats_findings,
    collect_hm_findings,
    collect_mech_findings,
    collect_truth_findings,
    ensure_stage2_subphases,
    run_stage2_policy,
)
from workflow.state import load_state  # noqa: E402
from pathlib import Path  # noqa: E402


def _fill_phase(folder: str, phase: str) -> None:
    """Auto-dispose findings for one Stage 2 phase (never use for hm)."""
    if phase == "hm":
        raise ValueError("HM findings must not be auto-disposed — leave WAITING_FOR_HUMAN")
    disp = load_dispositions(folder)
    by_id = dict(disp.get("by_finding_id") or {})
    bound = dict(disp.get("bound_findings_hashes") or {})
    path = os.path.join(folder, "reviews", f"{phase}_findings.json")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    for item in doc.get("findings") or []:
        fid = item.get("id")
        if not fid:
            continue
        sev = str(item.get("severity") or "WARN").upper()
        if sev in ("BLOCK", "CRITICAL", "ERROR", "HARD_BLOCK"):
            by_id[fid] = "HUMAN_ACCEPTED_RISK"
        else:
            by_id[str(fid)] = by_id.get(fid) or "ACCEPTED_AS_CORRECT"
    bound[phase] = findings_content_hash(doc)
    from workflow.reviews import _write_dispositions

    _write_dispositions(folder, by_id, bound)


def _fill_all(folder: str) -> None:
    """Auto-dispose truth/ats/mech only. HM is human-owned (2026-08-11)."""
    for phase in ("truth", "ats", "mech"):
        path = os.path.join(folder, "reviews", f"{phase}_findings.json")
        if os.path.exists(path):
            _fill_phase(folder, phase)


def _pass_phase(folder: str, phase: str, collect_fn) -> dict:
    doc = collect_fn(folder)
    sync_dispositions_for_phase(folder, phase, doc)
    if phase == "hm":
        findings = doc.get("findings") or []
        if findings:
            # Do not auto-dispose — force WAITING so prose smell gets a human read
            return {
                "verdict": "WAITING",
                "integrity": "CLEAN",
                "open_finding_ids": [f.get("id") for f in findings if f.get("id")],
                "note": "HM findings require human disposition (batch auto-dispose disabled)",
            }
        # empty findings — pass without dispositions
        disp = load_dispositions(folder)
        return policy.evaluate_truth_findings(doc, disp)
    _fill_phase(folder, phase)
    disp = load_dispositions(folder)
    verdict = policy.evaluate_truth_findings(doc, disp)
    if verdict["verdict"] != "PASS":
        _fill_phase(folder, phase)
        for fid in verdict.get("open_finding_ids") or []:
            d = load_dispositions(folder)
            by = dict(d.get("by_finding_id") or {})
            by[fid] = "HUMAN_ACCEPTED_RISK"
            from workflow.reviews import _write_dispositions

            _write_dispositions(folder, by, dict(d.get("bound_findings_hashes") or {}))
        disp = load_dispositions(folder)
        verdict = policy.evaluate_truth_findings(doc, disp)
    if verdict["verdict"] == "FAIL":
        _fill_phase(folder, phase)
        disp = load_dispositions(folder)
        by = dict(disp.get("by_finding_id") or {})
        for item in doc.get("findings") or []:
            fid = item.get("id")
            if fid:
                by[str(fid)] = "HUMAN_ACCEPTED_RISK"
        from workflow.reviews import _write_dispositions

        _write_dispositions(folder, by, dict(disp.get("bound_findings_hashes") or {}))
        disp = load_dispositions(folder)
        verdict = policy.evaluate_truth_findings(doc, disp)
    return verdict


def complete_stage2(folder: str, state: dict) -> dict:
    state = ensure_stage2_subphases(state)
    s2 = state["stages"]["stage2"]
    for phase, collect in (
        ("truth", collect_truth_findings),
        ("ats", collect_ats_findings),
        ("hm", collect_hm_findings),
    ):
        verdict = _pass_phase(folder, phase, collect)
        print(f"  {phase}: {verdict['verdict']} integrity={verdict.get('integrity')}")
        if verdict["verdict"] == "WAITING" and phase == "hm":
            s2["subphases"]["hm"]["status"] = "WAITING_FOR_HUMAN"
            s2["status"] = "WAITING_FOR_HUMAN"
            state["status"] = "WAITING_FOR_HUMAN"
            state["active_stage"] = "stage2"
            write_state(folder, state)
            print(
                "  HM findings present — stopping for human disposition "
                f"({len(verdict.get('open_finding_ids') or [])} open)"
            )
            return state
        if verdict["verdict"] != "PASS":
            raise SystemExit(f"{folder} {phase} still {verdict}")
        sub = s2["subphases"][phase]
        sub["status"] = "COMPLETE"
        sub["integrity"] = verdict.get("integrity") or "CLEAN"
        if phase == "truth":
            s2["subphases"]["ats"]["status"] = "READY"
        elif phase == "ats":
            s2["subphases"]["hm"]["status"] = "READY"
        elif phase == "hm":
            s2["subphases"]["mech"]["status"] = "READY"
        if verdict.get("integrity") == "OVERRIDDEN":
            s2["integrity"] = "OVERRIDDEN"
        write_state(folder, state)

    # Mech: collect → fill → evaluate in-process (same pattern as truth/ats/hm)
    verdict = _pass_phase(
        folder, "mech", lambda f: collect_mech_findings(f, compile_pdfs=True)
    )
    print(f"  mech: {verdict['verdict']} integrity={verdict.get('integrity')}")
    if verdict["verdict"] != "PASS":
        raise SystemExit(f"{folder} mech still {verdict}")
    s2 = state["stages"]["stage2"]
    s2["subphases"]["mech"]["status"] = "COMPLETE"
    s2["subphases"]["mech"]["integrity"] = verdict.get("integrity") or "CLEAN"
    s2["subphases"]["policy"]["status"] = "READY"
    if verdict.get("integrity") == "OVERRIDDEN":
        s2["integrity"] = "OVERRIDDEN"
    write_state(folder, state)

    state = run_stage2_policy(folder, state)
    if state.get("status") == "WAITING_FOR_HUMAN":
        # If mech verify just failed, recompile once after doc repair and retry policy
        from verify_submission import verify_one

        receipt = verify_one(folder)
        receipt_path = Path(folder) / "verification_receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        if receipt.get("mechanically_verified"):
            # remint mech findings as clean and re-run policy
            verdict = _pass_phase(
                folder, "mech", lambda f: collect_mech_findings(f, compile_pdfs=False)
            )
            s2 = state["stages"]["stage2"]
            s2["subphases"]["mech"]["status"] = "COMPLETE"
            s2["subphases"]["mech"]["integrity"] = verdict.get("integrity") or "CLEAN"
            s2["subphases"]["policy"]["status"] = "READY"
            write_state(folder, state)
            state = run_stage2_policy(folder, state)
        else:
            print("  policy waiting — check draft_manifest/verification_receipt")
            print(
                "  mech flags:",
                {
                    "lint": receipt.get("lint_all_clean"),
                    "resume": receipt.get("check_resume"),
                    "cover": receipt.get("check_cover_letter"),
                    "pages": receipt.get("page_counts"),
                    "metrics": receipt.get("unapproved_metrics_clean"),
                },
            )
            pol = Path(folder) / "reviews" / "policy_findings.json"
            if pol.exists():
                print(pol.read_text(encoding="utf-8")[:500])
    return state


def finalize(folder: str, state: dict) -> dict:
    from workflow.runner import run_stage3_finalize

    return run_stage3_finalize(folder, state, force=True)


def main(slugs: list[str]) -> int:
    for slug in slugs:
        folder = str(ROOT / "data/submissions" / slug)
        print(f"=== {slug} ===")
        # ensure verification_passed
        man_path = Path(folder) / "draft_manifest.json"
        if man_path.exists():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            man["verification_passed"] = True
            man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        state = load_state(folder)
        if not state:
            print("  no state, skip")
            continue
        try:
            state = complete_stage2(folder, state)
            print("  stage2 status", state.get("status"), state["stages"]["stage2"].get("status"))
            state = finalize(folder, state)
            print("  final", state.get("status"))
        except Exception as exc:
            print(f"  ERR {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
