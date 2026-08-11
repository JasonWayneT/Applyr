"""SOLE writer of workflow_state.json and stage_receipts/*.json (CR-076).

Workers and other scripts must not import write helpers to mint production
authority — call run_submission / workflow.runner instead.
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Mapping

from workflow.invalidate import sha256_file, sha256_hex_bytes
from workflow.state import receipts_dir, stamp_updated, state_path, utc_now

ISSUED_BY = "scripts/run_submission.py"


def _atomic_write_json(path: str, data: dict[str, Any]) -> None:
    import time

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    last_err: Exception | None = None
    for attempt in range(8):
        fd, tmp = tempfile.mkstemp(prefix=".wf_", suffix=".json", dir=parent or None)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            return
        except PermissionError as exc:
            last_err = exc
            try:
                os.unlink(tmp)
            except OSError:
                pass
            time.sleep(0.05 * (attempt + 1))
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    assert last_err is not None
    raise last_err


def receipt_path(folder: str, stage: str) -> str:
    return os.path.join(receipts_dir(folder), f"{stage}.json")


def build_receipt(
    *,
    stage: str,
    status: str,
    mode: str,
    input_hashes: Mapping[str, str],
    output_hashes: Mapping[str, str],
    result: dict[str, Any] | None = None,
    checks: dict[str, Any] | None = None,
    prior_receipt_id: str | None = None,
    integrity: str = "CLEAN",
    override: dict[str, Any] | None = None,
    issued_at: str | None = None,
) -> dict[str, Any]:
    """Build a receipt dict (does not write). receipt_id = sha256 of canonical body."""
    body = {
        "stage": stage,
        "status": status,
        "integrity": integrity,
        "issued_by": ISSUED_BY,
        "issued_at": issued_at or utc_now(),
        "mode": mode,
        "prior_receipt_id": prior_receipt_id,
        "input_hashes": dict(input_hashes),
        "output_hashes": dict(output_hashes),
        "result": result or {},
        "checks": checks or {},
        "override": override,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    receipt_id = f"{stage}:{sha256_hex_bytes(canonical.encode('utf-8'))}"
    out = dict(body)
    out["receipt_id"] = receipt_id
    return out


def write_receipt(folder: str, receipt: dict[str, Any]) -> str:
    """Persist a stage receipt. Returns absolute path written."""
    stage = receipt["stage"]
    path = receipt_path(folder, stage)
    _atomic_write_json(path, receipt)
    return path


def write_state(folder: str, state: dict[str, Any]) -> str:
    """Persist workflow_state.json. Returns absolute path written."""
    state = stamp_updated(state)
    path = state_path(folder)
    _atomic_write_json(path, state)
    return path


def commit_stage(
    folder: str,
    state: dict[str, Any],
    receipt: dict[str, Any],
    *,
    workflow_status: str,
    active_stage: str | None,
) -> dict[str, Any]:
    """Write receipt first, then state (crash-resume: adopt receipt if state lags)."""
    from workflow.transitions import apply_stage_update

    write_receipt(folder, receipt)
    new_state = apply_stage_update(
        state,
        stage=receipt["stage"],
        stage_status=receipt["status"],
        workflow_status=workflow_status,
        receipt_id=receipt["receipt_id"],
        integrity=receipt.get("integrity") or "CLEAN",
        active_stage=active_stage,
    )
    write_state(folder, new_state)
    return new_state


def file_hash_map(folder: str, relative_paths: list[str]) -> dict[str, str]:
    """Build {rel: sha256} for existing files; skip missing."""
    out: dict[str, str] = {}
    for rel in relative_paths:
        digest = sha256_file(os.path.join(folder, rel))
        if digest is not None:
            out[rel] = digest
    return out


def load_receipt(folder: str, stage: str) -> dict[str, Any] | None:
    path = receipt_path(folder, stage)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{stage} receipt is not a JSON object")
    return data
