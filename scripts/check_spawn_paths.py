#!/usr/bin/env python3
"""
CI guard: python spawns in server/ must use SCRIPTS_DIR or documented allowlist (CR-ARCH-001).

Implements spawn inventory CR-ARCH-000 exceptions S06, S10.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_DIR = PROJECT_ROOT / "server"

# Lines matching these are OK without SCRIPTS_DIR on the same line
ALLOW_LINE_PATTERNS = [
    re.compile(r"path\.join\s*\(\s*SCRIPTS_DIR"),
    re.compile(r"runPythonScript\s*\("),
    re.compile(r"['\"]scripts/batch_pipeline\.py['\"]"),
    re.compile(r"['\"]scripts/generate_experience_summary\.py['\"]"),
    # runPythonScript passes absolute paths in args (middleware.ts)
    re.compile(r"spawn\s*\(\s*['\"]python['\"],\s*args"),
    # Manual draft — procArgs built with path.join(SCRIPTS_DIR, 'batch_pipeline.py') (jobs.ts)
    re.compile(r"spawn\s*\(\s*['\"]python['\"],\s*procArgs"),
    re.compile(r"spawnPython\s*\("),
]

SPAWN_PATTERN = re.compile(r"""spawn\s*\(\s*['"]python['"]""")


def line_allowed(line: str) -> bool:
    return any(p.search(line) for p in ALLOW_LINE_PATTERNS)


def main() -> int:
    violations: list[str] = []
    for path in sorted(SERVER_DIR.rglob("*.ts")):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if SPAWN_PATTERN.search(line) and not line_allowed(line):
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{i}: {line.strip()}")

    if violations:
        print("SPAWN CHECK FAILED — use path.join(SCRIPTS_DIR, ...) or allowlisted paths:")
        for v in violations:
            print(f"  {v}")
        return 1

    print(f"SPAWN CHECK OK ({len(list(SERVER_DIR.rglob('*.ts')))} files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
