#!/usr/bin/env python3
"""Tests for scripts/archive_submission.py's stale-PDF warning (CR-092
follow-up, 2026-08-15) -- see _warn_if_pdfs_stale's own docstring for why
this is a WARN, not a forced recompile or a block."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from archive_submission import _warn_if_pdfs_stale


class TestWarnIfPdfsStale(unittest.TestCase):

    def _make_folder(self, tmp: str, pdf_bytes: bytes, receipt_hash: str | None) -> str:
        folder = os.path.join(tmp, "testco")
        os.makedirs(os.path.join(folder, "stage_receipts"))
        with open(os.path.join(folder, "Resume.pdf"), "wb") as f:
            f.write(pdf_bytes)
        if receipt_hash is not None:
            receipt = {"output_hashes": {"Resume.pdf": receipt_hash}}
            with open(os.path.join(folder, "stage_receipts", "stage2.json"), "w") as f:
                json.dump(receipt, f)
        return folder

    def test_mismatched_hash_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._make_folder(tmp, b"actual content", "0" * 64)
            buf = StringIO()
            with redirect_stdout(buf):
                _warn_if_pdfs_stale(folder)
            self.assertIn("WARNING", buf.getvalue())
            self.assertIn("Resume.pdf", buf.getvalue())

    def test_matching_hash_stays_silent(self):
        import hashlib
        content = b"actual content"
        real_hash = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            folder = self._make_folder(tmp, content, real_hash)
            buf = StringIO()
            with redirect_stdout(buf):
                _warn_if_pdfs_stale(folder)
            self.assertEqual(buf.getvalue(), "")

    def test_no_receipt_stays_silent_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "testco")
            os.makedirs(folder)
            buf = StringIO()
            with redirect_stdout(buf):
                _warn_if_pdfs_stale(folder)  # must not raise
            self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
