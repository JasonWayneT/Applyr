#!/usr/bin/env python3
"""Create Applyr's isolated .venv and install Python deps + Playwright Chromium."""
from __future__ import annotations

import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"


def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _bootstrap_interpreter() -> list[str]:
    """Pick a host Python that is not Hermes (Windows: py launcher)."""
    if sys.platform == "win32" and shutil.which("py"):
        return ["py", "-3"]
    host = Path(sys.executable)
    if "hermes" in str(host).lower():
        for candidate in ("python3", "python"):
            found = shutil.which(candidate)
            if found and "hermes" not in found.lower():
                return [found]
        raise SystemExit(
            "Cannot bootstrap Applyr venv: current Python is Hermes and no py/python3 fallback found.\n"
            "Install Python 3.10+ from python.org, then re-run: npm run setup:python"
        )
    return [str(host)]


def main() -> int:
    if not REQUIREMENTS.exists():
        print(f"Missing {REQUIREMENTS}", file=sys.stderr)
        return 1

    if not VENV_DIR.exists():
        print(f"Creating {VENV_DIR} ...")
        bootstrap = _bootstrap_interpreter()
        subprocess.check_call([*bootstrap, "-m", "venv", str(VENV_DIR)])

    python = _venv_python()
    if not python.exists():
        print(f"Venv creation failed: {python} not found", file=sys.stderr)
        return 1

    print(f"Installing requirements into {python} ...")
    subprocess.check_call([str(python), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])

    print("Installing Playwright Chromium for PDF compile ...")
    subprocess.check_call([str(python), "-m", "playwright", "install", "chromium"])

    print(f"\nApplyr Python ready:\n  {python}")
    print("Restart `npm run dev` so the server picks up .venv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
