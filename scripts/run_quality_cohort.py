#!/usr/bin/env python3
"""Build a read-only five-JD first-draft quality cohort report."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import contracts  # noqa: E402

COHORT_SIZE = 5
REPORT_SCHEMA_VERSION = 1
EXIT_SIGNAL_FAILED = 1
EXIT_INCOMPLETE = 2


def build_parser() -> argparse.ArgumentParser:
    """Return the command-line parser for the cohort reporter."""
    parser = argparse.ArgumentParser(
        description=(
            "Track the immutable first-draft 70/65 floor signal for an explicit "
            "five-JD cohort. Skip and Block folders remain visible but do not "
            "enter the document-quality denominator."
        )
    )
    parser.add_argument(
        "folders",
        nargs="+",
        type=Path,
        help="Attempted cohort folders, in run order.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON report path. The command is read-only when omitted.",
    )
    return parser


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    """Read one JSON file and return its value plus an optional error."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path.name} not found"
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path.name} could not be read/parsed: {exc}"


def _sha256(path: Path) -> str | None:
    """Return a file SHA-256, or None when the file cannot be read."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _finite_total(row: dict[str, Any], side: str) -> float | None:
    """Return a finite non-boolean rubric total from a scorecard row."""
    side_data = row.get(side)
    if not isinstance(side_data, dict):
        return None
    total = side_data.get("total")
    if (
        not isinstance(total, (int, float))
        or isinstance(total, bool)
        or not math.isfinite(total)
    ):
        return None
    return float(total)


def _workflow_status(folder: Path) -> str | None:
    """Return the workflow status when workflow_state.json is readable."""
    data, _error = _read_json(folder / "workflow_state.json")
    if not isinstance(data, dict):
        return None
    status = data.get("status")
    return status if isinstance(status, str) and status.strip() else None


def _stage0_receipt_errors(folder: Path, decision: str) -> list[str]:
    """Return errors when canonical Stage 0 receipt evidence is invalid."""
    receipt, receipt_error = _read_json(folder / "stage_receipts" / "stage0.json")
    state, state_error = _read_json(folder / "workflow_state.json")
    errors: list[str] = []
    if receipt_error or not isinstance(receipt, dict):
        return [receipt_error or "stage_receipts/stage0.json is not an object"]
    if state_error or not isinstance(state, dict):
        return [state_error or "workflow_state.json is not an object"]

    expected_status = "COMPLETE" if decision == "PASS" else "SKIPPED"
    if receipt.get("stage") != "stage0":
        errors.append("stage0 receipt must identify stage0")
    if receipt.get("status") != expected_status:
        errors.append(f"stage0 receipt status must be {expected_status}")
    if receipt.get("issued_by") != "scripts/run_submission.py":
        errors.append("stage0 receipt must be issued by scripts/run_submission.py")
    result = receipt.get("result")
    if not isinstance(result, dict) or result.get("decision") != decision:
        errors.append(f"stage0 receipt result.decision must be {decision}")

    receipt_id = receipt.get("receipt_id")
    body = {key: value for key, value in receipt.items() if key != "receipt_id"}
    canonical = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    expected_id = f"stage0:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
    if receipt_id != expected_id:
        errors.append("stage0 receipt_id does not match its canonical body")

    stages = state.get("stages")
    stage0_state = stages.get("stage0") if isinstance(stages, dict) else None
    if not isinstance(stage0_state, dict) or stage0_state.get("receipt_id") != receipt_id:
        errors.append("workflow_state stage0 receipt pointer does not match")

    for relative_path in ("Original_JD.txt", "stage0_fit_gate.json"):
        hash_group = "input_hashes" if relative_path == "Original_JD.txt" else "output_hashes"
        recorded = receipt.get(hash_group)
        current = _sha256(folder / relative_path)
        if (
            current is None
            or not isinstance(recorded, dict)
            or recorded.get(relative_path) != current
        ):
            errors.append(f"stage0 receipt hash is stale or missing for {relative_path}")
    return errors


def _stage0_decision(folder: Path) -> tuple[str | None, list[str]]:
    """Return a normalized Stage 0 decision and any contract errors."""
    errors: list[str] = []
    ok, contract_errors = contracts.check_stage0_fit_gate(str(folder))
    if not ok:
        errors.extend(contract_errors)
        return None, errors
    data, read_error = _read_json(folder / "stage0_fit_gate.json")
    if read_error or not isinstance(data, dict):
        errors.append(read_error or "stage0_fit_gate.json is not an object")
        return None, errors
    decision = data.get("decision")
    if not isinstance(decision, str) or decision.upper() not in {"PASS", "SKIP"}:
        errors.append("stage0_fit_gate.json: 'decision' must be PASS or SKIP")
        return None, errors
    normalized = decision.upper()
    errors.extend(_stage0_receipt_errors(folder, normalized))
    return normalized, errors


def _first_draft_identity(
    folder: Path,
) -> tuple[dict[str, str] | None, str | None, list[str]]:
    """Return immutable first-draft hashes, observation time, and errors."""
    snapshot_dir = folder / "stage1_first_draft"
    history, read_error = _read_json(snapshot_dir / "verify_history.json")
    errors: list[str] = []
    if read_error:
        return None, None, [read_error]
    if not isinstance(history, list) or not history or not isinstance(history[0], dict):
        return None, None, [
            "stage1_first_draft/verify_history.json must contain a first attempt"
        ]

    first = history[0]
    if first.get("attempt") != 1:
        errors.append("first verify_history row must have attempt=1")
    observed_at = first.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        errors.append("first verify_history row must have a non-empty observed_at")
        observed_at = None

    hashes: dict[str, str] = {}
    for side, filename, history_key in (
        ("resume", "Resume.md", "resume_sha256"),
        ("cover_letter", "CoverLetter.md", "cover_sha256"),
    ):
        digest = _sha256(snapshot_dir / filename)
        recorded = first.get(history_key)
        if digest is None:
            errors.append(f"stage1_first_draft/{filename} not found or unreadable")
            continue
        if not isinstance(recorded, str) or recorded != digest:
            errors.append(
                f"first verify_history {history_key} does not match immutable {filename}"
            )
            continue
        hashes[side] = digest
    return (hashes if len(hashes) == 2 else None), observed_at, errors


def _first_draft_scores(
    folder: Path,
    hashes: dict[str, str],
) -> tuple[dict[str, float] | None, list[str]]:
    """Return the unique authoring-session score for first-draft hashes."""
    rows, row_errors = contracts._load_rubric_scorecards(str(folder))
    if row_errors:
        return None, row_errors

    matching = [
        row
        for row in rows
        if row.get("reviewer_role") == "authoring_session"
        and isinstance(row.get("document_sha256"), dict)
        and row["document_sha256"].get("resume") == hashes["resume"]
        and row["document_sha256"].get("cover_letter") == hashes["cover_letter"]
    ]
    if len(matching) != 1:
        return None, [
            "reviews/rubric_scorecard.json must contain exactly one "
            "authoring_session row for the immutable first-draft hashes"
        ]
    resume = _finite_total(matching[0], "resume")
    cover = _finite_total(matching[0], "cover_letter")
    if resume is None or cover is None:
        return None, ["first-draft scorecard totals must be finite numbers"]
    return {"resume": resume, "cover_letter": cover}, []


def inspect_case(folder: Path, sequence: int) -> dict[str, Any]:
    """Inspect one attempted folder without modifying it."""
    resolved = folder.resolve()
    row: dict[str, Any] = {
        "sequence": sequence,
        "slug": folder.name,
        "folder": str(resolved),
        "classification": "INCOMPLETE",
        "denominator_included": False,
        "exclusion_reason": None,
        "workflow_status": _workflow_status(folder),
        "stage0_decision": None,
        "jd_sha256": _sha256(folder / "Original_JD.txt"),
        "first_draft_observed_at": None,
        "first_draft_sha256": None,
        "first_draft_scores": None,
        "first_draft_floor": None,
        "errors": [],
    }
    if not folder.is_dir():
        row["errors"].append("folder not found")
        return row
    if row["jd_sha256"] is None:
        row["errors"].append("Original_JD.txt not found or unreadable")

    decision, stage0_errors = _stage0_decision(folder)
    row["stage0_decision"] = decision
    row["errors"].extend(stage0_errors)
    if decision == "SKIP":
        if not row["errors"]:
            row["classification"] = "EXCLUDED_SKIP"
            row["exclusion_reason"] = "stage0_skip"
        return row
    if decision != "PASS" or row["errors"]:
        return row

    hashes, observed_at, draft_errors = _first_draft_identity(folder)
    row["first_draft_observed_at"] = observed_at
    row["errors"].extend(draft_errors)
    if hashes is None:
        snapshot_dir = folder / "stage1_first_draft"
        if row["workflow_status"] == "FAILED" and not snapshot_dir.exists():
            row["classification"] = "EXCLUDED_BLOCK"
            row["exclusion_reason"] = "terminal_failure_before_first_draft"
            row["errors"] = []
        else:
            row["classification"] = "PENDING"
        return row

    row["first_draft_sha256"] = hashes
    scores, score_errors = _first_draft_scores(folder, hashes)
    row["errors"].extend(score_errors)
    if scores is None:
        return row

    # Implements FR-318 / AC-415: track the same locked 70/65 floors.
    resume_pass = scores["resume"] >= contracts.RUBRIC_FLOOR_RESUME
    cover_pass = scores["cover_letter"] >= contracts.RUBRIC_FLOOR_COVER_LETTER
    row["first_draft_scores"] = scores
    row["first_draft_floor"] = {
        "resume_pass": resume_pass,
        "cover_letter_pass": cover_pass,
        "pair_pass": resume_pass and cover_pass,
    }
    row["classification"] = "ELIGIBLE"
    return row


def evaluate_cohort(folders: list[Path]) -> dict[str, Any]:
    """Evaluate an explicit attempted cohort and return a stable report."""
    cases = [inspect_case(folder, index) for index, folder in enumerate(folders, 1)]
    errors: list[str] = []

    for row in cases:
        if row["classification"] in {"PENDING", "INCOMPLETE"}:
            errors.append(
                f"{row['slug']}: "
                + ("; ".join(row["errors"]) if row["errors"] else "case is not terminal")
            )

    resolved_paths = [str(folder.resolve()).lower() for folder in folders]
    if len(set(resolved_paths)) != len(resolved_paths):
        errors.append("attempted cohort contains a duplicate folder path")

    eligible = [row for row in cases if row["classification"] == "ELIGIBLE"]
    jd_hashes = [row["jd_sha256"] for row in eligible]
    if len(set(jd_hashes)) != len(jd_hashes):
        errors.append("eligible cohort contains duplicate Original_JD.txt content")
    if len(eligible) < COHORT_SIZE:
        errors.append(
            f"eligible denominator is {len(eligible)}; exactly {COHORT_SIZE} are required"
        )
    elif len(eligible) > COHORT_SIZE:
        errors.append(
            f"eligible denominator is {len(eligible)}; select exactly {COHORT_SIZE} "
            "instead of silently dropping eligible runs"
        )

    denominator_complete = not errors and len(eligible) == COHORT_SIZE
    if denominator_complete:
        for row in eligible:
            row["denominator_included"] = True

    pair_pass_count = sum(
        1
        for row in eligible
        if isinstance(row.get("first_draft_floor"), dict)
        and row["first_draft_floor"]["pair_pass"]
    )
    consecutive_resume_failures: list[list[str]] = []
    if denominator_complete:
        for previous, current in zip(eligible, eligible[1:]):
            previous_floor = previous["first_draft_floor"]
            current_floor = current["first_draft_floor"]
            if not previous_floor["resume_pass"] and not current_floor["resume_pass"]:
                consecutive_resume_failures.append([previous["slug"], current["slug"]])

    if not denominator_complete:
        signal = "NOT_EVALUABLE"
    elif pair_pass_count >= 4 and not consecutive_resume_failures:
        signal = "PASS"
    else:
        signal = "FAIL"

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "cohort_size_required": COHORT_SIZE,
        "attempted_count": len(cases),
        "eligible_count": len(eligible),
        "excluded_count": sum(
            row["classification"] in {"EXCLUDED_SKIP", "EXCLUDED_BLOCK"} for row in cases
        ),
        "pending_or_invalid_count": sum(
            row["classification"] in {"PENDING", "INCOMPLETE"} for row in cases
        ),
        "denominator_status": "COMPLETE" if denominator_complete else "INCOMPLETE",
        "floors": {
            "resume": contracts.RUBRIC_FLOOR_RESUME,
            "cover_letter": contracts.RUBRIC_FLOOR_COVER_LETTER,
        },
        "first_draft_signal": {
            "status": signal,
            "pairs_clearing_both_floors": pair_pass_count,
            "pairs_required": 4,
            "no_two_consecutive_resume_below_floor": not consecutive_resume_failures,
            "consecutive_resume_below_floor": consecutive_resume_failures,
            "scope": (
                "Untouched first-draft floor signal only. This does not establish "
                "correction-round, PDF-lineage, cost, or DAILY_USE_READY criteria."
            ),
        },
        "errors": errors,
        "cases": cases,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """Write a report atomically enough for a local evidence artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    """Run the cohort CLI and return a signal-aware process status."""
    args = build_parser().parse_args(argv)
    report = evaluate_cohort(args.folders)
    if args.out is not None:
        _write_report(args.out, report)

    signal = report["first_draft_signal"]
    print(
        f"Denominator: {report['eligible_count']}/{report['cohort_size_required']} "
        f"({report['denominator_status']})"
    )
    print(
        "Untouched pairs clearing 70/65: "
        f"{signal['pairs_clearing_both_floors']}/{report['eligible_count']}"
    )
    print(
        "No consecutive below-floor resumes: "
        f"{signal['no_two_consecutive_resume_below_floor']}"
    )
    print(f"First-draft signal: {signal['status']}")
    if report["errors"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_INCOMPLETE
    if signal["status"] != "PASS":
        return EXIT_SIGNAL_FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())
