#!/usr/bin/env python3
"""Stage 0 skip ledger — posting memory keyed by URL, then company+title.

# Implements FR-264 / CR-091

Not a jobs.status. Application outcomes stay on the jobs table. This table
answers "did we already Skip this posting?" in one indexed lookup.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SCRIPT_DIR = Path(__file__).parent
_REPO_ROOT = _SCRIPT_DIR.parent
DEFAULT_DB = _REPO_ROOT / "data" / "jobagent.sqlite"

_TRACKING_PARAMS = frozenset(
    {"gh_src", "source", "ref", "trk", "mc_cid", "mc_eid"}
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS stage0_skips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT,
  url_key TEXT,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  posting_key TEXT NOT NULL,
  skip_reason TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  slug TEXT,
  archive_path TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_stage0_skips_url_key
  ON stage0_skips(url_key) WHERE url_key IS NOT NULL AND url_key != '';
CREATE UNIQUE INDEX IF NOT EXISTS idx_stage0_skips_posting_key
  ON stage0_skips(posting_key);
"""


def normalize_url(url: str | None) -> str | None:
    """Lowercase URL with tracking query params stripped. Empty → None."""
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    parts = urlsplit(raw)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or ""
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in _TRACKING_PARAMS:
            continue
        kept.append((key, value))
    query = urlencode(kept, doseq=True)
    if not netloc and not path:
        return raw.lower().rstrip("/")
    normalized = urlunsplit((scheme, netloc, path, query, ""))
    return normalized or None


def posting_key(company: str, title: str) -> str:
    """Exact company||title identity for URL-less (or URL-changed) fallback."""
    return f"{(company or '').strip().lower()}||{(title or '').strip().lower()}"


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create stage0_skips if missing. Idempotent."""
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open the jobs DB and ensure the skip table exists."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def lookup_skip(
    *,
    url: str | None = None,
    company: str = "",
    title: str = "",
    db_path: Path | str | None = None,
    _conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Return the skip row if this posting was skipped before, else None.

    URL (normalized) wins. Company+title is the fallback when URL is missing
    or a board id changed but the title did not.
    """
    close_after = False
    conn = _conn
    if conn is None:
        path = Path(db_path) if db_path is not None else DEFAULT_DB
        if not path.exists():
            return None
        conn = connect(path)
        close_after = True
    else:
        ensure_schema(conn)
    try:
        url_key = normalize_url(url)
        if url_key:
            row = conn.execute(
                "SELECT * FROM stage0_skips WHERE url_key = ?",
                (url_key,),
            ).fetchone()
            if row:
                return dict(row)
        key = posting_key(company, title)
        if key == "||":
            return None
        row = conn.execute(
            "SELECT * FROM stage0_skips WHERE posting_key = ?",
            (key,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        if close_after:
            conn.close()


def record_skip(
    *,
    url: str | None,
    company: str,
    title: str,
    skip_reason: str,
    slug: str | None = None,
    archive_path: str | None = None,
    db_path: Path | str | None = None,
    _conn: sqlite3.Connection | None = None,
    decided_at: str | None = None,
) -> dict[str, Any]:
    """Insert or update a skip row. Returns the stored row."""
    close_after = False
    conn = _conn
    if conn is None:
        conn = connect(db_path)
        close_after = True
    else:
        ensure_schema(conn)
    try:
        url_key = normalize_url(url)
        key = posting_key(company, title)
        now = decided_at or datetime.now(tz=timezone.utc).isoformat()
        existing = lookup_skip(
            url=url, company=company, title=title, _conn=conn
        )
        if existing:
            conn.execute(
                """
                UPDATE stage0_skips
                SET url = ?, url_key = ?, company = ?, title = ?,
                    posting_key = ?, skip_reason = ?, decided_at = ?,
                    slug = ?, archive_path = ?
                WHERE id = ?
                """,
                (
                    url or existing.get("url"),
                    url_key or existing.get("url_key"),
                    company,
                    title,
                    key,
                    skip_reason,
                    now,
                    slug if slug is not None else existing.get("slug"),
                    archive_path
                    if archive_path is not None
                    else existing.get("archive_path"),
                    existing["id"],
                ),
            )
            row_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO stage0_skips (
                    url, url_key, company, title, posting_key,
                    skip_reason, decided_at, slug, archive_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    url,
                    url_key,
                    company,
                    title,
                    key,
                    skip_reason,
                    now,
                    slug,
                    archive_path,
                ),
            )
            row_id = cur.lastrowid
        conn.commit()
        row = conn.execute(
            "SELECT * FROM stage0_skips WHERE id = ?", (row_id,)
        ).fetchone()
        return dict(row)
    finally:
        if close_after:
            conn.close()


def clear_skip(
    *,
    url: str | None = None,
    company: str = "",
    title: str = "",
    db_path: Path | str | None = None,
    _conn: sqlite3.Connection | None = None,
) -> bool:
    """Delete a skip row after a forced PASS. True if a row was removed."""
    close_after = False
    conn = _conn
    if conn is None:
        path = Path(db_path) if db_path is not None else DEFAULT_DB
        if not path.exists():
            return False
        conn = connect(path)
        close_after = True
    else:
        ensure_schema(conn)
    try:
        existing = lookup_skip(
            url=url, company=company, title=title, _conn=conn
        )
        if not existing:
            return False
        conn.execute("DELETE FROM stage0_skips WHERE id = ?", (existing["id"],))
        conn.commit()
        return True
    finally:
        if close_after:
            conn.close()
