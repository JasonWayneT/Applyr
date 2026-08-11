"""
Independent completion check for a submission folder -- computed from the filesystem only.

Why this exists (2026-08-06): every "is this submission done?" answer in this process has, up
to now, come from an agent's own report at the end of a drafting session. That's the specific
pattern that has failed before, on more than one harness: a plausible-looking summary asserting
completion when a required step was actually skipped or failed (byte-identical rubric scores,
a resume lint check that silently never ran). The fix isn't a more insistent instruction to the
model -- it's a status computed by code that never asks the model anything. This script IS that
computation. It reads only files on disk (via contracts.py's structural checks plus its own
existence/page-count checks) and reports DONE or INCOMPLETE. An agent can run it, read it, and
explain it -- it cannot talk it into a different answer.

This is the gate scripts/finalize_submission_job.py itself enforces before writing to the DB
(see contracts.check_finalize_ready) -- this script is the human/agent-facing report of the
same underlying check, with the full breakdown of what's missing when the answer is INCOMPLETE.

Usage:
    python scripts/check_submission_status.py data/submissions/{company} [...]
        Exits 0 only if every folder passed is DONE. Exits 1 if any folder is INCOMPLETE.
"""
from __future__ import annotations

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

import contracts  # noqa: E402

_RUBRIC_THRESHOLDS = {"resume": 70, "cover_letter": 65}


def compute_status(folder: str) -> dict:
    folder = folder.rstrip("/\\")
    company = os.path.basename(folder)
    checks: list[dict] = []
    warnings: list[str] = []

    def record(name: str, ok: bool, errors: list[str] | None = None):
        checks.append({"name": name, "passed": ok, "errors": errors or []})

    # -- Documents exist at all --
    resume_exists = os.path.exists(os.path.join(folder, "Resume.md"))
    cover_exists = os.path.exists(os.path.join(folder, "CoverLetter.md"))
    record("Resume.md exists", resume_exists)
    record("CoverLetter.md exists", cover_exists)

    resume_pdf = os.path.exists(os.path.join(folder, "Resume.pdf"))
    cover_pdf = os.path.exists(os.path.join(folder, "CoverLetter.pdf"))
    record("Resume.pdf compiled", resume_pdf)
    record("CoverLetter.pdf compiled", cover_pdf)

    # -- stage0_fit_gate.json --
    stage0_exists = os.path.exists(os.path.join(folder, "stage0_fit_gate.json"))
    if stage0_exists:
        ok, errors = contracts.check_stage0_fit_gate(folder)
        record("stage0_fit_gate.json valid", ok, errors)
    else:
        record("stage0_fit_gate.json exists", False, ["not found -- Stage 0 was never persisted for this company"])

    # -- verification_receipt.json + freshness --
    receipt_exists = os.path.exists(os.path.join(folder, "verification_receipt.json"))
    if receipt_exists:
        ok, errors = contracts.check_verification_receipt(folder)
        record("verification_receipt.json: mechanically clean", ok, errors)
        ok, errors = contracts.check_freshness(folder)
        record("verification_receipt.json: fresh (newer than the .md files)", ok, errors)
    else:
        record("verification_receipt.json exists", False, ["not found -- scripts/verify_submission.py was never run"])

    # -- draft_manifest.json --
    manifest_exists = os.path.exists(os.path.join(folder, "draft_manifest.json"))
    resume_score = cover_score = None
    if manifest_exists:
        ok, errors = contracts.check_draft_manifest(folder)
        record("draft_manifest.json valid (rubric_score + verification_passed populated)", ok, errors)
        manifest, _ = contracts.load_json(os.path.join(folder, "draft_manifest.json"))
        if manifest and manifest.get("verification_passed") is not True:
            record("draft_manifest.json: verification_passed is true", False, ["verification_passed is not True"])
        if manifest:
            rubric = manifest.get("rubric_score") or {}
            resume_score = (rubric.get("resume") or {}).get("total")
            cover_score = (rubric.get("cover_letter") or {}).get("total")
            if isinstance(resume_score, (int, float)) and resume_score < _RUBRIC_THRESHOLDS["resume"]:
                warnings.append(f"resume rubric score {resume_score} is below the {_RUBRIC_THRESHOLDS['resume']} CONVERT-READY floor")
            if isinstance(cover_score, (int, float)) and cover_score < _RUBRIC_THRESHOLDS["cover_letter"]:
                warnings.append(f"cover letter rubric score {cover_score} is below the {_RUBRIC_THRESHOLDS['cover_letter']} CONVERT-READY floor")
    else:
        record("draft_manifest.json exists", False, ["not found -- rubric_score was never recorded"])

    done = all(c["passed"] for c in checks)

    # CR-078 AC-302/303: surface the CR-076/077/084 workflow-authority signal alongside the
    # existing DONE oracle -- additive only, never folded into `checks`/`done` above. Per AC-303,
    # a hard cutover would fail its own bar right now: check_workflow_complete() requires real
    # stage_receipts through Stage 3, and as of this CR essentially no real folder has been run
    # through scripts/run_submission.py yet, so requiring it here would flip every already-DONE
    # submission to INCOMPLETE -- the exact regression this CR exists to prevent. This field is
    # informational only ("has this folder been adopted into the new system, and if so what does
    # it say") until a real migration pass populates receipts for the existing folders and a
    # follow-up CR can safely fold it into `done`.
    wf_state_path = os.path.join(folder, "workflow_state.json")
    workflow_authority: dict = {"adopted": os.path.exists(wf_state_path)}
    if workflow_authority["adopted"]:
        wf_ok, wf_errors = contracts.check_workflow_complete(folder)
        state, _ = contracts.load_json(wf_state_path)
        workflow_authority["status"] = (state or {}).get("status")
        workflow_authority["check_workflow_complete"] = wf_ok
        workflow_authority["complete_reasons"] = wf_errors

    return {
        "submission": company,
        "checks": checks,
        "warnings": warnings,
        "resume_rubric_score": resume_score,
        "cover_letter_rubric_score": cover_score,
        "done": done,
        "workflow_authority": workflow_authority,
    }


def _print_report(status: dict) -> None:
    print(f"\n{status['submission']}:")
    for c in status["checks"]:
        mark = "PASS" if c["passed"] else "FAIL"
        print(f"  [{mark}] {c['name']}")
        for e in c["errors"]:
            print(f"         - {e}")
    for w in status["warnings"]:
        print(f"  [WARN] {w}")
    print(f"  STATUS: {'DONE' if status['done'] else 'INCOMPLETE'}")
    wf = status.get("workflow_authority") or {}
    if wf.get("adopted"):
        print(
            f"  [INFO] workflow-authority (CR-076+): status={wf.get('status')} "
            f"check_workflow_complete={'YES' if wf.get('check_workflow_complete') else 'NO'}"
        )
    else:
        print("  [INFO] workflow-authority (CR-076+): not yet adopted (no workflow_state.json)")


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    all_done = True
    for folder in folders:
        status = compute_status(folder)
        _print_report(status)
        if not status["done"]:
            all_done = False

    sys.exit(0 if all_done else 1)


if __name__ == "__main__":
    main()
