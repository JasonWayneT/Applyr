#!/usr/bin/env python3
"""Pre-push audit: scan tracked files for PII patterns and gitignore leaks."""
from __future__ import annotations

import os
import re
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PII_PATTERNS = [
    ("email", re.compile(r"[a-zA-Z0-9_.+-]+@gmail\.com", re.I)),
    ("phone", re.compile(r"REDACTED_PHONE|\(760\)\s*317-8264")),
    ("linkedin", re.compile(r"linkedin\.com/in/redacted-linkedin-slug", re.I)),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("gemini_key", re.compile(r"AIzaSy[A-Za-z0-9_-]{30,}")),
]

BLOCKED_TRACKED_PREFIXES = (
    "data/archive/",
    "data/submissions/",
    "docs/reports/",
    "docs/legacy/",
    "data/workExperience.md",
    "data/Resume.md",
    "data/Cover_Letter_Reference.md",
    "data/Resume_Style_Reference.md",
    "data/application_question_bank.md",
    "data/bridge_phrases.json",
    "data/candidate_preferences.json",
    "data/master_claims.json",
    "data/workExperience_summary.md",
    "PRODUCT_CAPABILITIES.md",
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("audit_public_repo: not a git repo or git unavailable", file=sys.stderr)
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    files = tracked_files()
    if not files:
        return 1

    errors: list[str] = []

    for path in files:
        if path.startswith("data/submissions/") and path != "data/submissions/.gitkeep":
            errors.append(f"tracked path should be gitignored: {path}")
            continue
        for prefix in BLOCKED_TRACKED_PREFIXES:
            if path == prefix or path.startswith(prefix):
                errors.append(f"tracked path should be gitignored: {path}")
                break

    for rel in files:
        if rel in ("scripts/audit_public_repo.py", "scripts/pii_guard.py"):
            continue
        if not rel.endswith((".py", ".ts", ".tsx", ".md", ".json", ".txt", ".env", ".mjs")):
            continue
        abs_path = os.path.join(PROJECT_ROOT, rel)
        if not os.path.isfile(abs_path):
            continue
        try:
            text = open(abs_path, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for label, pattern in PII_PATTERNS:
            if pattern.search(text):
                errors.append(f"{label} match in tracked file: {rel}")

    if errors:
        print("PUBLIC REPO AUDIT FAILED")
        for err in sorted(set(errors)):
            print(f"  - {err}")
        return 1

    print(f"PUBLIC REPO AUDIT PASSED ({len(files)} tracked files scanned)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
