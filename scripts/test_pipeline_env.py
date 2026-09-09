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
    """2026-09-01, Jason-directed: flipped to on-by-default after live testing
    against real archived opportunities confirmed the cascade stays cloud-first
    (Groq then Gemini, no local model calls) for required/preferred gap
    classification. STAGE0_EVIDENCE_CASCADE=0 stays as the rollback path."""

    def test_defaults_on_when_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STAGE0_EVIDENCE_CASCADE", None)
            self.assertTrue(pipeline_env.stage0_evidence_cascade_enabled())

    def test_explicit_zero_opts_out(self) -> None:
        with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "0"}):
            self.assertFalse(pipeline_env.stage0_evidence_cascade_enabled())

    def test_explicit_false_opts_out(self) -> None:
        with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "false"}):
            self.assertFalse(pipeline_env.stage0_evidence_cascade_enabled())

    def test_explicit_one_stays_enabled(self) -> None:
        with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "1"}):
            self.assertTrue(pipeline_env.stage0_evidence_cascade_enabled())


if __name__ == "__main__":
    unittest.main()
