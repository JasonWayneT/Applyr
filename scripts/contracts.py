"""
Handoff-contract validation for the generate-submission process's canonical artifacts.

Why this exists (2026-08-06): every stage in this pipeline already writes a JSON artifact for
the next stage to read (stage0_fit_gate.json -> draft_manifest.json -> verification_receipt.json),
but nothing has ever actually validated those files' shape before trusting them. Every existing
read (in verify_submission.py, finalize_submission_job.py) is a plain `.get()` with a silent
fallback to None or empty -- a malformed or missing artifact doesn't block anything, it just
produces a quieter wrong answer downstream. That's the exact failure mode a handoff contract is
supposed to prevent: a stage should refuse to proceed on a bad upstream artifact, not improvise
around it. See the SESSION conversation this came out of (2026-08-06) for the fuller reasoning --
short version: prose instructions to "run the verification steps" have failed silently three
times in this project's history (case-sensitivity bug, dropped resume lint, byte-identical
rubric scores); the fix each time was a mechanical artifact the process can't improvise past.
This module is that same fix applied one layer earlier -- at the artifact handoffs themselves,
not just the final verification gate.

Two kinds of check per artifact:
  1. Structural -- required keys present, right type, non-empty where that matters.
  2. Freshness (verification_receipt.json only) -- is it newer than the documents it claims to
     have verified? A receipt older than Resume.md/CoverLetter.md means the documents changed
     after the last real verification pass -- stale, not passing.

This module does NOT decide whether every stage has run yet -- see check_submission_status.py
for that (it computes overall done/not-done from the filesystem, independent of any agent's
self-report, and uses these functions as its building blocks).

Usage:
    python scripts/contracts.py data/submissions/{company} [...]
        Runs every check that applies to whichever of the three artifacts exist in each folder.
        A file that doesn't exist yet (e.g. draft_manifest.json before Stage 2 has run) is not
        itself a failure here -- this is a shape/freshness check on what IS present, not a
        "has every stage run" check. Exits 1 if any EXISTING artifact fails its contract.

Also importable:
    check_stage0_fit_gate(folder) -> (ok, errors)
    check_draft_manifest(folder) -> (ok, errors)
    check_verification_receipt(folder) -> (ok, errors)
    check_freshness(folder) -> (ok, errors)
    check_finalize_ready(folder) -> (ok, errors)   # the combined gate finalize_submission_job.py uses
"""
from __future__ import annotations

import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(path: str) -> tuple[dict | None, str | None]:
    """Returns (data, error). error is None on success."""
    if not os.path.exists(path):
        return None, f"{os.path.basename(path)} not found"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return None, f"{os.path.basename(path)} could not be read/parsed: {e}"
    if not isinstance(data, dict):
        return None, f"{os.path.basename(path)} is not a JSON object"
    return data, None


# ---------------------------------------------------------------------------
# stage0_fit_gate.json
# ---------------------------------------------------------------------------

_STAGE0_REQUIRED_LIST_KEYS = ["required", "preferred", "responsibilities", "flagged_gaps"]


def check_stage0_fit_gate(folder: str) -> tuple[bool, list[str]]:
    """Per SKILL.md Stage 0 step 5: 'required list, preferred list, responsibilities list,
    flagged gaps, stage signal, thin-JD flag' -- persisted as this file. Stage 1 depends on
    all of these existing, not just required/preferred (the responsibilities list was silently
    missing from every real file for a while before that was caught -- see SKILL.md Stage 0
    step 5's own history note)."""
    path = os.path.join(folder, "stage0_fit_gate.json")
    data, err = load_json(path)
    if err:
        return False, [err]

    errors: list[str] = []
    if not data.get("company"):
        errors.append("stage0_fit_gate.json: missing or empty 'company'")
    for key in _STAGE0_REQUIRED_LIST_KEYS:
        val = data.get(key)
        if not isinstance(val, list):
            errors.append(f"stage0_fit_gate.json: '{key}' must be a list (got {type(val).__name__})")
    if not data.get("stage_signal"):
        errors.append("stage0_fit_gate.json: missing or empty 'stage_signal' (use 'unknown' if the JD doesn't state one -- never omit the key)")
    if "thin_jd" not in data or not isinstance(data.get("thin_jd"), bool):
        errors.append("stage0_fit_gate.json: 'thin_jd' must be present and a real boolean")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# draft_manifest.json
# ---------------------------------------------------------------------------

def _check_rubric_score_shape(score) -> list[str]:
    errors = []
    if not isinstance(score, dict):
        return ["'rubric_score' must be an object with 'resume' and 'cover_letter' sub-scores"]
    for side in ("resume", "cover_letter"):
        sub = score.get(side)
        if not isinstance(sub, dict) or not isinstance(sub.get("total"), (int, float)):
            errors.append(f"'rubric_score.{side}.total' must be a real number -- a genuinely scored document always has one")
    return errors


def check_draft_manifest(folder: str) -> tuple[bool, list[str]]:
    """Per SKILL.md Stage 3: 'draft_manifest.json with verification_passed/rubric_score
    populated (same field shape the old draft_compiler.py wrote)'."""
    path = os.path.join(folder, "draft_manifest.json")
    data, err = load_json(path)
    if err:
        return False, [err]

    errors: list[str] = []
    if not data.get("company"):
        errors.append("draft_manifest.json: missing or empty 'company'")
    if not data.get("title"):
        errors.append("draft_manifest.json: missing or empty 'title'")
    if "verification_passed" not in data or not isinstance(data.get("verification_passed"), bool):
        errors.append("draft_manifest.json: 'verification_passed' must be present and a real boolean")
    errors.extend(f"draft_manifest.json: {e}" for e in _check_rubric_score_shape(data.get("rubric_score")))

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# verification_receipt.json
# ---------------------------------------------------------------------------

_RECEIPT_BOOL_KEYS = [
    "mechanically_verified",
    "lint_all_clean",
    "unapproved_metrics_clean",
    "page_counts_ok",
]


def check_verification_receipt(folder: str) -> tuple[bool, list[str]]:
    """Structural check AND a pass/fail check -- a receipt that parses fine but reports
    mechanically_verified=False is not a satisfied contract for anything downstream. Callers
    that only care about shape (not about whether it passed) should read the file directly."""
    path = os.path.join(folder, "verification_receipt.json")
    data, err = load_json(path)
    if err:
        return False, [err]

    errors: list[str] = []
    if not data.get("submission"):
        errors.append("verification_receipt.json: missing or empty 'submission'")
    for key in _RECEIPT_BOOL_KEYS:
        if key not in data or not isinstance(data.get(key), bool):
            errors.append(f"verification_receipt.json: '{key}' must be present and a real boolean")
    for key in ("check_resume", "check_cover_letter"):
        sub = data.get(key)
        if not isinstance(sub, dict) or "passed" not in sub:
            errors.append(f"verification_receipt.json: '{key}.passed' missing")

    if errors:
        return False, errors

    if data.get("mechanically_verified") is not True:
        return False, ["verification_receipt.json: mechanically_verified is False -- re-run scripts/verify_submission.py and fix what it flags, this is not a passing receipt"]

    return True, []


def check_freshness(folder: str) -> tuple[bool, list[str]]:
    """Is verification_receipt.json newer than the documents it claims to have verified? An
    edit made after the last real verification pass leaves a stale receipt on disk that still
    reads as passing -- this is the mtime-based version of the artifact-lineage problem (a
    downstream artifact silently referencing a stale upstream one)."""
    receipt_path = os.path.join(folder, "verification_receipt.json")
    if not os.path.exists(receipt_path):
        return False, ["verification_receipt.json not found -- nothing to check freshness against"]
    receipt_mtime = os.path.getmtime(receipt_path)

    errors: list[str] = []
    for doc in ("Resume.md", "CoverLetter.md"):
        doc_path = os.path.join(folder, doc)
        if os.path.exists(doc_path) and os.path.getmtime(doc_path) > receipt_mtime:
            errors.append(
                f"{doc} was edited after verification_receipt.json was generated -- stale receipt, "
                f"re-run scripts/verify_submission.py"
            )
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Combined finalize gate
# ---------------------------------------------------------------------------

def check_finalize_ready(folder: str) -> tuple[bool, list[str]]:
    """The gate finalize_submission_job.py enforces before it will write to the DB: a passing,
    fresh verification receipt AND a draft_manifest.json that says verification_passed."""
    errors: list[str] = []

    _, errs = check_verification_receipt(folder)
    errors.extend(errs)

    _, errs = check_freshness(folder)
    errors.extend(errs)

    _, errs = check_draft_manifest(folder)
    errors.extend(errs)
    manifest_path = os.path.join(folder, "draft_manifest.json")
    manifest, _ = load_json(manifest_path)
    if manifest is not None and manifest.get("verification_passed") is not True:
        errors.append("draft_manifest.json: verification_passed is not True")

    return len(errors) == 0, errors


def main() -> None:
    folders = sys.argv[1:]
    if not folders:
        print(__doc__)
        sys.exit(1)

    any_failed = False
    for folder in folders:
        folder = folder.rstrip("/\\")
        company = os.path.basename(folder)
        print(f"\n{company}:")

        checks = [
            ("stage0_fit_gate.json", check_stage0_fit_gate, "stage0_fit_gate.json"),
            ("draft_manifest.json", check_draft_manifest, "draft_manifest.json"),
            ("verification_receipt.json", check_verification_receipt, "verification_receipt.json"),
        ]
        for label, fn, filename in checks:
            if not os.path.exists(os.path.join(folder, filename)):
                print(f"  [SKIP] {label} -- not present yet")
                continue
            ok, errors = fn(folder)
            if ok:
                print(f"  [PASS] {label}")
            else:
                any_failed = True
                print(f"  [FAIL] {label}")
                for e in errors:
                    print(f"         - {e}")

        if os.path.exists(os.path.join(folder, "verification_receipt.json")):
            ok, errors = check_freshness(folder)
            if ok:
                print("  [PASS] freshness (receipt newer than Resume.md/CoverLetter.md)")
            else:
                any_failed = True
                print("  [FAIL] freshness")
                for e in errors:
                    print(f"         - {e}")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
