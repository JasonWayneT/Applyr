#!/usr/bin/env python3
"""Copy data/*.example.* → runtime files when missing (local dev / fresh clone)."""
from __future__ import annotations

import os
import shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

PAIRS = [
    ("candidate_preferences.example.json", "candidate_preferences.json"),
    ("master_claims.example.json", "master_claims.json"),
    ("workExperience.example.md", "workExperience.md"),
    ("workExperience_summary.example.md", "workExperience_summary.md"),
]


def main() -> int:
    os.makedirs(DATA_DIR, exist_ok=True)
    copied = []
    for src_name, dest_name in PAIRS:
        src = os.path.join(DATA_DIR, src_name)
        dest = os.path.join(DATA_DIR, dest_name)
        if os.path.exists(dest):
            continue
        if not os.path.exists(src):
            print(f"  [SKIP] missing template: {src_name}")
            continue
        shutil.copy2(src, dest)
        copied.append(dest_name)
        print(f"  [OK] created {dest_name} from {src_name}")
    if not copied:
        print("bootstrap_local_data: all runtime data files already present.")
    else:
        print(f"bootstrap_local_data: created {len(copied)} file(s). Re-save Job Search in UI to merge SQLite prefs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
