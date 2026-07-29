"""Tests for Applyr Python interpreter resolution (no Hermes / PATH fallback)."""
from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from applyr_python import ApplyrPythonError, assert_applyr_host, resolve_applyr_python

APPLYR_VENV = r"C:\Applyr\.venv\Scripts\python.exe"


class TestApplyrPython(unittest.TestCase):
    def test_rejects_hermes_via_applyr_python_env(self):
        with patch.dict(
            os.environ,
            {"APPLYR_PYTHON": r"C:\hermes\hermes-agent\venv\Scripts\python.exe"},
            clear=False,
        ):
            with self.assertRaises(ApplyrPythonError) as ctx:
                resolve_applyr_python()
            self.assertIn("Hermes", str(ctx.exception))

    def test_missing_venv_errors_without_path_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("APPLYR_PYTHON", None)
            with patch("applyr_python.os.path.isfile", return_value=False):
                with self.assertRaises(ApplyrPythonError) as ctx:
                    resolve_applyr_python()
                self.assertIn(".venv not found", str(ctx.exception))

    def test_assert_host_rejects_hermes(self):
        with patch("applyr_python.resolve_applyr_python", return_value=APPLYR_VENV):
            with patch.object(sys, "executable", r"C:\hermes\venv\Scripts\python.exe"):
                with self.assertRaises(ApplyrPythonError) as ctx:
                    assert_applyr_host()
                self.assertIn("Hermes", str(ctx.exception))

    def test_assert_host_rejects_mismatch(self):
        with patch("applyr_python.resolve_applyr_python", return_value=APPLYR_VENV):
            with patch.object(sys, "executable", r"C:\Python312\python.exe"):
                with self.assertRaises(ApplyrPythonError) as ctx:
                    assert_applyr_host()
                self.assertIn("wrong Python interpreter", str(ctx.exception))

    def test_assert_host_accepts_expected(self):
        with patch("applyr_python.resolve_applyr_python", return_value=APPLYR_VENV):
            with patch.object(sys, "executable", APPLYR_VENV):
                self.assertEqual(assert_applyr_host(), APPLYR_VENV)


if __name__ == "__main__":
    unittest.main()
