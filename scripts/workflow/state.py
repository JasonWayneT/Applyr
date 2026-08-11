"""Authoritative workflow_state.json load/save (used only via receipts/runner)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from workflow import RECEIPTS_DIR_NAME, WORKFLOW_STATE_NAME
from workflow.transitions import new_state


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_path(folder: str) -> str:
    return os.path.join(folder, WORKFLOW_STATE_NAME)


def receipts_dir(folder: str) -> str:
    return os.path.join(folder, RECEIPTS_DIR_NAME)


def load_state(folder: str) -> dict[str, Any] | None:
    path = state_path(folder)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{WORKFLOW_STATE_NAME} is not a JSON object")
    return data


def init_state(folder: str, mode: str = "production") -> dict[str, Any]:
    slug = os.path.basename(folder.rstrip("/\\"))
    state = new_state(slug, mode=mode)
    now = utc_now()
    state["created_at"] = now
    state["updated_at"] = now
    return state


def stamp_updated(state: dict[str, Any]) -> dict[str, Any]:
    state = dict(state)
    state["updated_at"] = utc_now()
    if not state.get("created_at"):
        state["created_at"] = state["updated_at"]
    return state
