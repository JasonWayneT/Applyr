"""Pure transition helpers for workflow_state (no I/O)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def new_state(slug: str, mode: str = "production") -> dict[str, Any]:
    """Return a fresh workflow_state dict."""
    stages = {
        name: {"status": "LOCKED" if name != "stage0" else "READY", "receipt_id": None, "integrity": "CLEAN"}
        for name in ("stage0", "stage1", "stage2", "stage3")
    }
    return {
        "schema_version": 1,
        "slug": slug,
        "mode": mode,
        "status": "NOT_STARTED",
        "active_stage": "stage0",
        "created_at": None,
        "updated_at": None,
        "stages": stages,
        "legacy": False,
    }


def apply_stage_update(
    state: dict[str, Any],
    *,
    stage: str,
    stage_status: str,
    workflow_status: str,
    receipt_id: str | None,
    integrity: str = "CLEAN",
    active_stage: str | None = None,
) -> dict[str, Any]:
    """Return a new state dict with one stage updated."""
    out = deepcopy(state)
    if stage not in out["stages"]:
        raise KeyError(stage)
    out["stages"][stage] = {
        "status": stage_status,
        "receipt_id": receipt_id,
        "integrity": integrity,
    }
    out["status"] = workflow_status
    if active_stage is not None:
        out["active_stage"] = active_stage
    return out
