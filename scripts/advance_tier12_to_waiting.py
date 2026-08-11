#!/usr/bin/env python3
"""Advance all Tier 1/2 folders to WAITING_FOR_LLM (packet + prompt)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    t1 = (ROOT / "data/reports/tier1_slugs.txt").read_text().split()
    t2 = (ROOT / "data/reports/tier2_slugs.txt").read_text().split()
    slugs = t1 + t2
    print(f"Advancing {len(slugs)} folders to WAITING_FOR_LLM")
    ok, fail = [], []
    for slug in slugs:
        folder = ROOT / "data/submissions" / slug
        cmd = [
            sys.executable,
            str(ROOT / "scripts/run_submission.py"),
            str(folder),
            "--mode",
            "production",
            "--force",
            "--stop-at-waiting",
        ]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0 or "WAITING_FOR_LLM" in out:
            ok.append(slug)
            print(f"  OK {slug}")
        else:
            fail.append(slug)
            print(f"  FAIL {slug}: {out[-400:]}")
    print(f"done ok={len(ok)} fail={len(fail)}")
    if fail:
        (ROOT / "data/reports/packet_fail_slugs.txt").write_text("\n".join(fail) + "\n")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
