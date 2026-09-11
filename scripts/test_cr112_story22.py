#!/usr/bin/env python3
"""CR-112 Story 2.2 — tracked Claude batch runner must not load WE (FR-300 / AC-397)."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BATCH = _REPO / ".claude" / "workflows" / "generate-submission-batch.js"
_TRACKED = ".claude/workflows/generate-submission-batch.js"


def _review_prompt_fn(source: str) -> str:
    start = source.index("function reviewPrompt(")
    end = source.index("// 2026-08-06: defensive fix")
    return source[start:end]


class TestCr112Story22(unittest.TestCase):
    def setUp(self) -> None:
        self.source = _BATCH.read_text(encoding="utf-8")

    def test_tracked_batch_file_exists(self) -> None:
        self.assertTrue(_BATCH.is_file(), str(_BATCH))
        tracked = subprocess.check_output(
            ["git", "ls-files", "--", _TRACKED],
            cwd=_REPO,
            text=True,
        ).strip().replace("\\", "/")
        self.assertEqual(tracked, _TRACKED)

    def test_review_prompt_does_not_load_work_experience(self) -> None:
        """Implements FR-300 / AC-397."""
        review = _review_prompt_fn(self.source)
        self.assertIn("function reviewPrompt(", review)
        self.assertIn("Do not read data/workExperience.md", review)
        self.assertIn("authoring_packet.json", review)
        self.assertIn("claim_constraints", review)
        self.assertNotIn("Read data/workExperience.md", review)

    def test_when_to_use_is_never_default(self) -> None:
        self.assertIn("Never the default for routine", self.source)
        self.assertIn("run_submission.py", self.source)

    def test_company_cap_and_large_batch_opt_in_remain(self) -> None:
        self.assertIn("MAX_COMPANIES_PER_RUN = 3", self.source)
        self.assertIn("allowLargeBatch", self.source)

    def test_claude_primitives_kept_portable_rewrite_deferred(self) -> None:
        self.assertIn("harness-agnostic rewrite is deferred", self.source)
        self.assertIn("Workflow/agent/phase", self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
