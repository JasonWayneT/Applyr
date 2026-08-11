"""Warn when a CR-074 worker is invoked as a direct CLI entry point.

Canonical progression/completion path is ``scripts/run_submission.py`` (CR-076–084).
Workers remain callable for debug and are still used *by* the orchestrator.
"""
from __future__ import annotations

import os
import sys


def warn_worker_cli(script_basename: str) -> None:
    """Print a stderr note unless APPLYR_QUIET_WORKER_WARN=1 (orchestrator / tests)."""
    if os.environ.get("APPLYR_QUIET_WORKER_WARN", "").strip() in ("1", "true", "yes"):
        return
    print(
        f"NOTE: {script_basename} is a worker under scripts/run_submission.py "
        "(CR-076-084). Prefer: python scripts/run_submission.py <folder> "
        "[--resume|--finalize|--status]. Direct CLI use is for debug only.",
        file=sys.stderr,
    )
