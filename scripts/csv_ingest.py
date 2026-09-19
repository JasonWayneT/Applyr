#!/usr/bin/env python3
"""Shared CSV ingest helpers for CR-119 (FR-340 / FR-341 / FR-342).

Moved from import_csv_to_submissions.py. write_jd() output is pinned by AC-440.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from stage0_skip_ledger import lookup_skip, normalize_url, posting_key

ROOT = Path(__file__).resolve().parents[1]
PENDING_REVIEW = ROOT / "data" / "pending_review"
SUBMISSIONS = ROOT / "data" / "submissions"
DB = ROOT / "data" / "jobagent.sqlite"

# Closed error-code set (CR-119). Spellings are part of the contract.
EMPTY_COMPANY = "EMPTY_COMPANY"
JD_TOO_SHORT = "JD_TOO_SHORT"
NO_DEDUP_KEY = "NO_DEDUP_KEY"
FILE_UNPARSEABLE = "FILE_UNPARSEABLE"
FILE_ENCODING = "FILE_ENCODING"
ERROR_CODES = frozenset(
    {EMPTY_COMPANY, JD_TOO_SHORT, NO_DEDUP_KEY, FILE_UNPARSEABLE, FILE_ENCODING}
)

JD_MIN_CHARS = 200
STABLE_SIZE_SLEEP_S = 0.25

_REQUIRED_HEADERS = frozenset({"Company", "Job Description"})
_COMPANY_TITLE_SEPS = (" - ", " – ", " — ", " | ", ": ", " / ")


def sanitize(name: str) -> str:
    return re.sub(r"[\W_]+", "_", name).strip("_").lower()


def clean_company_field(company: str, title: str = "") -> str:
    """Strip a trailing or prefixed role title from the Company cell.

    Bookmarklet and some CSV exports put "ESO Product Manager" (or
    "Product Manager at ESO") in Company while Position already holds the
    title. That made a second slug (`eso_product_manager`) and missed the
    ESO cooldown / skip-ledger row.
    """
    company = re.sub(r"\s+", " ", (company or "").replace("\u00a0", " ")).strip()
    title = re.sub(r"\s+", " ", (title or "").replace("\u00a0", " ")).strip()
    if not company:
        return ""
    if not title:
        return company
    lowered_c = company.lower()
    lowered_t = title.lower()
    if lowered_c == lowered_t:
        return ""
    for suffix in (lowered_t, *(f"{sep}{lowered_t}" for sep in _COMPANY_TITLE_SEPS)):
        if lowered_c.endswith(suffix) and len(company) > len(suffix):
            remainder = company[: len(company) - len(suffix)].rstrip(" -–—|:/")
            if remainder and remainder.lower() != lowered_t:
                return remainder.strip()
    prefix = f"{lowered_t} at "
    if lowered_c.startswith(prefix):
        remainder = company[len(prefix) :].strip(" -–—|:/")
        if remainder and remainder.lower() != lowered_t:
            return remainder
    return company


def normalize_ingest_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with Company cleaned against Position."""
    out = dict(row)
    title = (out.get("Position") or "").strip()
    out["Position"] = title
    out["Company"] = clean_company_field(out.get("Company") or "", title)
    return out


def _scan_jd_urls(root: Path, mapping: dict[str, str]) -> None:
    """Add URL → slug mappings from Original_JD.txt files under root."""
    if not root.exists():
        return
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        jd = folder / "Original_JD.txt"
        if not jd.exists():
            continue
        first = jd.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
        if first and first[0].lower().startswith("url:"):
            mapping[first[0].split(":", 1)[1].strip().lower()] = folder.name


def url_to_slug(
    db_path: Path | str | None = None,
    pending_root: Path | None = None,
    submissions_root: Path | None = None,
) -> dict[str, str]:
    """Map lowercase URL -> slug (pending_review / submissions win over DB-only rows)."""
    mapping: dict[str, str] = {}
    db = Path(db_path) if db_path is not None else DB
    pending = pending_root if pending_root is not None else PENDING_REVIEW
    submissions = submissions_root if submissions_root is not None else SUBMISSIONS
    if db.exists():
        conn = sqlite3.connect(str(db))
        try:
            for u, company in conn.execute(
                "SELECT url, company FROM jobs WHERE url IS NOT NULL"
            ):
                if u:
                    mapping[u.strip().lower()] = sanitize(company or "")
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
    _scan_jd_urls(pending, mapping)
    _scan_jd_urls(submissions, mapping)
    return mapping


def existing_urls(
    db_path: Path | str | None = None,
    pending_root: Path | None = None,
    submissions_root: Path | None = None,
) -> set[str]:
    return set(url_to_slug(db_path, pending_root, submissions_root).keys())


def unique_slug(
    base: str,
    pending_root: Path | None = None,
    submissions_root: Path | None = None,
) -> str:
    pending = pending_root if pending_root is not None else PENDING_REVIEW
    submissions = submissions_root if submissions_root is not None else SUBMISSIONS
    slug = base
    n = 2
    while (pending / slug).exists() or (submissions / slug).exists():
        slug = f"{base}_{n}"
        n += 1
    return slug


def write_jd(
    slug: str,
    url: str,
    position: str,
    jd: str,
    dest_root: Path | None = None,
) -> Path:
    folder = (dest_root if dest_root is not None else PENDING_REVIEW) / slug
    folder.mkdir(parents=True, exist_ok=True)
    parts = []
    if url:
        parts.append(f"URL: {url}")
        parts.append("")
    if position:
        parts.append(f"Title: {position}")
        parts.append("")
    parts.append(jd.strip())
    path = folder / "Original_JD.txt"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(parts) + "\n")
    return path


def validate_row(row: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (ok, error_code). Checks run in FR-341 order."""
    row = normalize_ingest_row(row)
    company = (row.get("Company") or "").strip()
    if not company:
        return False, EMPTY_COMPANY
    jd = (row.get("Job Description") or "").strip()
    if len(jd) < JD_MIN_CHARS:
        return False, JD_TOO_SHORT
    url = (row.get("URL") or "").strip()
    position = (row.get("Position") or "").strip()
    if not url and not position:
        return False, NO_DEDUP_KEY
    return True, None


def file_size_stable(path: Path, sleep_s: float = STABLE_SIZE_SLEEP_S) -> bool:
    size1 = path.stat().st_size
    time.sleep(sleep_s)
    size2 = path.stat().st_size
    return size1 == size2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_text(path: Path) -> tuple[str | None, str | None]:
    """Return (decoded text, error_code). Strips a UTF-8 BOM if present."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, FILE_ENCODING


def parse_csv_rows(text: str) -> tuple[list[dict[str, str]] | None, str | None]:
    try:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            return None, FILE_UNPARSEABLE
        headers = {h.strip() for h in reader.fieldnames if h}
        if not _REQUIRED_HEADERS.issubset(headers):
            return None, FILE_UNPARSEABLE
        return list(reader), None
    except csv.Error:
        return None, FILE_UNPARSEABLE


def _jd_header_value(folder: Path, prefix: str) -> str | None:
    jd = folder / "Original_JD.txt"
    if not jd.exists():
        return None
    for line in jd.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def _slug_for_url(
    url: str,
    pending: Path,
    submissions: Path,
    conn: sqlite3.Connection,
) -> str | None:
    url_key = normalize_url(url)
    lowered = url.strip().lower()
    mapping: dict[str, str] = {}
    _scan_jd_urls(pending, mapping)
    _scan_jd_urls(submissions, mapping)
    for stored, slug in mapping.items():
        if stored == lowered or (url_key and normalize_url(stored) == url_key):
            return slug
    if url_key:
        row = conn.execute(
            "SELECT slug FROM pipeline_queue WHERE url_key = ?",
            (url_key,),
        ).fetchone()
        if row:
            return row["slug"] if isinstance(row, sqlite3.Row) else row[0]
    return None


def _slug_for_posting(
    company: str,
    title: str,
    pending: Path,
    submissions: Path,
    conn: sqlite3.Connection,
) -> str | None:
    key = posting_key(company, title)
    row = conn.execute(
        "SELECT slug FROM pipeline_queue WHERE posting_key = ? AND (url_key IS NULL OR url_key = '')",
        (key,),
    ).fetchone()
    if row:
        return row["slug"] if isinstance(row, sqlite3.Row) else row[0]
    base = sanitize(company)
    for root in (pending, submissions):
        if not root.exists():
            continue
        candidate = root / base
        if not candidate.is_dir():
            continue
        folder_url = _jd_header_value(candidate, "url:")
        folder_title = _jd_header_value(candidate, "title:") or ""
        if folder_url:
            continue
        if folder_title.strip().lower() == title.strip().lower() or not folder_title:
            return base
    return None


def resolve_opportunity(
    company: str,
    title: str,
    url: str,
    conn: sqlite3.Connection,
    *,
    pending_root: Path | None = None,
    submissions_root: Path | None = None,
    skip_db_path: Path | str | None = None,
) -> tuple[str, str]:
    """Return (action, slug) where action is create / reuse / skip_ledger."""
    pending = pending_root if pending_root is not None else PENDING_REVIEW
    submissions = submissions_root if submissions_root is not None else SUBMISSIONS
    url_text = (url or "").strip()

    if url_text:
        prior = lookup_skip(
            url=url_text,
            company=company,
            title=title,
            db_path=skip_db_path,
            _conn=conn,
        )
        if prior:
            return "skip_ledger", prior.get("slug") or sanitize(company)
        existing = _slug_for_url(url_text, pending, submissions, conn)
        if existing:
            return "reuse", existing
        return "create", unique_slug(sanitize(company), pending, submissions)

    prior = lookup_skip(
        url=None,
        company=company,
        title=title,
        db_path=skip_db_path,
        _conn=conn,
    )
    if prior:
        return "skip_ledger", prior.get("slug") or sanitize(company)
    existing = _slug_for_posting(company, title, pending, submissions, conn)
    if existing:
        return "reuse", existing
    return "create", unique_slug(sanitize(company), pending, submissions)


def networking_contacts_raw(row: dict[str, Any]) -> str | None:
    cell = row.get("Networking Contacts")
    if cell is None or str(cell).strip() == "":
        return None
    return str(cell)


def row_payload(row: dict[str, Any]) -> str:
    return json.dumps(dict(row), ensure_ascii=False)


def quarantine_reason(error_code: str) -> str:
    reasons = {
        EMPTY_COMPANY: "Company field is empty",
        JD_TOO_SHORT: "Job Description is shorter than 200 characters",
        NO_DEDUP_KEY: "Row has neither URL nor Position",
        FILE_UNPARSEABLE: "CSV could not be parsed",
        FILE_ENCODING: "File is not valid UTF-8",
    }
    return reasons.get(error_code, error_code)
