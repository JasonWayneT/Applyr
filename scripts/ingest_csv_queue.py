#!/usr/bin/env python3
"""CR-119 drop-folder ingest: inbox CSV → queued rows + pending_review JD files.

# Implements FR-340 / FR-341 / FR-342 / AC-438 / AC-440 / SEC-007
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import csv_ingest as ingest
import pipeline_queue as pq
from stage0_skip_ledger import ensure_schema as ensure_skip_schema
from stage0_skip_ledger import normalize_url, posting_key

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = _REPO_ROOT / "data" / "inbox" / "csv"


def _safe_print(*args: object) -> None:
    print(*args)


def _move_aside(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        dest = dest_dir / f"{src.stem}_{stamp}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


def ingest_inbox(
    inbox: Path,
    db_path: Path,
    *,
    dry_run: bool = False,
    pending_root: Path | None = None,
    submissions_root: Path | None = None,
    archive_submissions_root: Path | None = None,
    archive_skipped_root: Path | None = None,
    data_root: Path | None = None,
    reconcile_already_handled: bool = False,
    sleep_s: float | None = None,
) -> dict[str, int]:
    pending = pending_root if pending_root is not None else ingest.PENDING_REVIEW
    submissions = submissions_root if submissions_root is not None else ingest.SUBMISSIONS
    archive_subs = (
        archive_submissions_root
        if archive_submissions_root is not None
        else ingest.ARCHIVE_SUBMISSIONS
    )
    archive_skip = (
        archive_skipped_root
        if archive_skipped_root is not None
        else ingest.ARCHIVE_SKIPPED
    )
    archive_dir = inbox / "archive"
    quarantine_dir = inbox / "quarantine"
    counts = {
        "files_seen": 0,
        "files_archived": 0,
        "files_quarantined": 0,
        "files_duplicate_hash": 0,
        "files_unstable": 0,
        "queued": 0,
        "reused": 0,
        "skipped_ledger": 0,
        "already_handled": 0,
        "quarantined_rows": 0,
        "reconciled": 0,
    }
    root = data_root if data_root is not None else pending.parent
    conn = pq.connect(db_path)
    ensure_skip_schema(conn)
    try:
        if reconcile_already_handled:
            # Implements FR-366 / AC-475. Same closer as already_handled rows.
            counts["reconciled"] = pq.reconcile_already_handled(
                conn,
                data_root=root,
                archive_submissions_root=archive_subs,
                archive_skipped_root=archive_skip,
            )
        if not inbox.exists():
            if reconcile_already_handled:
                return counts
            raise FileNotFoundError(f"inbox not found: {inbox}")
        for path in sorted(inbox.glob("*.csv")):
            counts["files_seen"] += 1
            if not ingest.file_size_stable(
                path, sleep_s if sleep_s is not None else ingest.STABLE_SIZE_SLEEP_S
            ):
                counts["files_unstable"] += 1
                continue
            digest = ingest.sha256_file(path)
            if pq.lookup_file(conn, digest):
                counts["files_duplicate_hash"] += 1
                continue
            text, enc_err = ingest.read_csv_text(path)
            if enc_err:
                counts["files_quarantined"] += 1
                if not dry_run:
                    moved = _move_aside(path, quarantine_dir)
                    pq.record_quarantine(
                        conn,
                        scope="file",
                        source_file=path.name,
                        error_code=enc_err,
                        quarantine_reason=ingest.quarantine_reason(enc_err),
                    )
                    pq.record_file(
                        conn,
                        sha256=digest,
                        filename=path.name,
                        row_count=0,
                        quarantine_count=1,
                        archive_path=str(moved),
                        status="file_quarantined",
                    )
                continue
            rows, parse_err = ingest.parse_csv_rows(text or "")
            if parse_err:
                counts["files_quarantined"] += 1
                if not dry_run:
                    moved = _move_aside(path, quarantine_dir)
                    pq.record_quarantine(
                        conn,
                        scope="file",
                        source_file=path.name,
                        error_code=parse_err,
                        quarantine_reason=ingest.quarantine_reason(parse_err),
                    )
                    pq.record_file(
                        conn,
                        sha256=digest,
                        filename=path.name,
                        row_count=0,
                        quarantine_count=1,
                        archive_path=str(moved),
                        status="file_quarantined",
                    )
                continue

            row_quarantine = 0
            queued_here = 0
            line_number = 1
            for line_number, row in enumerate(rows or [], start=2):
                row = ingest.normalize_ingest_row(row)
                ok, error_code = ingest.validate_row(row)
                if not ok and error_code:
                    row_quarantine += 1
                    counts["quarantined_rows"] += 1
                    if not dry_run:
                        pq.record_quarantine(
                            conn,
                            scope="row",
                            source_file=path.name,
                            error_code=error_code,
                            quarantine_reason=ingest.quarantine_reason(error_code),
                            line_number=line_number,
                            raw_payload=ingest.row_payload(row),
                        )
                    continue
                company = (row.get("Company") or "").strip()
                title = (row.get("Position") or "").strip()
                url = (row.get("URL") or "").strip()
                jd = (row.get("Job Description") or "").strip()
                action, slug = ingest.resolve_opportunity(
                    company,
                    title,
                    url,
                    conn,
                    pending_root=pending,
                    submissions_root=submissions,
                    skip_db_path=db_path,
                    archive_submissions_root=archive_subs,
                    archive_skipped_root=archive_skip,
                )
                if action == "skip_ledger":
                    counts["skipped_ledger"] += 1
                    continue
                if action == "already_handled":
                    # Implements FR-361 / AC-470. Distinct from skip_ledger.
                    counts["already_handled"] += 1
                    if not dry_run:
                        # Implements FR-366 / AC-475. Close any existing ghost.
                        counts["reconciled"] += pq.reconcile_already_handled(
                            conn,
                            data_root=root,
                            archive_submissions_root=archive_subs,
                            archive_skipped_root=archive_skip,
                        )
                    continue
                if action == "reuse":
                    counts["reused"] += 1
                    if not dry_run and pq.get_row(conn, slug) is None:
                        pq.upsert_queued(
                            conn,
                            slug=slug,
                            company=company,
                            title=title,
                            url=url or None,
                            url_key=normalize_url(url) if url else None,
                            posting_key=posting_key(company, title),
                            networking_contacts_raw=ingest.networking_contacts_raw(row),
                            source_sha256=digest,
                            source_line=line_number,
                            folder_root="pending_review"
                            if (pending / slug).exists()
                            else "submissions",
                        )
                    continue
                if not dry_run:
                    ingest.write_jd(slug, url, title, jd, dest_root=pending)
                    pq.upsert_queued(
                        conn,
                        slug=slug,
                        company=company,
                        title=title,
                        url=url or None,
                        url_key=normalize_url(url) if url else None,
                        posting_key=posting_key(company, title),
                        networking_contacts_raw=ingest.networking_contacts_raw(row),
                        source_sha256=digest,
                        source_line=line_number,
                        folder_root="pending_review",
                    )
                counts["queued"] += 1
                queued_here += 1

            if not dry_run:
                moved = _move_aside(path, archive_dir)
                pq.record_file(
                    conn,
                    sha256=digest,
                    filename=path.name,
                    row_count=queued_here,
                    quarantine_count=row_quarantine,
                    archive_path=str(moved),
                    status="ingested",
                )
            counts["files_archived"] += 1
    finally:
        conn.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest CSVs from the drop-folder inbox.")
    parser.add_argument("--inbox", default=str(DEFAULT_INBOX))
    parser.add_argument("--db", default=str(pq.DEFAULT_DB))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--reconcile-already-handled",
        action="store_true",
        help="Close already-handled queue ghosts without requiring inbox CSVs.",
    )
    args = parser.parse_args(argv)
    counts = ingest_inbox(
        Path(args.inbox),
        Path(args.db),
        dry_run=args.dry_run,
        reconcile_already_handled=args.reconcile_already_handled,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "queued": counts["queued"],
                    "duplicate": counts["files_duplicate_hash"],
                    "quarantined": counts["files_quarantined"] + counts["quarantined_rows"],
                }
            )
        )
        return 0
    _safe_print(
        "files_seen={files_seen} archived={files_archived} "
        "quarantined_files={files_quarantined} duplicate_hash={files_duplicate_hash} "
        "unstable={files_unstable} queued={queued} reused={reused} "
        "skipped_ledger={skipped_ledger} already_handled={already_handled} "
        "reconciled={reconciled} quarantined_rows={quarantined_rows}".format(**counts)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
