#!/usr/bin/env python3
"""Tests for scripts/playwright_env.py — no browser launch."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright_env import (
    chromium_install_ready,
    ensure_playwright_browsers_env,
    resolve_playwright_browsers_path,
)


class PlaywrightEnvTests(unittest.TestCase):
    def test_ready_when_chromium_dir_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "chromium_headless_shell-1228").mkdir()
            self.assertTrue(chromium_install_ready(tmp))

    def test_not_ready_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(chromium_install_ready(tmp))

    def test_prefers_stable_install_over_sandbox_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            stable = Path(tmp) / "Local" / "ms-playwright"
            sandbox = Path(tmp) / "cursor-sandbox-cache" / "hash" / "playwright"
            (stable / "chromium-1228").mkdir(parents=True)
            sandbox.mkdir(parents=True)
            env = {
                "LOCALAPPDATA": str(Path(tmp) / "Local"),
                "PLAYWRIGHT_BROWSERS_PATH": str(sandbox),
            }
            chosen = resolve_playwright_browsers_path(env)
            self.assertEqual(Path(chosen), stable)

    def test_drops_broken_sandbox_when_stable_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = Path(tmp) / "cursor-sandbox-cache" / "hash" / "playwright"
            sandbox.mkdir(parents=True)
            env = {
                "LOCALAPPDATA": str(Path(tmp) / "Local"),
                "USERPROFILE": tmp,
                "PLAYWRIGHT_BROWSERS_PATH": str(sandbox),
            }
            chosen = ensure_playwright_browsers_env(env)
            self.assertIsNone(chosen)
            self.assertNotIn("PLAYWRIGHT_BROWSERS_PATH", env)


if __name__ == "__main__":
    unittest.main(verbosity=2)
