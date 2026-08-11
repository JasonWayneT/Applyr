#!/usr/bin/env python3
"""
CR-075 Story 5.4 / AC8: check_submission_status.py report-shape regression.

Confirms the status oracle still emits the same check names, PASS/FAIL/WARN lines,
STATUS: DONE|INCOMPLETE, and exit codes. Epic 2's hash-aware freshness may change
*results* for a given folder; this test locks the *shape*, not pass/fail outcomes.
No new gate is added to check_submission_status.py (explicit Out of Scope).

Run with:
    .venv\\Scripts\\python.exe -m unittest scripts.test_check_submission_status -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).parent / "check_submission_status.py"

# Exact check-name strings compute_status / _print_report emit today.
_EXPECTED_NAME_PREFIXES = (
    "Resume.md exists",
    "CoverLetter.md exists",
    "Resume.pdf compiled",
    "CoverLetter.pdf compiled",
    "stage0_fit_gate.json",
    "verification_receipt.json",
    "draft_manifest.json",
)


class TestCheckSubmissionStatusShape(unittest.TestCase):
    def _run(self, folder: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_SCRIPT), str(folder)],
            capture_output=True,
            text=True,
        )

    def test_incomplete_folder_shape_and_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "emptyco"
            folder.mkdir()
            result = self._run(folder)
            self.assertEqual(result.returncode, 1)
            out = result.stdout
            self.assertIn("STATUS: INCOMPLETE", out)
            for prefix in _EXPECTED_NAME_PREFIXES:
                self.assertRegex(out, rf"\[(PASS|FAIL)\] {prefix}")
            # Line shape: "  [PASS|FAIL] name". [WARN] and [INFO] (CR-078's additive
            # workflow-authority line, never folded into checks/done -- see compute_status)
            # are the two exempt prefixes, not new gates.
            for line in out.splitlines():
                if (
                    line.startswith("  [")
                    and "STATUS" not in line
                    and not line.startswith("  [WARN]")
                    and not line.startswith("  [INFO]")
                ):
                    self.assertRegex(line, r"^  \[(PASS|FAIL)\] .+")

    def test_passing_folder_shape_and_exit_0(self):
        """Build a minimal folder that clears every check_submission_status predicate."""
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "passco"
            folder.mkdir()
            resume = "# Name\n\n## PROFESSIONAL SUMMARY\n\nA. B. C.\n"
            cover = "# Name\n\nDear Hiring Manager,\n\nBody.\n\nBest regards,\n\nName\n"
            (folder / "Resume.md").write_text(resume, encoding="utf-8", newline="\n")
            (folder / "CoverLetter.md").write_text(cover, encoding="utf-8", newline="\n")
            (folder / "Resume.pdf").write_bytes(b"%PDF-1.4 minimal")
            (folder / "CoverLetter.pdf").write_bytes(b"%PDF-1.4 minimal")
            (folder / "stage0_fit_gate.json").write_text(
                json.dumps(
                    {
                        "company": "PassCo",
                        "required": ["x"],
                        "preferred": [],
                        "responsibilities": ["y"],
                        "flagged_gaps": [],
                        "stage_signal": "unknown",
                        "thin_jd": False,
                    }
                ),
                encoding="utf-8",
            )
            # Hash the on-disk bytes (same as contracts._sha256_hex / verify_submission).
            resume_hash = hashlib.sha256((folder / "Resume.md").read_bytes()).hexdigest()
            cover_hash = hashlib.sha256((folder / "CoverLetter.md").read_bytes()).hexdigest()
            (folder / "verification_receipt.json").write_text(
                json.dumps(
                    {
                        "submission": "passco",
                        "mechanically_verified": True,
                        "lint_all_clean": True,
                        "unapproved_metrics_clean": True,
                        "page_counts_ok": True,
                        "check_resume": {"passed": True},
                        "check_cover_letter": {"passed": True},
                        "content_hashes": {
                            "algorithm": "sha256",
                            "Resume.md": resume_hash,
                            "CoverLetter.md": cover_hash,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (folder / "draft_manifest.json").write_text(
                json.dumps(
                    {
                        "company": "PassCo",
                        "title": "Product Manager",
                        "verification_passed": True,
                        "rubric_score": {
                            "resume": {"total": 75},
                            "cover_letter": {"total": 70},
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = self._run(folder)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("STATUS: DONE", result.stdout)
            for prefix in _EXPECTED_NAME_PREFIXES:
                self.assertRegex(result.stdout, rf"\[PASS\] {prefix}")


class TestCr078WorkflowAuthorityInfo(unittest.TestCase):
    """CR-078 AC-302/303: workflow-authority status is additive info only, never a new gate."""

    def _run(self, folder: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(_SCRIPT), str(folder)],
            capture_output=True,
            text=True,
        )

    def test_no_workflow_state_shows_not_adopted_and_does_not_affect_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "legacyco"
            folder.mkdir()
            # Deliberately empty (INCOMPLETE) -- proves the INFO line appears either way and
            # never changes the exit code / DONE-INCOMPLETE verdict on its own.
            result = self._run(folder)
            self.assertEqual(result.returncode, 1)
            self.assertIn("STATUS: INCOMPLETE", result.stdout)
            self.assertIn("workflow-authority (CR-076+): not yet adopted", result.stdout)

    def test_adopted_folder_shows_status_without_gating_done(self):
        """A folder with a workflow_state.json that is NOT check_workflow_complete must still
        be reported DONE if the existing (unchanged) checks all pass -- proves the new field
        is informational, not folded into `done`."""
        import hashlib

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "adoptedco"
            folder.mkdir()
            resume = "# Name\n\n## PROFESSIONAL SUMMARY\n\nA. B. C.\n"
            cover = "# Name\n\nDear Hiring Manager,\n\nBody.\n\nBest regards,\n\nName\n"
            (folder / "Resume.md").write_text(resume, encoding="utf-8", newline="\n")
            (folder / "CoverLetter.md").write_text(cover, encoding="utf-8", newline="\n")
            (folder / "Resume.pdf").write_bytes(b"%PDF-1.4 minimal")
            (folder / "CoverLetter.pdf").write_bytes(b"%PDF-1.4 minimal")
            (folder / "stage0_fit_gate.json").write_text(
                json.dumps(
                    {
                        "company": "AdoptedCo",
                        "required": ["x"],
                        "preferred": [],
                        "responsibilities": ["y"],
                        "flagged_gaps": [],
                        "stage_signal": "unknown",
                        "thin_jd": False,
                    }
                ),
                encoding="utf-8",
            )
            resume_hash = hashlib.sha256((folder / "Resume.md").read_bytes()).hexdigest()
            cover_hash = hashlib.sha256((folder / "CoverLetter.md").read_bytes()).hexdigest()
            (folder / "verification_receipt.json").write_text(
                json.dumps(
                    {
                        "submission": "adoptedco",
                        "mechanically_verified": True,
                        "lint_all_clean": True,
                        "unapproved_metrics_clean": True,
                        "page_counts_ok": True,
                        "check_resume": {"passed": True},
                        "check_cover_letter": {"passed": True},
                        "content_hashes": {
                            "algorithm": "sha256",
                            "Resume.md": resume_hash,
                            "CoverLetter.md": cover_hash,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (folder / "draft_manifest.json").write_text(
                json.dumps(
                    {
                        "company": "AdoptedCo",
                        "title": "Product Manager",
                        "verification_passed": True,
                        "rubric_score": {
                            "resume": {"total": 75},
                            "cover_letter": {"total": 70},
                        },
                    }
                ),
                encoding="utf-8",
            )
            # Present but deliberately mid-flight -- not COMPLETE/COMPLETE_WITH_OVERRIDE, so
            # check_workflow_complete() must be False even though `done` (old checks) is True.
            (folder / "workflow_state.json").write_text(
                json.dumps({"status": "WAITING_FOR_LLM", "mode": "production", "stages": {}}),
                encoding="utf-8",
            )

            result = self._run(folder)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("STATUS: DONE", result.stdout)
            self.assertIn("workflow-authority (CR-076+): status=WAITING_FOR_LLM", result.stdout)
            self.assertIn("check_workflow_complete=NO", result.stdout)


if __name__ == "__main__":
    unittest.main()
