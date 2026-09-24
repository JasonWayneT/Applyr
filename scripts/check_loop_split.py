"""Rebuild the F2 draw and compare it to docs/loop/STATE.json.

Uses folder names and file sizes only. Does not open job text.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_ARCHIVE = _ROOT / "data" / "archive" / "submissions"
_STATE = _ROOT / "docs" / "loop" / "STATE.json"
_RESERVED = (
    "1uphealth",
    "candor_health",
    "classlink",
    "curinos",
    "dropbox",
    "highmark_health",
    "keyfactor",
    "makai_labs",
    "massive_bio",
    "medrisk",
    "medrisk_2",
    "nisum",
    "obie_2",
    "rex_zone",
    "securitize",
    "sourcegraph_2",
    "torentify",
    "very_good_security",
)


def draw(seed: int = 20260923) -> tuple[list[str], list[str]]:
    """Return (dev slugs, holdout slugs) for the recorded seed."""
    eligible = sorted(
        path.name
        for path in _ARCHIVE.iterdir()
        if path.is_dir()
        and "_backup_" not in path.name
        and (path / "Original_JD.txt").is_file()
        and (path / "Original_JD.txt").stat().st_size >= 1500
    )
    pool = [slug for slug in eligible if slug not in _RESERVED]
    random.Random(seed).shuffle(pool)
    holdout = sorted(pool[:60])
    dev = sorted(set(eligible) - set(holdout))
    return dev, holdout


def main() -> int:
    """Print MATCH when STATE.json still equals the frozen draw."""
    dev, holdout = draw()
    state = json.loads(_STATE.read_text(encoding="utf-8"))
    ok = state.get("dev_slugs") == dev and state.get("holdout_slugs") == holdout
    print("MATCH" if ok else "MISMATCH")
    print(f"dev {len(dev)} holdout {len(holdout)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
