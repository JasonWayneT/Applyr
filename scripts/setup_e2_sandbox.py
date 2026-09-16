#!/usr/bin/env python3
"""
Construct an isolated E2 dry-run sandbox.

Creates data/sandbox/e2-dryrun/<slug>/ with:
  - Original_JD.txt copied from --source
  - Reference snapshots of master_claims sidecars at the sandbox root
  - An empty SQLite shim (e2-sandbox.sqlite) at the sandbox root

The shim has the production jobs/activity_log/profiles/system_status schema
but no rows.  Point the pipeline at it via APPLYR_SANDBOX_DB so Stage 0-2
reads against an isolated, empty DB rather than production jobagent.sqlite.
Use --mode practice for the actual run so Stage 3 never writes at all.

Usage:
  python scripts/setup_e2_sandbox.py --source data/submissions/arbiter
  python scripts/setup_e2_sandbox.py --source tests/fixtures/cr112_eval/jd_01_northwind_platform

Then run the dry run (PowerShell):
  $env:APPLYR_SANDBOX_DB = 'data/sandbox/e2-dryrun/e2-sandbox.sqlite'
  python scripts/run_submission.py data/sandbox/e2-dryrun/<slug> --mode practice
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
_SANDBOX_ROOT = os.path.join(_REPO_ROOT, "data", "sandbox", "e2-dryrun")
_DATA_DIR = os.path.join(_REPO_ROOT, "data")

_SHIM_DDL = """\
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    url TEXT UNIQUE,
    score INTEGER,
    status TEXT DEFAULT 'Drafted',
    summary TEXT,
    salary_range TEXT,
    rejection_type TEXT,
    outcome_notes TEXT,
    status_changed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    meta TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS system_status (
    id TEXT PRIMARY KEY,
    process_type TEXT,
    status TEXT,
    current_item TEXT,
    items_completed INTEGER DEFAULT 0,
    items_total INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _create_shim(shim_path: str) -> None:
    if os.path.exists(shim_path):
        print(f"  shim already exists, skipping: {os.path.relpath(shim_path, _REPO_ROOT)}")
        return
    conn = sqlite3.connect(shim_path)
    try:
        conn.executescript(_SHIM_DDL)
        conn.commit()
    finally:
        conn.close()
    print(f"  created shim:  {os.path.relpath(shim_path, _REPO_ROOT)}")


def _copy_sidecars(dest_dir: str) -> None:
    for name in ("master_claims_tags_only.json", "master_claims.json"):
        src = os.path.join(_DATA_DIR, name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dest_dir, name)
        shutil.copy2(src, dst)
        print(f"  sidecar copy:  {os.path.relpath(dst, _REPO_ROOT)}")


def setup_sandbox(source: str, slug: str) -> None:
    source = os.path.abspath(source)
    jd_src = os.path.join(source, "Original_JD.txt")
    if not os.path.exists(jd_src):
        sys.exit(f"error: Original_JD.txt not found in {source}")

    slug_dir = os.path.join(_SANDBOX_ROOT, slug)
    os.makedirs(slug_dir, exist_ok=True)

    jd_dst = os.path.join(slug_dir, "Original_JD.txt")
    shutil.copy2(jd_src, jd_dst)
    print(f"  Original_JD.txt -> {os.path.relpath(jd_dst, _REPO_ROOT)}")

    _copy_sidecars(_SANDBOX_ROOT)

    shim_path = os.path.join(_SANDBOX_ROOT, "e2-sandbox.sqlite")
    _create_shim(shim_path)

    rel_shim = os.path.relpath(shim_path, _REPO_ROOT)
    rel_slug = os.path.relpath(slug_dir, _REPO_ROOT)
    print()
    print("Sandbox ready.  To run the E2 dry run (PowerShell):")
    print()
    print(f"  $env:APPLYR_SANDBOX_DB = '{rel_shim.replace(os.sep, '/')}'")
    print(f"  python scripts/run_submission.py {rel_slug.replace(os.sep, '/')} --mode practice")
    print()
    print("Clear the env var afterwards:")
    print("  Remove-Item Env:\\APPLYR_SANDBOX_DB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, metavar="PATH",
                        help="Folder containing Original_JD.txt (submission or fixture dir)")
    parser.add_argument("--slug", metavar="NAME",
                        help="Sandbox slug name (default: basename of --source)")
    args = parser.parse_args()

    slug = args.slug or os.path.basename(args.source.rstrip("/\\"))
    print(f"Setting up E2 sandbox: {slug}")
    setup_sandbox(args.source, slug)


if __name__ == "__main__":
    main()
