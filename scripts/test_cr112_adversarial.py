#!/usr/bin/env python3
"""CR-112 Epic 4 — adversarial runner honesty."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_adversarial_pressure_test as adv


class TestUnhandledFixtureFailsClosed(unittest.TestCase):
    def test_unknown_fixture_name_never_passes(self) -> None:
        """Implements FR-307 / AC-404."""
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case_mystery"
            case_dir.mkdir()
            (case_dir / "case_meta.json").write_text(
                json.dumps({"name": "case_mystery", "invariant_id": "DOC-099"}),
                encoding="utf-8",
            )
            with self.assertRaises(AssertionError) as ctx:
                adv.run_fixture_case(case_dir)
            self.assertIn("unhandled fixture name", str(ctx.exception))
            self.assertIn("DOC-099", str(ctx.exception))

    def test_missing_meta_is_not_a_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "empty_dir"
            case_dir.mkdir()
            self.assertIsNone(adv.run_fixture_case(case_dir))

    def test_stale_hash_fixture_is_skipped_as_programmatic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "case_stale_hash"
            case_dir.mkdir()
            (case_dir / "case_meta.json").write_text(
                json.dumps({"name": "case_stale_hash", "invariant_id": "STATE-003"}),
                encoding="utf-8",
            )
            res = adv.run_fixture_case(case_dir)
            self.assertEqual(res["status"], "SKIPPED")
            self.assertNotEqual(res["status"], "PASS")


class TestProgrammaticCasesPresent(unittest.TestCase):
    def test_named_invariant_cases_are_registered(self) -> None:
        """Implements FR-308 / FR-309."""
        for name in (
            "case_stale_hash",
            "case_downstream_no_receipt",
            "case_state_001_negative",
            "case_forbidden_punctuation",
            "case_doc_003_negative",
            "case_state_004_incomplete",
            "case_state_004_complete",
        ):
            self.assertIn(name, adv.CASES)

    def test_expect_workflow_error_requires_named_substring(self) -> None:
        class Boom(adv.runner.WorkflowError):
            pass

        def raise_other() -> None:
            raise Boom("some other precondition failed")

        with self.assertRaises(AssertionError) as ctx:
            adv.expect_workflow_error(
                raise_other,
                must_contain="Stage 0 receipt missing",
                invariant_id="STATE-001",
                context="unit",
            )
        self.assertIn("Stage 0 receipt missing", str(ctx.exception))
