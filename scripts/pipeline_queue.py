#!/usr/bin/env python3
"""CR-119 CSV drop queue — pipeline_queue / ingest ledger / quarantine.

# Implements FR-340 / FR-341 / FR-342 / FR-343 / DATA-006 / ADR-001

Queue lifecycle lives here. workflow_state.json + stage_receipts/ remain stage
authority (CR-119 Decision 2). Status on pipeline_queue is a mirror.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
DEFAULT_DB = _REPO_ROOT / "data" / "jobagent.sqlite"

# Semantically identical to server/migrations/025_add_pipeline_queue.sql
# plus 026_add_pipeline_queue_paused_at.sql (paused_at)
# plus 027_add_pipeline_queue_paused_reason.sql (paused_reason)
# plus 028_add_pipeline_queue_requeue_audit.sql (requeued_by / requeue_reason / requeued_at).
# Story 1.3 anti-drift test dumps sqlite_master from both copies.
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_queue (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,

  slug                 TEXT NOT NULL UNIQUE,
  company              TEXT NOT NULL,
  title                TEXT NOT NULL,
  url                  TEXT,
  url_key              TEXT,
  posting_key          TEXT NOT NULL,

  networking_contacts_raw TEXT,

  source_sha256        TEXT,
  source_line          INTEGER,

  folder_root          TEXT NOT NULL,

  status               TEXT NOT NULL CHECK(
                         status IN ('queued', 'leased', 'in_progress', 'paused', 'done')
                       ),

  locked_by            TEXT,
  lease_expires_at     TEXT,
  fencing_token        INTEGER NOT NULL DEFAULT 0,

  queued_at            TEXT NOT NULL,
  claimed_at           TEXT,
  started_at           TEXT,
  updated_at           TEXT,

  last_workflow_status TEXT,
  last_stage           TEXT,
  paused_at            TEXT,
  paused_reason        TEXT,
  requeued_by          TEXT,
  requeue_reason       TEXT,
  requeued_at          TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_queue_url_key
  ON pipeline_queue(url_key) WHERE url_key IS NOT NULL AND url_key != '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_queue_posting_key
  ON pipeline_queue(posting_key) WHERE url_key IS NULL OR url_key = '';

CREATE TABLE IF NOT EXISTS csv_ingest_ledger (
  sha256           TEXT PRIMARY KEY,
  filename         TEXT NOT NULL,
  ingested_at      TEXT NOT NULL,
  row_count        INTEGER NOT NULL DEFAULT 0,
  quarantine_count INTEGER NOT NULL DEFAULT 0,
  archive_path     TEXT,
  status           TEXT NOT NULL CHECK(status IN ('ingested', 'file_quarantined'))
);

CREATE TABLE IF NOT EXISTS csv_quarantine (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  scope             TEXT NOT NULL CHECK(scope IN ('file', 'row')),
  source_file       TEXT NOT NULL,
  line_number       INTEGER,
  raw_payload       TEXT,
  error_code        TEXT NOT NULL,
  quarantine_reason TEXT NOT NULL
);
"""


def _ensure_paused_at_column(conn: sqlite3.Connection) -> None:
    """Add paused_at on DBs that already ran 025 without 026 (FR-346)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
    if "paused_at" not in cols:
        conn.execute("ALTER TABLE pipeline_queue ADD COLUMN paused_at TEXT")
    conn.execute(
        """
        UPDATE pipeline_queue
           SET paused_at = updated_at
         WHERE status = 'paused'
           AND paused_at IS NULL
           AND updated_at IS NOT NULL
        """
    )


def _ensure_paused_reason_column(conn: sqlite3.Connection) -> None:
    """Add paused_reason on DBs that already ran 025/026 without 027."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
    if "paused_reason" not in cols:
        conn.execute("ALTER TABLE pipeline_queue ADD COLUMN paused_reason TEXT")


def _ensure_requeue_columns(conn: sqlite3.Connection) -> None:
    """Add manual-requeue audit columns on DBs that ran 025-027 without 028."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_queue)")}
    for name in ("requeued_by", "requeue_reason", "requeued_at"):
        if name not in cols:
            conn.execute(f"ALTER TABLE pipeline_queue ADD COLUMN {name} TEXT")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the three CR-119 tables if missing. Idempotent."""
    conn.executescript(_SCHEMA_SQL)
    _ensure_paused_at_column(conn)
    _ensure_paused_reason_column(conn)
    _ensure_requeue_columns(conn)
    conn.commit()


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open the jobs DB and ensure the queue tables exist."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    ensure_schema(conn)
    return conn


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_dict(row: sqlite3.Row | tuple | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def record_quarantine(
    conn: sqlite3.Connection,
    *,
    scope: str,
    source_file: str,
    error_code: str,
    quarantine_reason: str,
    line_number: int | None = None,
    raw_payload: str | None = None,
) -> None:
    if scope not in ("file", "row"):
        raise ValueError(f"invalid quarantine scope: {scope}")
    conn.execute(
        """
        INSERT INTO csv_quarantine
          (scope, source_file, line_number, raw_payload, error_code, quarantine_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (scope, source_file, line_number, raw_payload, error_code, quarantine_reason),
    )
    conn.commit()


def lookup_file(conn: sqlite3.Connection, sha256: str) -> dict[str, Any] | None:
    return _row_dict(
        conn.execute(
            "SELECT * FROM csv_ingest_ledger WHERE sha256 = ?",
            (sha256,),
        ).fetchone()
    )


def record_file(
    conn: sqlite3.Connection,
    *,
    sha256: str,
    filename: str,
    row_count: int,
    quarantine_count: int,
    archive_path: str | None,
    status: str,
) -> dict[str, Any]:
    existing = lookup_file(conn, sha256)
    if existing:
        return existing
    conn.execute(
        """
        INSERT INTO csv_ingest_ledger
          (sha256, filename, ingested_at, row_count, quarantine_count, archive_path, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (sha256, filename, utc_now(), row_count, quarantine_count, archive_path, status),
    )
    conn.commit()
    stored = lookup_file(conn, sha256)
    if stored is None:
        raise RuntimeError("csv_ingest_ledger insert did not persist")
    return stored


def get_row(conn: sqlite3.Connection, slug: str) -> dict[str, Any] | None:
    return _row_dict(
        conn.execute(
            "SELECT * FROM pipeline_queue WHERE slug = ?",
            (slug,),
        ).fetchone()
    )


def upsert_queued(
    conn: sqlite3.Connection,
    *,
    slug: str,
    company: str,
    title: str,
    url: str | None,
    url_key: str | None,
    posting_key: str,
    networking_contacts_raw: str | None,
    source_sha256: str | None,
    source_line: int | None,
    folder_root: str,
) -> dict[str, Any]:
    existing = get_row(conn, slug)
    if existing:
        return existing
    now = utc_now()
    conn.execute(
        """
        INSERT INTO pipeline_queue (
          slug, company, title, url, url_key, posting_key,
          networking_contacts_raw, source_sha256, source_line, folder_root,
          status, fencing_token, queued_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?, ?)
        """,
        (
            slug,
            company,
            title,
            url,
            url_key,
            posting_key,
            networking_contacts_raw,
            source_sha256,
            source_line,
            folder_root,
            now,
            now,
        ),
    )
    conn.commit()
    stored = get_row(conn, slug)
    if stored is None:
        raise RuntimeError("pipeline_queue insert did not persist")
    return stored


LEGAL_TRANSITIONS = frozenset(
    {
        ("queued", "leased"),
        ("leased", "in_progress"),
        ("in_progress", "paused"),
        ("paused", "queued"),
        ("paused", "done"),
        ("in_progress", "done"),
        ("leased", "queued"),
        # Expiry reclaim: an expired in_progress row becomes claimable (Story 3.3).
        ("in_progress", "queued"),
        # CR-123 FR-363: already-handled close. Supersedes CR-119 Story 3.1
        # for these two pairs only. Still five statuses.
        ("queued", "done"),
        ("leased", "done"),
    }
)

MAX_PACK_SIZE = 10
DEFAULT_PACK_SIZE = 8
DEFAULT_LEASE_MINUTES = 20
CONVERSION_RISK_OVERRIDE_NAME = "conversion_risk_apply_anyway.json"
PAUSE_KIND_CONVERSION_RISK = "conversion_risk"
PAUSED_REASON_CONVERSION_RISK = "conversion_risk"
PAUSED_REASON_READY_TO_FINALIZE = "ready_to_finalize"
MIRROR_READY_TO_FINALIZE = "READY_TO_FINALIZE"
STAGE1_BUDGET_RETRY_NAME = "stage1_budget_retry.json"


def mark_done(
    slug: str,
    *,
    conn: sqlite3.Connection,
    last_workflow_status: str = "COMPLETE",
    last_stage: str | None = "stage3",
) -> dict[str, Any] | None:
    """Move a closable queue row to done. Implements FR-363.

    Accepts queued, paused, leased, and in_progress. done is a no-op.
    Still calls transition() with the row's locked_by + fencing_token
    (empty worker + unlocked fence when locked_by is NULL).
    """
    row = get_row(conn, slug)
    if row is None or row["status"] == "done":
        return row
    if row["status"] not in ("queued", "paused", "leased", "in_progress"):
        return row
    return transition(
        slug,
        "done",
        worker=row["locked_by"] or "",
        token=int(row["fencing_token"] or 0),
        conn=conn,
        last_workflow_status=last_workflow_status,
        last_stage=last_stage or row.get("last_stage"),
    )


DATA_ROOT = _REPO_ROOT / "data"


class IllegalTransition(ValueError):
    """Status pair is not in the CR-119 transition table."""


class FenceRejected(RuntimeError):
    """Fenced UPDATE matched zero rows; SQLite state is unchanged."""


class PackSizeError(ValueError):
    """--size outside 1..10."""


class RequeueRefused(ValueError):
    """Manual requeue is not allowed for this row's current state."""


def list_rows(
    conn: sqlite3.Connection,
    status: str | None = None,
) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            "SELECT * FROM pipeline_queue WHERE status = ? ORDER BY queued_at, id",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM pipeline_queue ORDER BY queued_at, id"
        ).fetchall()
    return [dict(row) for row in rows]


def _lease_expiry(minutes: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(minutes=minutes)
    ).replace(microsecond=0).isoformat()


def _commit(conn: sqlite3.Connection, commit: bool) -> None:
    if commit:
        conn.commit()


def transition(
    slug: str,
    to_status: str,
    *,
    worker: str,
    token: int,
    conn: sqlite3.Connection,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    last_workflow_status: str | None = None,
    last_stage: str | None = None,
    folder_root: str | None = None,
    new_slug: str | None = None,
    paused_reason: str | None = None,
    requeued_by: str | None = None,
    requeue_reason: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Sole writer of pipeline_queue.status. Fenced; rowcount must be 1."""
    row = get_row(conn, slug)
    if row is None:
        raise FenceRejected(f"no pipeline_queue row for {slug}")
    from_status = row["status"]
    if (from_status, to_status) not in LEGAL_TRANSITIONS:
        raise IllegalTransition(f"{from_status} -> {to_status} is not a legal transition")
    now = utc_now()
    locked_by = row["locked_by"]
    if locked_by:
        fence_sql = "slug = ? AND fencing_token = ? AND locked_by = ?"
        fence_args: tuple[Any, ...] = (slug, token, worker)
    else:
        fence_sql = "slug = ? AND fencing_token = ? AND locked_by IS NULL"
        fence_args = (slug, token)

    sets = ["status = ?", "updated_at = ?"]
    args: list[Any] = [to_status, now]
    if to_status == "leased":
        sets.extend(
            [
                "locked_by = ?",
                "lease_expires_at = ?",
                "fencing_token = fencing_token + 1",
                "claimed_at = ?",
            ]
        )
        args.extend([worker, _lease_expiry(lease_minutes), now])
    elif to_status == "in_progress":
        sets.append("started_at = ?")
        args.append(now)
    elif to_status in ("queued", "paused", "done") and from_status != "queued":
        if to_status in ("queued", "paused", "done"):
            sets.extend(["locked_by = NULL", "lease_expires_at = NULL"])
        if to_status == "paused":
            sets.append("paused_at = ?")
            args.append(now)
            sets.append("paused_reason = ?")
            args.append(paused_reason)
        elif to_status in ("queued", "done"):
            sets.append("paused_reason = NULL")
    if requeued_by is not None:
        sets.append("requeued_by = ?")
        args.append(requeued_by)
    if requeue_reason is not None:
        sets.append("requeue_reason = ?")
        args.append(requeue_reason)
        sets.append("requeued_at = ?")
        args.append(now)
    if last_workflow_status is not None:
        sets.append("last_workflow_status = ?")
        args.append(last_workflow_status)
    if last_stage is not None:
        sets.append("last_stage = ?")
        args.append(last_stage)
    if folder_root is not None:
        sets.append("folder_root = ?")
        args.append(folder_root)
    if new_slug is not None and new_slug != slug:
        sets.append("slug = ?")
        args.append(new_slug)

    sql = f"UPDATE pipeline_queue SET {', '.join(sets)} WHERE {fence_sql}"
    cur = conn.execute(sql, (*args, *fence_args))
    if cur.rowcount != 1:
        raise FenceRejected(f"fenced update rejected for {slug}")
    _commit(conn, commit)
    result_slug = new_slug or slug
    stored = get_row(conn, result_slug)
    if stored is None:
        raise RuntimeError("transition did not persist")
    return stored


def requeue_paused_for_repair(
    folder: Path,
    *,
    conn: sqlite3.Connection | None = None,
    data_root: Path | None = None,
) -> str | None:
    """Move a paused FAILED queue row back to queued. No auto-promote.

    Only touches rows whose folder is under pending_review/ or submissions/.
    Temp test folders are ignored. Missing rows are a no-op.
    """
    folder = folder.resolve()
    root = (data_root or DATA_ROOT).resolve()
    under_queue_tree = False
    for name in ("pending_review", "submissions"):
        try:
            folder.relative_to(root / name)
            under_queue_tree = True
            break
        except ValueError:
            continue
    if not under_queue_tree:
        return None
    slug = folder.name
    close_after = False
    if conn is None:
        conn = connect()
        close_after = True
    try:
        row = get_row(conn, slug)
        if not row or row["status"] != "paused":
            return None
        stored = transition(
            slug,
            "queued",
            worker=row["locked_by"] or "",
            token=int(row["fencing_token"] or 0),
            conn=conn,
            last_workflow_status=row.get("last_workflow_status") or "FAILED",
            last_stage=row.get("last_stage") or "stage1",
        )
        return stored["status"]
    except (IllegalTransition, FenceRejected):
        return None
    finally:
        if close_after:
            conn.close()


def requeue_paused(
    slug: str,
    *,
    reason: str,
    worker: str = "manual",
    conn: sqlite3.Connection | None = None,
    db_path: Path | str | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """Move an eligible paused row back to queued through transition().

    Allowed: paused FAILED, paused subscription_review evidence, paused
    requirement_extraction_review whose queue is entirely no_provider, or
    paused review_center with zero open questions.
    Refused: leased, in_progress, done, ready_to_finalize, real extraction
    reviews, and review_center with open cards.
    """
    note = (reason or "").strip()
    who = (worker or "manual").strip() or "manual"
    if not note:
        raise RequeueRefused("refused: reason is required")
    close_after = False
    if conn is None:
        conn = connect(db_path)
        close_after = True
    try:
        row = get_row(conn, slug)
        if row is None:
            raise RequeueRefused(f"refused: no pipeline_queue row for {slug}")
        status = row["status"]
        if status != "paused":
            raise RequeueRefused(f"refused: status={status}")
        if (
            row.get("paused_reason") == PAUSED_REASON_READY_TO_FINALIZE
            or row.get("last_workflow_status") == MIRROR_READY_TO_FINALIZE
        ):
            raise RequeueRefused("refused: ready_to_finalize")
        failed = row.get("last_workflow_status") == "FAILED"
        folder = _resolve_row_folder(row, (data_root or DATA_ROOT).resolve())
        kind = _pause_kind(folder) if folder is not None else None
        if kind == PAUSE_KIND_CONVERSION_RISK:
            if note.strip().lower() != "apply_anyway":
                raise RequeueRefused(
                    "refused: conversion_risk requires reason apply_anyway"
                )
            (folder / CONVERSION_RISK_OVERRIDE_NAME).write_text(
                json.dumps(
                    {"reason": "apply_anyway", "requeued_by": who, "at": utc_now()},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        elif not failed and not _requeue_pause_allowed(row, folder, conn):
            raise RequeueRefused("refused: not an eligible pause")
        try:
            return transition(
                slug,
                "queued",
                worker=row["locked_by"] or "",
                token=int(row["fencing_token"] or 0),
                conn=conn,
                last_workflow_status=row.get("last_workflow_status"),
                last_stage=row.get("last_stage"),
                requeued_by=who,
                requeue_reason=note,
            )
        except FenceRejected as err:
            raise RequeueRefused(f"refused: fence rejected for {slug}") from err
    finally:
        if close_after:
            conn.close()


def _resolve_row_folder(row: dict[str, Any], data_root: Path) -> Path | None:
    slug = row["slug"]
    roots = {
        "pending_review": data_root / "pending_review",
        "submissions": data_root / "submissions",
        "archive/skipped": data_root / "archive" / "skipped",
    }
    preferred = roots.get(row.get("folder_root") or "")
    if preferred is not None and (preferred / slug).exists():
        return preferred / slug
    for root in roots.values():
        candidate = root / slug
        if candidate.exists():
            return candidate
    return None


def _workflow_status(folder: Path) -> str | None:
    path = folder / "workflow_state.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    status = payload.get("status")
    return status if isinstance(status, str) else None


def _parse_paused_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _dispositions_mtime(folder: Path) -> datetime | None:
    """Return dispositions.json's own recorded write time, not filesystem mtime.

    Found 2026-09-20/21 root-causing FIXQUEUE 2026-09-18 item #5 (crio/lexipol
    repeatedly re-promoted with nothing actually changed): this used to read
    the file's OS mtime (full sub-second precision) and compare it against
    `paused_at` from the DB, which `utc_now()` truncates to whole seconds
    (`.replace(microsecond=0)`). Any write to dispositions.json that happens
    in the *same* wall-clock second as the pause -- which is the normal case,
    since the file is written moments before the row is marked paused -- has
    a sub-second remainder that always compares as "later than" the
    truncated `paused_at`, even though nothing changed since the pause.
    Reading the file's own `updated_at` field instead (written by
    workflow/reviews.py's `_write_dispositions` via the same whole-second
    `utc_now()` format used for `paused_at`) makes both sides of the
    comparison the same precision, so only a genuinely later write promotes
    the row. Also avoids false promotion from filesystem-level mtime changes
    that aren't a real edit (git checkout, file copy, backup/sync tooling).
    """
    path = folder / "reviews" / "dispositions.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return _parse_paused_at(payload.get("updated_at"))


def _file_mtime(path: Path) -> datetime | None:
    if not path.is_file():
        return None
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def _newer_than_paused(path: Path, paused_at: datetime | None) -> bool:
    if paused_at is None:
        return False
    stamp = _file_mtime(path)
    return stamp is not None and stamp > paused_at


def _pause_kind(folder: Path) -> str | None:
    receipt = folder / "stage_receipts" / "stage0.json"
    if not receipt.is_file():
        return None
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    kind = ((payload or {}).get("result") or {}).get("pause_kind")
    return kind if isinstance(kind, str) and kind.strip() else None


def _stage0_pause_result(folder: Path) -> dict[str, Any] | None:
    """Return the Stage 0 receipt result object, or None if unreadable."""
    receipt = folder / "stage_receipts" / "stage0.json"
    if not receipt.is_file():
        return None
    try:
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    result = (payload or {}).get("result")
    return result if isinstance(result, dict) else None


def _extraction_review_is_no_provider(folder: Path) -> bool:
    """True when every extraction-review queue item failed for no_provider.

    Live miss 2026-09-21: adapter-off packs paused outschool/omnissa/optum/
    origami_risk for human bucket review. Filling those templates is the
    wrong recovery once Agy is on. Implements FR-346.
    """
    result = _stage0_pause_result(folder)
    if not result or result.get("pause_kind") != "requirement_extraction_review":
        return False
    queue = result.get("queue") or []
    if not isinstance(queue, list) or not queue:
        return False
    return all(
        isinstance(item, dict)
        and str(item.get("extraction_reason") or "") == "no_provider"
        for item in queue
    )


def _review_center_open_count(
    conn: sqlite3.Connection | None, slug: str
) -> int | None:
    """Return open blocking Review Center count, or None if unread.

    CR-122 / FR-360: only ``hard_gate_review`` holds the queue. Open
    ``skill_presence`` cards are a later correction inbox.
    """
    if conn is None or not slug:
        return None
    try:
        open_n = conn.execute(
            """
            SELECT COUNT(*) FROM pending_skill_confirmations
            WHERE opportunity_key = ? AND status = 'open'
              AND question_type = 'hard_gate_review'
            """,
            (slug,),
        ).fetchone()[0]
    except sqlite3.OperationalError:
        return None
    return int(open_n)


def _requeue_pause_allowed(
    row: dict[str, Any],
    folder: Path | None,
    conn: sqlite3.Connection | None,
) -> bool:
    """True when a paused row may go back to queued through requeue_paused."""
    if row.get("last_workflow_status") == "FAILED":
        return True
    if folder is None:
        return False
    kind = _pause_kind(folder)
    if kind == "subscription_review":
        return True
    if kind == "requirement_extraction_review" and _extraction_review_is_no_provider(
        folder
    ):
        return True
    if kind == "review_center":
        return _review_center_open_count(conn, str(row.get("slug") or "")) == 0
    if kind == PAUSE_KIND_CONVERSION_RISK:
        return True
    return False


def _review_center_should_promote(
    conn: sqlite3.Connection | None,
    slug: str,
    paused_at: datetime | None,
) -> bool:
    """Promote when this slug has no open hard-gate Review Center questions.

    CR-122 / AC-469: skill_presence may stay open. Missing table stays paused.
    paused_at is unused; kept so callers do not change.
    """
    del paused_at
    if conn is None or not slug:
        return False
    open_n = _review_center_open_count(conn, slug)
    if open_n is None:
        return False
    return open_n == 0


def _waiting_for_input_should_promote(
    folder: Path,
    row: dict[str, Any] | None,
    conn: sqlite3.Connection | None,
) -> bool:
    paused_at = _parse_paused_at((row or {}).get("paused_at"))
    kind = _pause_kind(folder)
    if kind == "subscription_review":
        return _newer_than_paused(folder / "stage0_cascade_import.json", paused_at)
    if kind == "requirement_extraction_review":
        return _newer_than_paused(
            folder / "stage0_requirement_extraction_review.json", paused_at
        )
    if kind == "cost_authorization":
        return False
    if kind == "conversion_risk":
        return _newer_than_paused(folder / CONVERSION_RISK_OVERRIDE_NAME, paused_at)
    return _review_center_should_promote(
        conn, str((row or {}).get("slug") or folder.name), paused_at
    )


def is_retryable_stage1_budget_failure(folder: Path) -> bool:
    """True when FAILED is an over-budget packet with no draft yet.

    Live 2026-09-21: clarion/confidential/sourcegraph FAILED at 8565/8310/8783
    with no Resume.md. Current assemble trims those to ready. A FAILED folder
    that already has a resume stays paused. One retry marker blocks a loop.
    Implements AC-459 / FR-344. This is not a draft promote.
    """
    if not folder.is_dir():
        return False
    if (folder / "Resume.md").exists():
        return False
    if (folder / STAGE1_BUDGET_RETRY_NAME).exists():
        return False
    packet_path = folder / "authoring_packet.json"
    if not packet_path.is_file():
        return False
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(packet, dict):
        return False
    if packet.get("packet_status") == "ready":
        return True
    blob = " ".join(str(item) for item in (packet.get("incomplete_reasons") or []))
    return "over token budget" in blob.lower()


def write_stage1_budget_retry_marker(folder: Path) -> None:
    """Record that the one over-budget packet retry has started."""
    payload = {
        "reason": "over_token_budget",
        "started_at": utc_now(),
    }
    (folder / STAGE1_BUDGET_RETRY_NAME).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _paused_should_promote(
    folder: Path,
    row: dict[str, Any] | None = None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    if (row or {}).get("paused_reason") == PAUSED_REASON_READY_TO_FINALIZE:
        return False
    if (row or {}).get("last_workflow_status") == MIRROR_READY_TO_FINALIZE:
        return False
    status = _workflow_status(folder)
    if status == "NEEDS_DISPOSITION":
        paused_at = _parse_paused_at((row or {}).get("paused_at"))
        dispositions_at = _dispositions_mtime(folder)
        if paused_at is None or dispositions_at is None:
            return False
        return dispositions_at > paused_at
    if status == "WAITING_FOR_INPUT":
        return _waiting_for_input_should_promote(folder, row, conn)
    if status == "FAILED":
        return is_retryable_stage1_budget_failure(folder)
    if status in (
        "COMPLETE",
        "COMPLETE_WITH_OVERRIDE",
        "PRACTICE_COMPLETE",
        "SKIPPED",
    ):
        return False
    from contracts import check_stage1_ready

    ready, _ = check_stage1_ready(str(folder))
    if status in (None, "", "WAITING_FOR_LLM"):
        return ready
    return True


def _promotable_paused_slugs(conn: sqlite3.Connection, data_root: Path) -> list[str]:
    rows = list_rows(conn, status="paused")
    rows.sort(
        key=lambda row: (
            _parse_paused_at(row.get("paused_at")) is None,
            _parse_paused_at(row.get("paused_at")) or datetime.min.replace(tzinfo=timezone.utc),
            int(row["id"]),
        )
    )
    slugs: list[str] = []
    for row in rows:
        folder = _resolve_row_folder(row, data_root)
        if folder is None:
            continue
        if _paused_should_promote(folder, row, conn):
            slugs.append(row["slug"])
    return slugs


def _archive_roots(
    data_root: Path,
    archive_submissions_root: Path | None,
    archive_skipped_root: Path | None,
) -> tuple[Path, Path]:
    """Resolve archive trees from data_root unless callers inject roots.

    Args: data_root plus optional archive/submissions and archive/skipped.
    Returns the two roots. Does not list either tree.
    """
    subs = (
        archive_submissions_root
        if archive_submissions_root is not None
        else data_root / "archive" / "submissions"
    )
    skip = (
        archive_skipped_root
        if archive_skipped_root is not None
        else data_root / "archive" / "skipped"
    )
    return subs, skip


def _slug_is_already_archived(
    slug: str,
    data_root: Path,
    *,
    archive_submissions_root: Path | None = None,
    archive_skipped_root: Path | None = None,
) -> bool:
    """True when slug folder exists under archive/submissions or archive/skipped.

    Args: slug plus data_root and optional injectable archive roots.
    Returns True on a directory hit. Uses exists, not a tree walk.
    """
    subs, skip = _archive_roots(
        data_root, archive_submissions_root, archive_skipped_root
    )
    return (subs / slug).is_dir() or (skip / slug).is_dir()


def _folder_is_under_archive(folder: Path, data_root: Path) -> bool:
    """True when *folder* is inside data/archive (skipped or submissions)."""
    archive_root = (data_root / "archive").resolve()
    try:
        folder.resolve().relative_to(archive_root)
    except ValueError:
        return False
    return True


def _already_handled_slugs(
    conn: sqlite3.Connection,
    data_root: Path,
    *,
    archive_submissions_root: Path | None = None,
    archive_skipped_root: Path | None = None,
) -> set[str]:
    """Return non-done slugs that are jobs Applied+ or already archived.

    Args: conn, data_root, optional injectable archive roots.
    Returns a set of slugs. Implements FR-363 / AC-472 and FR-366 / AC-475.
    """
    from csv_ingest import lookup_applied_plus_job

    handled: set[str] = set()
    for row in list_rows(conn):
        if row["status"] == "done":
            continue
        slug = row["slug"]
        if _slug_is_already_archived(
            slug,
            data_root,
            archive_submissions_root=archive_submissions_root,
            archive_skipped_root=archive_skipped_root,
        ):
            # Live pending_review / submissions wins a leftover archive/skipped
            # folder from an earlier skip of the same slug (employers 2026-09-22).
            live = _resolve_row_folder(row, data_root)
            if live is None or _folder_is_under_archive(live, data_root):
                handled.add(slug)
            continue
        applied = lookup_applied_plus_job(
            conn,
            row.get("url") or "",
            row.get("company") or "",
            row.get("title") or "",
        )
        if applied:
            handled.add(slug)
    return handled


def _close_already_handled_rows(
    conn: sqlite3.Connection,
    slugs: set[str],
    now: str,
) -> None:
    """Fence-close already-handled rows inside the claim transaction.

    Args: conn, precomputed slugs, utc_now string used for expiry.
    Returns None. queued/paused use the unlocked fence. Expired
    leased/in_progress use the stored locked_by + token. Live leases
    are left alone. Implements FR-363 / AC-472 and FR-366 / AC-475.
    """
    for slug in slugs:
        row = get_row(conn, slug)
        if row is None or row["status"] == "done":
            continue
        status = row["status"]
        try:
            if status in ("queued", "paused") and not row["locked_by"]:
                transition(
                    slug,
                    "done",
                    worker="",
                    token=int(row["fencing_token"] or 0),
                    conn=conn,
                    commit=False,
                )
            elif status in ("leased", "in_progress"):
                expires = row.get("lease_expires_at")
                if expires and expires <= now:
                    transition(
                        slug,
                        "done",
                        worker=row["locked_by"] or "",
                        token=int(row["fencing_token"] or 0),
                        conn=conn,
                        commit=False,
                    )
        except FenceRejected:
            continue


def reconcile_already_handled(
    conn: sqlite3.Connection | None = None,
    *,
    db_path: Path | str | None = None,
    data_root: Path | None = None,
    archive_submissions_root: Path | None = None,
    archive_skipped_root: Path | None = None,
) -> int:
    """Close already-handled non-done queue rows. Returns how many became done.

    Walks Applied+ jobs plus archive/skipped and archive/submissions slugs
    via _already_handled_slugs. queued/paused close immediately; expired
    leased/in_progress close with the stored fence; a live lease is left.
    Implements FR-366 / AC-475.
    """
    close_after = False
    if conn is None:
        conn = connect(db_path)
        close_after = True
    root = data_root if data_root is not None else DATA_ROOT
    try:
        handled = _already_handled_slugs(
            conn,
            root,
            archive_submissions_root=archive_submissions_root,
            archive_skipped_root=archive_skipped_root,
        )
        before = {
            slug: (get_row(conn, slug) or {}).get("status") for slug in handled
        }
        _close_already_handled_rows(conn, handled, utc_now())
        conn.commit()
        closed = 0
        for slug in handled:
            row = get_row(conn, slug)
            if row and row["status"] == "done" and before.get(slug) != "done":
                closed += 1
        return closed
    finally:
        if close_after:
            conn.close()


def claim_pack(
    worker: str,
    size: int = DEFAULT_PACK_SIZE,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    conn: sqlite3.Connection | None = None,
    *,
    db_path: Path | str | None = None,
    data_root: Path | None = None,
    archive_submissions_root: Path | None = None,
    archive_skipped_root: Path | None = None,
) -> list[dict[str, Any]]:
    if size < 1 or size > MAX_PACK_SIZE:
        raise PackSizeError(f"size must be 1..{MAX_PACK_SIZE}, got {size}")
    close_after = False
    if conn is None:
        conn = connect(db_path)
        close_after = True
    root = data_root if data_root is not None else DATA_ROOT
    try:
        # Same pre-BEGIN IMMEDIATE slot as _promotable_paused_slugs.
        # Implements FR-363 / AC-472.
        already_handled = _already_handled_slugs(
            conn,
            root,
            archive_submissions_root=archive_submissions_root,
            archive_skipped_root=archive_skipped_root,
        )
        promotable = [
            slug
            for slug in _promotable_paused_slugs(conn, root)
            if slug not in already_handled
        ]
        now = utc_now()
        old_level = conn.isolation_level
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            _close_already_handled_rows(conn, already_handled, now)
            claimed: list[dict[str, Any]] = []
            for slug in promotable[:size]:
                row = get_row(conn, slug)
                if not row or row["status"] != "paused":
                    continue
                queued_row = transition(
                    slug,
                    "queued",
                    worker=row["locked_by"] or "",
                    token=row["fencing_token"],
                    conn=conn,
                    commit=False,
                )
                claimed.append(
                    transition(
                        queued_row["slug"],
                        "leased",
                        worker=worker,
                        token=queued_row["fencing_token"],
                        conn=conn,
                        lease_minutes=lease_minutes,
                        commit=False,
                    )
                )
            remaining = size - len(claimed)
            if remaining > 0:
                exclude = [row["slug"] for row in claimed]
                exclude.extend(
                    slug for slug in already_handled if slug not in exclude
                )
                where_sql = """
                    status = 'queued'
                    OR (
                      lease_expires_at IS NOT NULL
                      AND lease_expires_at <= ?
                      AND status IN ('leased', 'in_progress')
                    )
                """
                params: list[Any] = [now]
                if exclude:
                    placeholders = ",".join("?" * len(exclude))
                    where_sql = f"({where_sql}) AND slug NOT IN ({placeholders})"
                    params.extend(exclude)
                params.append(remaining)
                candidates = conn.execute(
                    f"""
                    SELECT * FROM pipeline_queue
                    WHERE {where_sql}
                    ORDER BY queued_at, id
                    LIMIT ?
                    """,
                    params,
                ).fetchall()
                for raw in candidates:
                    row = dict(raw)
                    if row["status"] != "queued":
                        row = transition(
                            row["slug"],
                            "queued",
                            worker=row["locked_by"] or worker,
                            token=row["fencing_token"],
                            conn=conn,
                            commit=False,
                        )
                    claimed.append(
                        transition(
                            row["slug"],
                            "leased",
                            worker=worker,
                            token=row["fencing_token"],
                            conn=conn,
                            lease_minutes=lease_minutes,
                            commit=False,
                        )
                    )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.isolation_level = old_level
        return claimed
    finally:
        if close_after:
            conn.close()


def heartbeat(
    worker: str,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    conn: sqlite3.Connection | None = None,
    *,
    db_path: Path | str | None = None,
) -> int:
    close_after = False
    if conn is None:
        conn = connect(db_path)
        close_after = True
    try:
        cur = conn.execute(
            """
            UPDATE pipeline_queue
            SET lease_expires_at = ?, updated_at = ?
            WHERE locked_by = ? AND status IN ('leased', 'in_progress')
            """,
            (_lease_expiry(lease_minutes), utc_now(), worker),
        )
        conn.commit()
        return cur.rowcount
    finally:
        if close_after:
            conn.close()


def release(
    worker: str,
    conn: sqlite3.Connection | None = None,
    *,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    close_after = False
    if conn is None:
        conn = connect(db_path)
        close_after = True
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_queue WHERE locked_by = ? AND status = 'leased'",
            (worker,),
        ).fetchall()
        released: list[dict[str, Any]] = []
        for raw in rows:
            row = dict(raw)
            released.append(
                transition(
                    row["slug"],
                    "queued",
                    worker=worker,
                    token=row["fencing_token"],
                    conn=conn,
                )
            )
        return released
    finally:
        if close_after:
            conn.close()

