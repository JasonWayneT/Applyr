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

# Semantically identical to server/migrations/025_add_pipeline_queue.sql.
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
  last_stage           TEXT
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


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the three CR-119 tables if missing. Idempotent."""
    conn.executescript(_SCHEMA_SQL)
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
        ("in_progress", "done"),
        ("leased", "queued"),
        # Expiry reclaim: an expired in_progress row becomes claimable (Story 3.3).
        ("in_progress", "queued"),
    }
)

MAX_PACK_SIZE = 10
DEFAULT_PACK_SIZE = 8
DEFAULT_LEASE_MINUTES = 20
DATA_ROOT = _REPO_ROOT / "data"


class IllegalTransition(ValueError):
    """Status pair is not in the CR-119 transition table."""


class FenceRejected(RuntimeError):
    """Fenced UPDATE matched zero rows; SQLite state is unchanged."""


class PackSizeError(ValueError):
    """--size outside 1..10."""


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


def _paused_should_promote(folder: Path) -> bool:
    from contracts import check_stage1_ready

    ready, _ = check_stage1_ready(str(folder))
    if ready:
        return True
    status = _workflow_status(folder)
    if status in (
        None,
        "",
        "WAITING_FOR_LLM",
        "NEEDS_DISPOSITION",
        "COMPLETE",
        "COMPLETE_WITH_OVERRIDE",
        "PRACTICE_COMPLETE",
        "SKIPPED",
    ):
        return False
    return True


def _promotable_paused_slugs(conn: sqlite3.Connection, data_root: Path) -> list[str]:
    slugs: list[str] = []
    for row in list_rows(conn, status="paused"):
        folder = _resolve_row_folder(row, data_root)
        if folder is None:
            continue
        if _paused_should_promote(folder):
            slugs.append(row["slug"])
    return slugs


def claim_pack(
    worker: str,
    size: int = DEFAULT_PACK_SIZE,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
    conn: sqlite3.Connection | None = None,
    *,
    db_path: Path | str | None = None,
    data_root: Path | None = None,
) -> list[dict[str, Any]]:
    if size < 1 or size > MAX_PACK_SIZE:
        raise PackSizeError(f"size must be 1..{MAX_PACK_SIZE}, got {size}")
    close_after = False
    if conn is None:
        conn = connect(db_path)
        close_after = True
    root = data_root if data_root is not None else DATA_ROOT
    try:
        promotable = _promotable_paused_slugs(conn, root)
        now = utc_now()
        old_level = conn.isolation_level
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            for slug in promotable:
                row = get_row(conn, slug)
                if not row or row["status"] != "paused":
                    continue
                transition(
                    slug,
                    "queued",
                    worker=row["locked_by"] or "",
                    token=row["fencing_token"],
                    conn=conn,
                    commit=False,
                )
            candidates = conn.execute(
                """
                SELECT * FROM pipeline_queue
                WHERE status = 'queued'
                   OR (
                     lease_expires_at IS NOT NULL
                     AND lease_expires_at <= ?
                     AND status IN ('leased', 'in_progress')
                   )
                ORDER BY queued_at, id
                LIMIT ?
                """,
                (now, size),
            ).fetchall()
            claimed: list[dict[str, Any]] = []
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

