"""Resolve a Playwright browsers directory that actually contains Chromium.

Cursor's agent sandbox sets PLAYWRIGHT_BROWSERS_PATH to
%TEMP%\\cursor-sandbox-cache\\<hash>\\playwright. That cache is often missing
chrome-headless-shell.exe, so PDF compile fails even though Chromium is
already installed at %USERPROFILE%\\AppData\\Local\\ms-playwright.

Call ensure_playwright_browsers_env() before sync_playwright() / chromium.launch().
"""
from __future__ import annotations

import os
from typing import Mapping

_SANDBOX_MARKER = "cursor-sandbox-cache"


def _is_sandbox_cache(path: str) -> bool:
    return _SANDBOX_MARKER in path.replace("\\", "/").lower()


def chromium_install_ready(root: str | None) -> bool:
    """True when *root* looks like a Playwright browsers dir with Chromium."""
    if not root or not os.path.isdir(root):
        return False
    try:
        names = os.listdir(root)
    except OSError:
        return False
    return any(name.startswith("chromium") for name in names)


def default_ms_playwright_dir(environ: Mapping[str, str] | None = None) -> str:
    env = environ if environ is not None else os.environ
    local = env.get("LOCALAPPDATA") or ""
    if local:
        return os.path.join(local, "ms-playwright")
    home = env.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, "AppData", "Local", "ms-playwright")


def resolve_playwright_browsers_path(
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return a Chromium-ready browsers dir, or None to unset the env var.

    Prefers the durable user install over a Cursor sandbox cache.
    """
    env = environ if environ is not None else os.environ
    stable = default_ms_playwright_dir(env)
    if chromium_install_ready(stable):
        return os.path.normpath(stable)

    current = (env.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip()
    if (
        current
        and current != "0"
        and not _is_sandbox_cache(current)
        and chromium_install_ready(current)
    ):
        return os.path.normpath(current)

    return None


def ensure_playwright_browsers_env(
    environ: dict[str, str] | None = None,
) -> str | None:
    """Point PLAYWRIGHT_BROWSERS_PATH at a real Chromium install.

    Returns the path that was set, or None if the var was cleared so Playwright
    can use its own default.
    """
    env = os.environ if environ is None else environ
    chosen = resolve_playwright_browsers_path(env)
    if chosen:
        env["PLAYWRIGHT_BROWSERS_PATH"] = chosen
        return chosen
    env.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    return None
