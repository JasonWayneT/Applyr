"""
Mechanical freshness gate for data/agent_context_pack.md.

Why this has to be a hard check, not a prose reminder: this repo has already
seen prose-only rules fail to hold under real drafting pressure more than
once (LR-016 gap-confession language recurred in 5 of 11 letters despite
being stated twice in SKILL.md before it was hard-blocked in the linter;
--audit's duplicate-score detector exists because a bare "score it for real"
instruction alone did not stop a templated score from shipping). A stale
context pack is the same failure shape: nothing about "regenerate when a
source file changes" surviving as a comment in a doc, when a script can just
check it and refuse to proceed.

This script recomputes the sha256 of every source file listed in the pack's
embedded manifest and compares against the hashes recorded at generation
time. Any mismatch (or a missing pack) is a hard FAIL, not a warning.

Usage:
    python scripts/check_context_pack_freshness.py
    Exit code 0 + "FRESH" if every source file is unchanged since generation.
    Exit code 1 + "STALE" and the specific changed file(s) otherwise.
    Exit code 1 + a clear "not generated yet" message if the pack doesn't exist.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK_PATH = os.path.join(REPO_ROOT, "data", "agent_context_pack.md")

MANIFEST_RE = re.compile(
    r"<!-- CONTEXT_PACK_MANIFEST\s*(\{.*?\})\s*-->", re.DOTALL
)


def _sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def read_manifest(pack_path: str) -> dict:
    with open(pack_path, encoding="utf-8") as f:
        head = f.read(4096)
    m = MANIFEST_RE.search(head)
    if not m:
        raise ValueError(
            f"No CONTEXT_PACK_MANIFEST found in {pack_path} -- file exists but is not "
            "a valid generated pack. Regenerate with generate_context_pack.py."
        )
    return json.loads(m.group(1))


def check_freshness(pack_path: str = PACK_PATH) -> tuple[bool, list[str]]:
    """Returns (is_fresh, list_of_problem_messages)."""
    if not os.path.exists(pack_path):
        return False, [
            f"{pack_path} does not exist -- run `python scripts/generate_context_pack.py` first."
        ]

    manifest = read_manifest(pack_path)
    sources = manifest.get("sources", {})
    if not sources:
        return False, [f"Manifest in {pack_path} has no 'sources' entries -- malformed pack."]

    problems = []
    for rel_path, recorded_hash in sources.items():
        abs_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.exists(abs_path):
            problems.append(f"Source file listed in manifest no longer exists: {rel_path}")
            continue
        current_hash = _sha256(abs_path)
        if current_hash != recorded_hash:
            problems.append(
                f"{rel_path} has changed since the pack was generated "
                f"(recorded {recorded_hash[:12]}..., now {current_hash[:12]}...)"
            )

    return (len(problems) == 0), problems


def main() -> None:
    is_fresh, problems = check_freshness()
    if is_fresh:
        print("FRESH -- data/agent_context_pack.md matches its recorded sources.")
        sys.exit(0)
    else:
        print("STALE -- data/agent_context_pack.md is out of date or invalid:")
        for p in problems:
            print(f"  - {p}")
        print("\nRegenerate with: python scripts/generate_context_pack.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
