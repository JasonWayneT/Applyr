"""
Stage-gate enforcement for CR-075 (Epic 4, Story 4.1).

contracts.py stays a pure predicate library (structural / freshness / ready checks that return
(bool, list[str])). This module owns the *enforcement* side: refuse to proceed on a failed
check, honour the per-stage --force policy, and durably log every override.

Why a separate module (locked architecture decision in CR-075 epics):
  check_submission_status.py imports contracts for read-only reporting. Putting argparse,
  sys.exit, subprocess, or durable-log writes into contracts.py would make merely *reporting*
  status have side effects (including mutating data/.force_override_log.json). One concern
  per module: contracts = predicates; stage_gate = enforcement + force policy + override log.

Usage (importable):
    from stage_gate import (
        StageGateNotReadyError,
        validate_force,
        require_stage_ready,
        log_force_override,
        add_force_args,
        parse_force_flags,
    )

    require_stage_ready("stage0", folder, force=False, force_reason=None)
    # raises StageGateNotReadyError with an itemized message on failure

    force, reason = parse_force_flags(sys.argv)  # for verify_submission.py's hand-rolled argv

Tests inject OVERRIDE_LOG_PATH so they never write the real data/.force_override_log.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Callable

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_DEFAULT_OVERRIDE_LOG = os.path.join(_REPO_ROOT, "data", ".force_override_log.json")

# Tests set this to a temp path; production leaves it None and uses _DEFAULT_OVERRIDE_LOG.
OVERRIDE_LOG_PATH: str | None = None

sys.path.insert(0, _SCRIPT_DIR)
import contracts  # noqa: E402

_STAGE_CHECKS: dict[str, Callable[[str], tuple[bool, list[str]]]] = {
    "stage0": contracts.check_stage0_fit_gate,
    "stage1": contracts.check_stage1_ready,
    "stage2": contracts.check_stage2_ready,
    "stage3": contracts.check_finalize_ready,
}

_VALID_STAGES = frozenset(_STAGE_CHECKS)


class StageGateNotReadyError(Exception):
    """Raised when a stage gate fails and no valid --force override was supplied.

    Carries the itemized error list from the underlying contracts check so callers can
    print or re-raise without re-running the predicate.
    """

    def __init__(self, stage: str, folder: str, errors: list[str]):
        self.stage = stage
        self.folder = folder
        self.errors = list(errors)
        detail = "\n".join(f"  - {e}" for e in self.errors)
        super().__init__(
            f"{folder} is not ready for {stage}:\n{detail}\n"
            f"Fix the items above, or pass --force"
            + (" --force-reason \"...\" " if stage == "stage2" else " ")
            + "if this is a deliberate override."
        )


class StageGateForceError(Exception):
    """Raised when --force flags violate the per-stage policy (e.g. bare --force at Stage 2)."""


def _override_log_path() -> str:
    if OVERRIDE_LOG_PATH is not None:
        return OVERRIDE_LOG_PATH
    env = os.environ.get("APPLYR_FORCE_OVERRIDE_LOG")
    if env:
        return env
    return _DEFAULT_OVERRIDE_LOG


def validate_force(stage: str, force: bool, force_reason: str | None) -> None:
    """Enforce the per-stage --force asymmetry (CR-075 Decision item 5 / AC10).

    - Stages 0 / 1 / 3: bare --force is accepted (reason optional).
    - Stage 2: --force requires a non-empty --force-reason string. A bare --force is rejected.
    - force=False: always valid (no override attempted).

    Raises StageGateForceError on a policy violation. Does not itself run any contracts check.
    """
    if stage not in _VALID_STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {sorted(_VALID_STAGES)}")
    if not force:
        return
    if stage == "stage2":
        if force_reason is None or not str(force_reason).strip():
            raise StageGateForceError(
                "Stage 2 override requires --force AND a non-empty --force-reason \"...\". "
                "A bare --force is rejected (AC10) -- Stage 2's audit override is the decision "
                "point the byte-identical-rubric-score incident lives at."
            )


def log_force_override(
    stage: str,
    folder: str,
    reason: str | None,
    argv: list[str] | None = None,
) -> None:
    """Append one override record to data/.force_override_log.json (or OVERRIDE_LOG_PATH).

    Shape: {timestamp, stage, folder, reason, argv}. Creates the file as a JSON array on
    first write. Never raises on a missing parent dir that we can create; surface I/O errors
    to the caller so a silent log failure cannot mask an override.
    """
    path = _override_log_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": stage,
        "folder": folder,
        "reason": reason if reason is not None else "",
        "argv": list(argv) if argv is not None else list(sys.argv),
    }

    existing: list = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                existing = data
        except (OSError, json.JSONDecodeError):
            # Corrupt / unreadable log: start a fresh array rather than lose the new record,
            # but keep a backup of whatever was there so nothing is silently deleted.
            try:
                os.replace(path, path + ".corrupt_backup")
            except OSError:
                pass
            existing = []

    existing.append(record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)
        f.write("\n")


def require_stage_ready(
    stage: str,
    folder: str,
    force: bool = False,
    force_reason: str | None = None,
    argv: list[str] | None = None,
) -> None:
    """Run the matching contracts check; raise or log-and-proceed per --force policy.

    On a clean check: return silently.
    On a failed check with a valid override: log the override, return.
    On a failed check with no / invalid override: raise StageGateNotReadyError (or
    StageGateForceError if the force flags themselves are illegal).
    """
    if stage not in _VALID_STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {sorted(_VALID_STAGES)}")

    validate_force(stage, force, force_reason)

    check = _STAGE_CHECKS[stage]
    ok, errors = check(folder)
    if ok:
        return
    if force:
        log_force_override(stage, folder, force_reason, argv=argv)
        return
    raise StageGateNotReadyError(stage, folder, errors)


def add_force_args(parser: argparse.ArgumentParser, stage: str) -> argparse.ArgumentParser:
    """Attach the right --force / --force-reason flags for this stage to an argparse parser.

    Stage 2 gets both flags (reason required at validate time). Stages 0/1/3 get bare --force
    only -- matching finalize_submission_job.py's existing flag surface for Stage 3.
    """
    if stage not in _VALID_STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {sorted(_VALID_STAGES)}")

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            f"Bypass the {stage} readiness gate (logged to data/.force_override_log.json)."
            + (
                " Stage 2 also requires --force-reason."
                if stage == "stage2"
                else ""
            )
        ),
    )
    if stage == "stage2":
        parser.add_argument(
            "--force-reason",
            default=None,
            help="Required with --force at Stage 2: why this override is deliberate (AC10).",
        )
    return parser


def parse_force_flags(argv: list[str]) -> tuple[bool, str | None]:
    """Extract --force / --force-reason from a raw argv list (verify_submission.py style).

    Does not mutate argv. Supports:
      --force
      --force-reason VALUE
      --force-reason=VALUE

    Returns (force: bool, force_reason: str | None). Does not validate policy -- call
    validate_force(stage, ...) after deciding which stage is being gated.
    """
    force = False
    force_reason: str | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--force":
            force = True
            i += 1
            continue
        if arg == "--force-reason":
            if i + 1 >= len(argv):
                raise StageGateForceError("--force-reason requires a non-empty value")
            force_reason = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--force-reason="):
            force_reason = arg.split("=", 1)[1]
            i += 1
            continue
        i += 1
    return force, force_reason


def strip_force_flags(argv: list[str]) -> list[str]:
    """Return argv with --force / --force-reason(--=) removed (for folder-path parsing)."""
    out: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--force":
            i += 1
            continue
        if arg == "--force-reason":
            i += 2
            continue
        if arg.startswith("--force-reason="):
            i += 1
            continue
        out.append(arg)
        i += 1
    return out


def folder_has_rubric_score(folder: str) -> bool:
    """True when draft_manifest.json carries a populated rubric_score (both totals present).

    Matches the shape check_stage2_ready / _check_rubric_score_shape require -- used to decide
    whether a failed Stage 2 gate is binding (rubric present) or mid-flow informational.
    """
    path = os.path.join(folder, "draft_manifest.json")
    data, err = contracts.load_json(path)
    if err or data is None:
        return False
    score = data.get("rubric_score")
    if not isinstance(score, dict):
        return False
    for side in ("resume", "cover_letter"):
        sub = score.get(side)
        if not isinstance(sub, dict) or not isinstance(sub.get("total"), (int, float)):
            return False
    return True


def apply_stage2_verdict(
    folder: str,
    *,
    force: bool = False,
    force_reason: str | None = None,
    argv: list[str] | None = None,
) -> bool:
    """Print STAGE 2: COMPLETE / INCOMPLETE (itemized) and apply AC4/AC10 force policy.

    Returns True when the caller should treat this as a *binding* Stage 2 gate failure
    (exit non-zero for the gate). Returns False when:
      - the gate passes, or
      - the gate fails but no rubric_score is present yet (mid-flow: keep existing exit
        semantics -- print INCOMPLETE, do not fail the process on the gate alone), or
      - a valid Stage 2 --force + --force-reason override was applied (logged).

    Raises StageGateForceError when an override is attempted with a bare --force (no reason).
    """
    folder = folder.rstrip("/\\")
    company = os.path.basename(folder)
    ok, errors = contracts.check_stage2_ready(folder)
    if ok:
        print(f"{company}: STAGE 2: COMPLETE")
        return False

    print(f"{company}: STAGE 2: INCOMPLETE")
    for e in errors:
        print(f"  - {e}")

    if not folder_has_rubric_score(folder):
        # Mid-flow: rubric not entered yet. Verdict is informational only.
        return False

    # Rubric present -- Stage 2 gate is binding (AC4 / locked decision on exit semantics).
    if force:
        validate_force("stage2", force, force_reason)
        log_force_override("stage2", folder, force_reason, argv=argv)
        print(
            f"{company}: STAGE 2: OVERRIDDEN (--force with --force-reason; "
            "recorded in data/.force_override_log.json)"
        )
        return False

    return True
