#!/usr/bin/env python3
"""Durable Stage 0 run, judgment, and local spool helpers (CR-108)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _ROOT / "data" / "jobagent.sqlite"
_MIGRATIONS = (
    _ROOT / "server" / "migrations" / "018_add_review_center.sql",
    _ROOT / "server" / "migrations" / "019_add_stage0_checkpoints.sql",
    _ROOT / "server" / "migrations" / "020_add_review_answer_history.sql",
    _ROOT / "server" / "migrations" / "021_add_evidence_promotion_proposals.sql",
)
_RUN_STATUSES = {"REQUESTED", "RUNNING", "WAITING_FOR_INPUT", "COMPLETE", "FAILED"}
CHECKPOINT_BOUNDARIES = (
    "before_request_spool",
    "after_request_spool",
    "after_run_requested",
    "before_provider_call",
    "after_response_spool",
    "after_judgment_commit",
    "after_pending_confirmation_commit",
    "after_run_complete",
)
_failure_injector: Callable[[str], None] | None = None


def set_failure_injector(injector: Callable[[str], None] | None) -> None:
    """Set the test-only callback used to inject failures at named boundaries."""
    global _failure_injector
    _failure_injector = injector


def checkpoint_boundary(name: str) -> None:
    """Invoke the optional test failure injector at a checkpoint boundary."""
    if name not in CHECKPOINT_BOUNDARIES:
        raise ValueError(f"unknown Stage 0 checkpoint boundary: {name}")
    if _failure_injector is not None:
        _failure_injector(name)


def _utc_now() -> str:
    """Return the current UTC timestamp for checkpoint records."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _digest(value: str) -> str:
    """Return a stable SHA-256 digest for canonical text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_run_key(
    opportunity_key: str,
    jd_hash: str,
    prompt_version: str,
    provider_policy_hash: str,
    evidence_index_hash: str,
) -> str:
    """Build a stable Stage 0 run key from all inputs that affect judgments."""
    canonical = json.dumps(
        {
            "opportunity_key": opportunity_key,
            "jd_hash": jd_hash,
            "prompt_version": prompt_version,
            "provider_policy_hash": provider_policy_hash,
            "evidence_index_hash": evidence_index_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"run:{_digest(canonical)}"


def make_item_key(bucket: str, item_text: str, ordinal: int) -> str:
    """Build a stable item key that distinguishes repeated lines in one bucket."""
    return f"{_safe_part(bucket)}:{ordinal}:{_digest(item_text.strip())[:16]}"


def start_run(
    db_path: str | Path | None,
    *,
    run_key: str,
    opportunity_key: str,
    jd_hash: str,
    prompt_version: str,
    provider_policy_hash: str,
    evidence_index_hash: str,
    request_hash: str | None = None,
    request_spool_path: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert a run checkpoint once and return its durable row."""
    connection = _connect(db_path)
    try:
        now = _utc_now()
        with connection:
            connection.execute(
                """
                INSERT INTO stage0_runs (
                  run_key, opportunity_key, jd_hash, prompt_version,
                  provider_policy_hash, evidence_index_hash, status,
                  request_hash, request_spool_path, metadata_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'REQUESTED', ?, ?, ?, ?, ?)
                ON CONFLICT(run_key) DO NOTHING
                """,
                (
                    run_key,
                    opportunity_key,
                    jd_hash,
                    prompt_version,
                    provider_policy_hash,
                    evidence_index_hash,
                    request_hash,
                    request_spool_path,
                    json.dumps(metadata, ensure_ascii=False) if metadata else None,
                    now,
                    now,
                ),
            )
        row = connection.execute(
            "SELECT * FROM stage0_runs WHERE run_key = ?", (run_key,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Stage 0 run checkpoint was not created: {run_key}")
        return dict(row)
    finally:
        connection.close()


def mark_run_status(
    db_path: str | Path | None,
    run_key: str,
    status: str,
    *,
    response_spool_path: str | None = None,
    response_hash: str | None = None,
) -> None:
    """Update a run checkpoint status and optional response metadata."""
    if status not in _RUN_STATUSES:
        raise ValueError(f"invalid Stage 0 run status: {status}")
    connection = _connect(db_path)
    try:
        completed_at = _utc_now() if status == "COMPLETE" else None
        with connection:
            updated = connection.execute(
                """
                UPDATE stage0_runs
                SET status = ?, response_spool_path = COALESCE(?, response_spool_path),
                    response_hash = COALESCE(?, response_hash), updated_at = ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE run_key = ?
                """,
                (status, response_spool_path, response_hash, _utc_now(), completed_at, run_key),
            ).rowcount
        if updated != 1:
            raise KeyError(f"Stage 0 run not found: {run_key}")
    finally:
        connection.close()


def update_run_metadata(
    db_path: str | Path | None,
    run_key: str,
    metadata: dict[str, Any],
) -> None:
    """Merge aggregate run telemetry into one Stage 0 checkpoint row."""
    connection = _connect(db_path)
    try:
        row = connection.execute(
            "SELECT metadata_json FROM stage0_runs WHERE run_key = ?",
            (run_key,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Stage 0 run not found: {run_key}")
        existing: dict[str, Any] = {}
        if row["metadata_json"]:
            try:
                parsed = json.loads(row["metadata_json"])
                if isinstance(parsed, dict):
                    existing = parsed
            except json.JSONDecodeError:
                pass
        existing.update(metadata)
        with connection:
            connection.execute(
                """
                UPDATE stage0_runs
                SET metadata_json = ?, updated_at = ?
                WHERE run_key = ?
                """,
                (json.dumps(existing, ensure_ascii=False, sort_keys=True), _utc_now(), run_key),
            )
    finally:
        connection.close()


def complete_judgment(
    db_path: str | Path | None,
    *,
    judgment_key: str,
    run_key: str,
    opportunity_key: str,
    item_key: str,
    item_text: str,
    bucket: str,
    request_hash: str,
    content_hash: str,
    evidence_index_hash: str,
    judgment: dict[str, Any],
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Persist one validated completed item judgment idempotently."""
    connection = _connect(db_path)
    try:
        now = _utc_now()
        with connection:
            connection.execute(
                """
                INSERT INTO stage0_judgments (
                  judgment_key, run_key, opportunity_key, item_key, item_text,
                  bucket, status, request_hash, content_hash,
                  evidence_index_hash, provider, model, judgment_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'COMPLETE', ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(judgment_key) DO UPDATE SET
                  status = excluded.status,
                  provider = excluded.provider,
                  model = excluded.model,
                  judgment_json = excluded.judgment_json,
                  updated_at = excluded.updated_at
                """,
                (
                    judgment_key,
                    run_key,
                    opportunity_key,
                    item_key,
                    item_text,
                    bucket,
                    request_hash,
                    content_hash,
                    evidence_index_hash,
                    provider,
                    model,
                    json.dumps(judgment, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )
    finally:
        connection.close()


def get_completed_judgment(
    db_path: str | Path | None,
    *,
    run_key: str,
    item_key: str,
    request_hash: str,
    content_hash: str,
    evidence_index_hash: str,
) -> dict[str, Any] | None:
    """Return a completed judgment only when all reuse hashes still match."""
    connection = _connect(db_path)
    try:
        row = connection.execute(
            """
            SELECT *
            FROM stage0_judgments
            WHERE run_key = ? AND item_key = ? AND request_hash = ?
              AND content_hash = ? AND evidence_index_hash = ?
              AND status = 'COMPLETE'
            """,
            (run_key, item_key, request_hash, content_hash, evidence_index_hash),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            result["judgment"] = json.loads(result["judgment_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        return result
    finally:
        connection.close()


def write_spool(
    folder: Path,
    kind: str,
    run_key: str,
    payload: dict[str, Any],
) -> tuple[str, str]:
    """Atomically write a hash-addressed local request or response spool."""
    spool_dir = folder / ".stage0_spool"
    spool_dir.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    digest = _digest(serialized)
    safe_kind = _safe_part(kind)
    safe_run = _safe_part(run_key)
    target = spool_dir / f"{safe_run}.{safe_kind}.{digest[:16]}.json"
    fd, temp_path = tempfile.mkstemp(prefix=".stage0_", suffix=".json", dir=spool_dir)
    try:
        # Keep the serialized bytes stable across Windows and POSIX. Text-mode
        # newline translation would make the stored SHA-256 differ from the
        # bytes that were actually spooled on Windows.
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return str(target), digest


def _safe_part(value: str) -> str:
    """Restrict a key segment to filesystem-safe stable characters."""
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(value)).strip("_") or "unknown"


def _connect(db_path: str | Path | None) -> sqlite3.Connection:
    """Open the shared SQLite database and apply the additive CR-108 tables."""
    path = Path(db_path) if db_path is not None else _DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30.0)
    connection.row_factory = sqlite3.Row
    for migration in _MIGRATIONS:
        connection.executescript(migration.read_text(encoding="utf-8"))
    return connection
