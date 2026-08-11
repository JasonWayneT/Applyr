#!/usr/bin/env python3
"""
Tests for scripts/check_finalize_ready.py (CR-078).

Invokes the script as a real subprocess (not importing its functions directly) -- this is the
exact boundary server/routes/jobs/files.ts crosses via runPythonScript(), so a test that only
imports contracts.check_finalize_ready() wouldn't actually prove the CLI/JSON contract works.
The specific scenario this exists to prove: a draft_manifest.json with a forged/stale
verification_passed=true, unaccompanied by a real passing verification_receipt.json, is
correctly rejected -- CR-078's Delta 3 fix (see CR-078-remove-agent-completion-authority.md).

Run with:
    python scripts/test_check_finalize_ready.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPT_PATH = os.path.join(_SCRIPT_DIR, "check_finalize_ready.py")

_VALID_MANIFEST: dict = {
    "company": "TestCo",
    "title": "Product Manager",
    "verification_passed": True,
    "rubric_score": {
        "resume": {"total": 78},
        "cover_letter": {"total": 70},
    },
}

_VALID_RECEIPT: dict = {
    "submission": "TestCo",
    "mechanically_verified": True,
    "lint_all_clean": True,
    "unapproved_metrics_clean": True,
    "page_counts_ok": True,
    "check_resume": {"passed": True},
    "check_cover_letter": {"passed": True},
}


def _run(folder: str) -> tuple[int, dict]:
    result = subprocess.run(
        [sys.executable, _SCRIPT_PATH, folder],
        capture_output=True,
        text=True,
        timeout=30,
    )
    parsed = json.loads(result.stdout.strip())
    return result.returncode, parsed


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestCheckFinalizeReady(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)
        (self.folder / "Resume.md").write_text("# Resume\n", encoding="utf-8")
        (self.folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_folder_fails_closed(self):
        code, parsed = _run(str(self.folder / "does_not_exist"))
        self.assertEqual(code, 1)
        self.assertFalse(parsed["ok"])
        self.assertTrue(parsed["errors"])

    def test_forged_manifest_with_no_receipt_is_rejected(self):
        """The exact Delta 3 vulnerability: verification_passed=true with nothing backing it."""
        _write_json(self.folder / "draft_manifest.json", _VALID_MANIFEST)
        # No verification_receipt.json at all -- a hand-authored/forged manifest.
        code, parsed = _run(str(self.folder))
        self.assertEqual(code, 1)
        self.assertFalse(parsed["ok"])
        self.assertTrue(any("not found" in e for e in parsed["errors"]))

    def test_forged_manifest_with_failing_receipt_is_rejected(self):
        """Manifest says passed=true; the real receipt underneath says otherwise -- must lose."""
        _write_json(self.folder / "draft_manifest.json", _VALID_MANIFEST)
        bad_receipt = dict(_VALID_RECEIPT)
        bad_receipt["mechanically_verified"] = False
        _write_json(self.folder / "verification_receipt.json", bad_receipt)
        code, parsed = _run(str(self.folder))
        self.assertEqual(code, 1)
        self.assertFalse(parsed["ok"])

    def test_genuinely_passing_folder_is_accepted(self):
        _write_json(self.folder / "draft_manifest.json", _VALID_MANIFEST)
        _write_json(self.folder / "verification_receipt.json", _VALID_RECEIPT)
        code, parsed = _run(str(self.folder))
        self.assertEqual(code, 0)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["errors"], [])

    def test_stale_receipt_older_than_resume_is_rejected(self):
        """Even a mechanically-clean receipt loses if Resume.md changed since it was written."""
        _write_json(self.folder / "draft_manifest.json", _VALID_MANIFEST)
        _write_json(self.folder / "verification_receipt.json", _VALID_RECEIPT)
        # Touch Resume.md after the receipt so its mtime is newer (no content_hashes on this
        # legacy-shaped receipt, so check_freshness falls back to the mtime comparison).
        import time

        time.sleep(0.05)
        (self.folder / "Resume.md").write_text("# Resume (edited)\n", encoding="utf-8")
        code, parsed = _run(str(self.folder))
        self.assertEqual(code, 1)
        self.assertFalse(parsed["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
