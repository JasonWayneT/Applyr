#!/usr/bin/env python3
"""Move Stage 0 folders out of submissions after a Skip / into submissions after PASS.

# Implements FR-264 / CR-091
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage0_skip_ledger import clear_skip, record_skip
from utils import move_folder_robust  # noqa: E402

_SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = _SCRIPT_DIR.parent

PENDING_DIR = REPO_ROOT / "data" / "pending_review"
SUBMISSIONS_DIR = REPO_ROOT / "data" / "submissions"
SKIPPED_DIR = REPO_ROOT / "data" / "archive" / "skipped"


def _is_under(folder: Path, root: Path) -> bool:
    """True if folder is root or a descendant of root."""
    try:
        folder.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def managed_folder(folder: Path) -> bool:
    """True when this folder lives in pending_review or submissions (not tmp tests)."""
    folder = Path(folder)
    return _is_under(folder, PENDING_DIR) or _is_under(folder, SUBMISSIONS_DIR)


def _unique_dest(parent: Path, slug: str) -> Path:
    """Return parent/slug, or parent/slug_YYYYMMDDTHHMMSS if taken."""
    dest = parent / slug
    if not dest.exists():
        return dest
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    return parent / f"{slug}_{stamp}"


def move_folder(src: Path, dest: Path) -> Path:
    """Move src to dest. Dest parent is created. Returns dest.

    CR-092 (2026-08-15): a plain shutil.move() failed with PermissionError on
    two real submission folders this session (transient Windows file lock
    somewhere under the tree). move_folder_robust() retries the rename with
    backoff, then falls back to copy+delete -- same recovery this exact
    failure needed by hand once already."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    return Path(move_folder_robust(src, dest))


def apply_stage0_placement(
    folder: Path | str,
    result: dict[str, Any],
    *,
    mode: str = "production",
    db_path: Path | str | None = None,
) -> Path:
    """Record/clear the skip ledger and move the folder when it is a managed path.

    Production Skip → ledger + data/archive/skipped/{slug}.
    Production PASS from pending_review → data/submissions/{slug}.
    Practice mode and unmanaged (temp) folders: no ledger write, no move.
    """
    folder = Path(folder)
    decision = (result.get("decision") or "").upper()
    company = result.get("company") or folder.name
    title = result.get("role") or ""
    url = result.get("url")
    reason = result.get("skip_reason") or result.get("notes") or "Stage 0 Skip"

    if mode == "practice" or not managed_folder(folder):
        return folder

    if decision == "SKIP":
        SKIPPED_DIR.mkdir(parents=True, exist_ok=True)
        dest = _unique_dest(SKIPPED_DIR, folder.name)
        moved = move_folder(folder, dest)
        record_skip(
            url=url,
            company=company,
            title=title,
            skip_reason=str(reason),
            slug=folder.name,
            archive_path=str(moved),
            db_path=db_path,
        )
        return moved

    if decision == "PASS":
        clear_skip(url=url, company=company, title=title, db_path=db_path)
        if _is_under(folder, PENDING_DIR):
            SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
            dest = _unique_dest(SUBMISSIONS_DIR, folder.name)
            return move_folder(folder, dest)
        return folder

    return folder
