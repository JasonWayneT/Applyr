"""
Resolve Applyr's Python interpreter — never PATH `python` or Hermes.

Server spawns use server/domain/pythonBin.ts (same rules). Pipeline scripts must
call assert_applyr_host() at entry and resolve_applyr_python() for subprocesses.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if sys.platform == "win32":
    APPLYR_VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
else:
    APPLYR_VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

SETUP_HINT = "Run `npm run setup:python` from the Applyr project root."


class ApplyrPythonError(RuntimeError):
    """Applyr could not resolve a valid Python interpreter."""


def _norm(path: str | Path) -> str:
    try:
        return os.path.normcase(str(Path(path).resolve()))
    except OSError:
        return os.path.normcase(str(path))


def _reject_hermes(path: str) -> None:
    if "hermes" in path.lower():
        raise ApplyrPythonError(
            f"Refusing Hermes Python for Applyr: {path}\n{SETUP_HINT}"
        )


def resolve_applyr_python() -> str:
    """Return the Python binary Applyr must use (never bare PATH `python`)."""
    explicit = (os.environ.get("APPLYR_PYTHON") or "").strip()
    if explicit:
        _reject_hermes(explicit)
        if not os.path.isfile(explicit):
            raise ApplyrPythonError(
                f"APPLYR_PYTHON not found: {explicit}\n{SETUP_HINT}"
            )
        return explicit

    venv = str(APPLYR_VENV_PYTHON)
    if os.path.isfile(venv):
        _reject_hermes(venv)
        return venv

    raise ApplyrPythonError(
        f"Applyr Python environment missing (.venv not found at {venv}).\n"
        f"{SETUP_HINT}\n"
        "Do not run pipeline scripts with PATH `python` — use "
        "`node scripts/invoke_applyr_python.mjs <script.py>` or npm scripts."
    )


def assert_applyr_host() -> str:
    """
    Fail fast when the current process was not started with Applyr's interpreter.
    Call at pipeline entry points (batch_pipeline, import_csv_jobs, etc.).
    """
    expected = resolve_applyr_python()
    host = sys.executable
    _reject_hermes(host)

    if _norm(host) != _norm(expected):
        raise ApplyrPythonError(
            "Applyr pipeline started with the wrong Python interpreter.\n"
            f"  Current:  {host}\n"
            f"  Expected: {expected}\n"
            "This usually means PATH `python` points at another tool (e.g. Hermes).\n"
            f"{SETUP_HINT}\n"
            "Then run via: node scripts/invoke_applyr_python.mjs scripts/batch_pipeline.py --mode batch"
        )
    return host
