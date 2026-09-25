#!/usr/bin/env python3
"""Tests for scripts/pipeline_env.py flag defaults."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pipeline_env  # noqa: E402


class TestStage0EvidenceCascadeDefault(unittest.TestCase):
    """CR-108 Epic 7.7 (2026-09-09): the cascade is now always on — the legacy
    per-line classifier was removed and the STAGE0_EVIDENCE_CASCADE env var
    no longer has any effect. The function is retained for call-site
    compatibility but always returns True."""

    def test_always_on_when_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STAGE0_EVIDENCE_CASCADE", None)
            self.assertTrue(pipeline_env.stage0_evidence_cascade_enabled())

    def test_always_on_when_zero(self) -> None:
        with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "0"}):
            self.assertTrue(pipeline_env.stage0_evidence_cascade_enabled())

    def test_always_on_when_false(self) -> None:
        with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "false"}):
            self.assertTrue(pipeline_env.stage0_evidence_cascade_enabled())

    def test_always_on_when_one(self) -> None:
        with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "1"}):
            self.assertTrue(pipeline_env.stage0_evidence_cascade_enabled())


if __name__ == "__main__":
    unittest.main()
