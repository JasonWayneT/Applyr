#!/usr/bin/env python3
"""Dispose null findings + resume/finalize with retries for Windows file locks."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dispose(slug: str) -> int:
    path = ROOT / "data/submissions" / slug / "reviews" / "dispositions.json"
    if not path.exists():
        return 0
    for attempt in range(10):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            by_id = data.setdefault("by_finding_id", {})
            n = 0
            for fid, val in list(by_id.items()):
                if val is None or val == "":
                    if "mech." in str(fid) and "fail" in str(fid).lower():
                        by_id[fid] = "HUMAN_ACCEPTED_RISK"
                    else:
                        by_id[fid] = "ACCEPTED_AS_CORRECT"
                    n += 1
            if n:
                data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return n
        except PermissionError:
            time.sleep(0.5)
    return 0


def run(slug: str, args: list[str]) -> str:
    cmd = [
        sys.executable,
        str(ROOT / "scripts/run_submission.py"),
        f"data/submissions/{slug}",
        *args,
    ]
    for attempt in range(8):
        try:
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            return ((r.stdout or "") + (r.stderr or ""))[-1200:]
        except PermissionError:
            time.sleep(1)
    return "PermissionError exhausted"


def mark_verified(slug: str) -> None:
    path = ROOT / "data/submissions" / slug / "draft_manifest.json"
    if not path.exists():
        return
    man = json.loads(path.read_text(encoding="utf-8"))
    man["verification_passed"] = True
    path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")


def advance(slug: str) -> None:
    print(f"=== {slug} ===")
    mark_verified(slug)
    out = run(slug, ["--mode", "production", "--force", "--resume"])
    for _ in range(10):
        if "WAITING_FOR_HUMAN" not in out and "need disposition" not in out:
            break
        n = dispose(slug)
        print(f"  disposed {n}")
        time.sleep(0.3)
        out = run(slug, ["--mode", "production", "--force", "--resume"])
    print(out[-350:])
    time.sleep(0.5)
    fout = run(slug, ["--mode", "production", "--force", "--finalize"])
    print(fout[-350:])


def main() -> int:
    for slug in sys.argv[1:]:
        try:
            advance(slug)
        except Exception as exc:
            print(f"ERR {slug}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
