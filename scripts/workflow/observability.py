"""Observability event log — append-only per-opportunity record of what each stage attempt did.

Generalizes the pattern author_from_packet.py's stage1_first_draft/verify_history.json already
proved out for Stage 1: one JSON object per line, written once, never rewritten in place, so a
replay's history survives across multiple --resume calls and even across a second full replay of
the same opportunity. Deliberately kept separate from stage_receipts/ (proof-of-completion,
hash-chained, overwritten on retry by design) rather than overloading that contract — see
docs/spec/08-implementation/OBSERVABILITY-DESIGN-2026-08-30-stage0-3-replay-reporting.md §4.2 for
the reasoning.

run_id groups the events from one execution attempt of one stage function (not one whole
run_submission.py CLI invocation — Stage 1's WAITING_FOR_LLM gap means a single "opportunity run"
routinely spans multiple separate CLI invocations anyway, so a per-stage-attempt id is the more
useful grouping key here, not a coarser per-process one).
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any


def new_run_id() -> str:
    """A fresh id for one stage-execution attempt. Sortable by time, unique enough for a
    single-operator local tool -- collision risk is not a real concern at this scale."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{ts}_{secrets.token_hex(2)}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def events_path(folder: str) -> str:
    return os.path.join(folder, "observability", "run_events.jsonl")


def append_event(folder: str, run_id: str, stage: str, event: str, **fields: Any) -> None:
    """Appends one event object as a single JSON line.

    Never reads-then-rewrites the file -- a pure append, so two concurrent processes appending to
    the same file (unlikely for a single-operator tool, but cheap to get right) can't clobber each
    other's lines the way a read-modify-write JSON file would.
    """
    path = events_path(folder)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "stage": stage,
        "event": event,
        "timestamp": utc_now_iso(),
    }
    record.update(fields)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_events(folder: str) -> list[dict[str, Any]]:
    """Reads every recorded event for a submission. Returns [] when no run_events.jsonl exists --
    submissions replayed before this instrumentation existed have none, by design; callers must
    degrade gracefully rather than treat an empty list as an error."""
    path = events_path(folder)
    if not os.path.exists(path):
        return []
    events: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                # A partially-written last line (process killed mid-write) must not make every
                # earlier, valid line unreadable.
                continue
    return events
