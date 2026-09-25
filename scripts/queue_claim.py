#!/usr/bin/env python3
"""CR-119 claim/heartbeat/release/requeue CLI. Thin argparse over pipeline_queue.

# Implements FR-343 / NFR-016 / SEC-007
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pipeline_queue as pq

_SAFE_STATUS_COLUMNS = (
    "slug",
    "status",
    "locked_by",
    "lease_expires_at",
    "fencing_token",
    "queued_at",
    "claimed_at",
    "updated_at",
    "last_workflow_status",
    "last_stage",
    "folder_root",
    "paused_reason",
    "requeued_by",
    "requeue_reason",
    "requeued_at",
)


def _print_row(row: dict) -> None:
    parts = [f"{key}={row.get(key)}" for key in _SAFE_STATUS_COLUMNS]
    print(" ".join(parts))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Claim and manage pipeline_queue packs.")
    parser.add_argument("--db", default=str(pq.DEFAULT_DB))
    sub = parser.add_subparsers(dest="cmd", required=True)

    claim = sub.add_parser("claim")
    claim.add_argument("--size", type=int, default=pq.DEFAULT_PACK_SIZE)
    claim.add_argument("--worker", required=True)
    claim.add_argument("--lease-minutes", type=int, default=pq.DEFAULT_LEASE_MINUTES)

    hb = sub.add_parser("heartbeat")
    hb.add_argument("--worker", required=True)
    hb.add_argument("--lease-minutes", type=int, default=pq.DEFAULT_LEASE_MINUTES)

    rel = sub.add_parser("release")
    rel.add_argument("--worker", required=True)

    sub.add_parser("status")

    requeue = sub.add_parser("requeue")
    requeue.add_argument("--slug", required=True)
    requeue.add_argument("--reason", required=True)
    requeue.add_argument("--worker", default="manual")
    requeue.add_argument("--data-root", default=str(pq.DATA_ROOT))

    args = parser.parse_args(argv)
    db_path = Path(args.db)
    if args.cmd == "claim":
        try:
            rows = pq.claim_pack(
                args.worker,
                size=args.size,
                lease_minutes=args.lease_minutes,
                db_path=db_path,
            )
        except pq.PackSizeError as err:
            print(str(err), file=sys.stderr)
            return 2
        print(f"claimed={len(rows)}")
        for row in rows:
            _print_row(row)
        return 0
    if args.cmd == "heartbeat":
        n = pq.heartbeat(args.worker, lease_minutes=args.lease_minutes, db_path=db_path)
        print(f"heartbeat={n} worker={args.worker}")
        return 0
    if args.cmd == "release":
        rows = pq.release(args.worker, db_path=db_path)
        print(f"released={len(rows)}")
        for row in rows:
            _print_row(row)
        return 0
    if args.cmd == "requeue":
        try:
            row = pq.requeue_paused(
                args.slug,
                reason=args.reason,
                worker=args.worker,
                db_path=db_path,
                data_root=Path(args.data_root),
            )
        except pq.RequeueRefused as err:
            print(str(err), file=sys.stderr)
            return 2
        print(
            f"requeued=1 slug={row['slug']} status={row['status']} "
            f"by={row.get('requeued_by')} reason={row.get('requeue_reason')}"
        )
        _print_row(row)
        return 0
    conn = pq.connect(db_path)
    try:
        rows = pq.list_rows(conn)
        print(f"rows={len(rows)}")
        for row in rows:
            _print_row(row)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
