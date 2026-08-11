#!/usr/bin/env python3
"""
Regression test for verify_editor_save.py's CLI argv contract.

Why this exists (2026-08-09): server/routes/jobs/files.ts's PUT /api/jobs/:id/files/:filename
route calls this script as `runPythonScript([verifyScript, folder, safeFilename], {stdin: text})`
-- exactly 2 real arguments plus the script name, sys.argv length 3. The script's own
`if __name__ == "__main__"` block checked `len(sys.argv) < 4`, an off-by-one against its only
real caller: every manual editor save through the Applyr UI 400'd with a "Usage: ..." message
before the document was ever written to disk. Confirmed live against a real job (Camunda) during
CR-078 verification, confirmed via git status that this file was untouched by any of that CR's
own changes -- a pre-existing bug, unrelated to CR-078, fixed here on its own.

This test only guards the CLI argv boundary (the actual bug), not the full audit/tone/hard-fact
logic inside verify_editor_save() itself -- that's exercised elsewhere via smoke_draft_compiler.py
and the function's own callers.

Run with:
    python scripts/test_verify_editor_save.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPT_PATH = os.path.join(_SCRIPT_DIR, "verify_editor_save.py")


class TestVerifyEditorSaveCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_too_few_args_still_shows_usage(self):
        """Only <folder>, no <filename> -- argv length 2, correctly rejected."""
        result = subprocess.run(
            [sys.executable, _SCRIPT_PATH, str(self.folder)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stdout)

    def test_real_caller_arg_count_does_not_hit_usage_error(self):
        """The exact shape files.ts sends: [folder, filename], text via stdin, argv length 3.

        This is the regression case: before the fix this always printed the Usage message and
        exited 2 regardless of stdin content, because the check required argv length 4. It must
        now actually reach verify_editor_save() -- proven by getting exit 0 or 1 (a real
        verification verdict), never the Usage/exit-2 path.
        """
        result = subprocess.run(
            [sys.executable, _SCRIPT_PATH, str(self.folder), "Resume.md"],
            input="# Some Resume\n\nSome body text.\n",
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 2, f"hit the Usage/argv-count path: {result.stdout}")
        self.assertNotIn("Usage:", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
