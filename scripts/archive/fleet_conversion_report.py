# Archived 2026-08-04 — legacy pipeline isolation audit.
# Parent scripts/ stays on sys.path so imports of still-live modules keep working.
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)

"""
Fleet conversion quality report (FR-232).

Scans submission folders for draft_manifest.json conversion_critique pass rates.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Dict, List, Tuple

from utils import SUBMISSIONS_DIR, init_pipeline_prefs

init_pipeline_prefs()


def _scan_root(root: str) -> Tuple[List[dict], int]:
    rows: List[dict] = []
    missing = 0
    if not os.path.isdir(root):
        return rows, missing

    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if not os.path.isdir(folder):
            continue
        manifest_path = os.path.join(folder, "draft_manifest.json")
        if not os.path.isfile(manifest_path):
            missing += 1
            rows.append(
                {
                    "folder": name,
                    "root": root,
                    "has_manifest": False,
                    "pass": None,
                    "codes": [],
                    "attempts": None,
                }
            )
            continue
        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            missing += 1
            rows.append(
                {
                    "folder": name,
                    "root": root,
                    "has_manifest": False,
                    "pass": None,
                    "codes": [],
                    "attempts": None,
                }
            )
            continue

        critique = data.get("conversion_critique") or {}
        codes = critique.get("final_codes") or []
        if not codes and critique.get("issues"):
            import re

            for issue in critique["issues"]:
                m = re.match(r"\[(CW-\d+)\]", issue)
                if m and m.group(1) not in codes:
                    codes.append(m.group(1))

        rows.append(
            {
                "folder": name,
                "root": root,
                "has_manifest": True,
                "pass": critique.get("pass"),
                "codes": codes,
                "attempts": critique.get("attempts"),
                "issue_count": critique.get("issue_count"),
            }
        )
    return rows, missing


def scan_submissions(include_archive: bool = False) -> List[dict]:
    rows, _ = _scan_root(SUBMISSIONS_DIR)
    if include_archive:
        archive_root = os.path.join(
            os.path.dirname(SUBMISSIONS_DIR), "archive", "submissions"
        )
        arch_rows, _ = _scan_root(archive_root)
        rows.extend(arch_rows)
    return rows


def print_report(rows: List[dict]) -> int:
    total = len(rows)
    with_manifest = [r for r in rows if r["has_manifest"]]
    evaluated = [r for r in with_manifest if r["pass"] is not None]
    passed = [r for r in evaluated if r["pass"] is True]
    failed = [r for r in evaluated if r["pass"] is False]

    print("=" * 60)
    print("  FLEET CONVERSION QUALITY REPORT (CR-042)")
    print("=" * 60)
    print(f"Folders scanned:     {total}")
    print(f"With manifest:       {len(with_manifest)}")
    print(f"Critique evaluated:  {len(evaluated)}")
    if evaluated:
        pct = 100.0 * len(passed) / len(evaluated)
        print(f"PASS rate:           {len(passed)}/{len(evaluated)} ({pct:.1f}%)")
    print(f"FAIL:                {len(failed)}")
    print(f"Missing manifest:    {total - len(with_manifest)}")

    code_counts: Counter = Counter()
    for r in failed:
        for c in r.get("codes") or []:
            code_counts[c] += 1
    if code_counts:
        print("\nTop failing codes:")
        for code, count in code_counts.most_common(10):
            print(f"  {code}: {count}")

    if failed:
        print("\nFailing folders (by issue count):")
        failed_sorted = sorted(
            failed,
            key=lambda r: (len(r.get("codes") or []), r["folder"]),
            reverse=True,
        )
        for r in failed_sorted[:25]:
            codes = ", ".join(r.get("codes") or []) or "?"
            print(f"  {r['folder']}: {codes}")

    return 0 if not failed else 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fleet conversion critique report")
    parser.add_argument(
        "--include-archive",
        action="store_true",
        help="Also scan archive/submissions/",
    )
    args = parser.parse_args(argv)
    rows = scan_submissions(include_archive=args.include_archive)
    return print_report(rows)


if __name__ == "__main__":
    sys.exit(main())
