#!/usr/bin/env python3
"""
CR-078: thin CLI wrapper around contracts.check_finalize_ready(), for server/routes/jobs/files.ts
to shell out to instead of trusting draft_manifest.json's verification_passed field directly.

Why this exists (2026-08-09): the PUT /api/jobs/:id/files/:filename PDF-export gate used to read
manifest.verification_passed as its only signal -- a hand-edited or stale draft_manifest.json
could flip that boolean and unlock export with no independent check against the real
verification_receipt.json. contracts.check_finalize_ready() already closes that (it re-derives
pass/fail from verification_receipt.json's own mechanically_verified flag, hash-based freshness,
and rubric shape -- not just the manifest's self-reported boolean), but nothing outside Python
could call it. This script is that missing bridge -- no new logic, just exposes the existing,
already-proven CR-075 gate over a CLI/JSON boundary the TS route can consume.

Deliberately does NOT call contracts.check_workflow_complete() (CR-076/077's newer, stricter
oracle) -- as of this CR, check_workflow_complete() returns False for every real submission
folder on disk (Stage 2/3 receipts don't exist yet; those land in CR-079-081), so wiring the
export gate to it today would break PDF export for every already-verified submission. CR-078's
own spec (Decision item 4 / AC-303) requires check_workflow_complete's verdict to be proven
equivalent against real folders before any live-app behavior migrates to it -- that proof doesn't
exist yet, so this script intentionally stays on the already-proven check_finalize_ready() gate.
Swapping to check_workflow_complete() is a follow-up once CR-079-081 make it meaningful.

Usage:
    python scripts/check_finalize_ready.py data/submissions/COMPANY
        Prints {"ok": bool, "errors": [str, ...]} as JSON on stdout.
        Exit 0 if ok, exit 1 if not ready (including a missing/invalid folder).
"""
from __future__ import annotations

import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

import contracts  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "errors": ["usage: check_finalize_ready.py <folder>"]}))
        sys.exit(1)

    folder = sys.argv[1].rstrip("/\\")
    if not os.path.isdir(folder):
        print(json.dumps({"ok": False, "errors": [f"{folder} is not a directory"]}))
        sys.exit(1)

    ok, errors = contracts.check_finalize_ready(folder)
    print(json.dumps({"ok": ok, "errors": errors}))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
