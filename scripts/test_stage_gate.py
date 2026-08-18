#!/usr/bin/env python3
"""
Tests for stage_gate.py (CR-075 Epic 4, Story 4.1).

Run with:
    .venv\\Scripts\\python.exe -m unittest scripts.test_stage_gate -v

No cloud LLM calls. Override log always writes to a temp path (never data/.force_override_log.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stage_gate  # noqa: E402
from stage_gate import (  # noqa: E402
    StageGateForceError,
    StageGateNotReadyError,
    add_force_args,
    log_force_override,
    parse_force_flags,
    require_stage_ready,
    validate_force,
)


def _write(folder: Path, name: str, content: str | dict) -> None:
    path = folder / name
    if isinstance(content, dict):
        path.write_text(json.dumps(content, indent=2), encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def _valid_stage0() -> dict:
    return {
        "company": "TestCo",
        "required": ["Define roadmap"],
        "preferred": [],
        "responsibilities": ["Ship features"],
        "flagged_gaps": [],
        "stage_signal": "unknown",
        "thin_jd": False,
    }


class StageGateTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.log_path = os.path.join(self._tmpdir.name, "force_override_log.json")
        self._prev_log = stage_gate.OVERRIDE_LOG_PATH
        stage_gate.OVERRIDE_LOG_PATH = self.log_path
        self.addCleanup(self._restore_log_path)

        self.folder = Path(self._tmpdir.name) / "testco"
        self.folder.mkdir()

    def _restore_log_path(self):
        stage_gate.OVERRIDE_LOG_PATH = self._prev_log

    def _read_log(self) -> list:
        if not os.path.exists(self.log_path):
            return []
        with open(self.log_path, encoding="utf-8") as f:
            return json.load(f)


# ---------------------------------------------------------------------------
# validate_force
# ---------------------------------------------------------------------------

class TestValidateForce(StageGateTestCase):
    def test_force_false_always_ok(self):
        for stage in ("stage0", "stage1", "stage2", "stage3"):
            validate_force(stage, False, None)
            validate_force(stage, False, "")

    def test_stage0_bare_force_ok(self):
        validate_force("stage0", True, None)

    def test_stage1_bare_force_ok(self):
        # Policy asymmetry at validate_force level; Story 4.3 simply never wires force for stage1.
        validate_force("stage1", True, None)

    def test_stage3_bare_force_ok(self):
        validate_force("stage3", True, None)

    def test_stage2_bare_force_rejected(self):
        with self.assertRaises(StageGateForceError) as ctx:
            validate_force("stage2", True, None)
        self.assertIn("force-reason", str(ctx.exception).lower())

    def test_stage2_empty_reason_rejected(self):
        with self.assertRaises(StageGateForceError):
            validate_force("stage2", True, "")
        with self.assertRaises(StageGateForceError):
            validate_force("stage2", True, "   ")

    def test_stage2_nonempty_reason_ok(self):
        validate_force("stage2", True, "re-score in progress, Jason approved")

    def test_unknown_stage_raises(self):
        with self.assertRaises(ValueError):
            validate_force("stage9", True, None)


# ---------------------------------------------------------------------------
# log_force_override
# ---------------------------------------------------------------------------

class TestLogForceOverride(StageGateTestCase):
    def test_creates_log_and_appends(self):
        self.assertFalse(os.path.exists(self.log_path))
        log_force_override("stage0", str(self.folder), None, argv=["prog", "--force"])
        log_force_override(
            "stage2",
            str(self.folder),
            "audit false positive",
            argv=["prog", "--force", "--force-reason", "audit false positive"],
        )
        records = self._read_log()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["stage"], "stage0")
        self.assertEqual(records[0]["reason"], "")
        self.assertEqual(records[0]["folder"], str(self.folder))
        self.assertIn("--force", records[0]["argv"])
        self.assertEqual(records[1]["stage"], "stage2")
        self.assertEqual(records[1]["reason"], "audit false positive")
        self.assertIn("timestamp", records[0])

    def test_never_writes_default_data_path(self):
        """Story 4.1: tests must not touch the real data/.force_override_log.json."""
        default = stage_gate._DEFAULT_OVERRIDE_LOG
        # Guaranteed by setUp pointing OVERRIDE_LOG_PATH at temp.
        self.assertNotEqual(self.log_path, default)
        log_force_override("stage0", str(self.folder), "x")
        self.assertTrue(os.path.exists(self.log_path))
        # If the default somehow already exists from a real run, we at least did not
        # append *this* test's folder into it -- assert our record is only in the temp log.
        records = self._read_log()
        self.assertEqual(records[-1]["folder"], str(self.folder))


# ---------------------------------------------------------------------------
# require_stage_ready
# ---------------------------------------------------------------------------

class TestRequireStageReady(StageGateTestCase):
    def test_stage0_passes_silently_when_ready(self):
        _write(self.folder, "stage0_fit_gate.json", _valid_stage0())
        require_stage_ready("stage0", str(self.folder))
        self.assertEqual(self._read_log(), [])

    def test_stage0_raises_itemized_when_missing(self):
        with self.assertRaises(StageGateNotReadyError) as ctx:
            require_stage_ready("stage0", str(self.folder))
        self.assertTrue(ctx.exception.errors)
        self.assertIn("stage0_fit_gate.json", str(ctx.exception))
        self.assertEqual(self._read_log(), [])

    def test_stage0_force_logs_and_proceeds(self):
        with self.assertRaises(StageGateNotReadyError):
            require_stage_ready("stage0", str(self.folder))
        require_stage_ready(
            "stage0",
            str(self.folder),
            force=True,
            argv=["build_authoring_packet.py", "--force"],
        )
        records = self._read_log()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["stage"], "stage0")

    def test_stage2_bare_force_rejected_before_check(self):
        with self.assertRaises(StageGateForceError):
            require_stage_ready("stage2", str(self.folder), force=True)
        self.assertEqual(self._read_log(), [])

    def test_stage2_force_with_reason_logs_and_proceeds(self):
        require_stage_ready(
            "stage2",
            str(self.folder),
            force=True,
            force_reason="Jason approved sending without rubric this once",
            argv=["verify_submission.py", "--force", "--force-reason", "Jason approved"],
        )
        records = self._read_log()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["reason"], "Jason approved sending without rubric this once")

    def test_stage1_ready_when_packet_and_docs_present(self):
        _write(
            self.folder,
            "authoring_packet.json",
            {
                "company": "TestCo",
                "packet_status": "ready",
                "incomplete_reasons": [],
            },
        )
        _write(self.folder, "Resume.md", "# Name\n")
        _write(self.folder, "CoverLetter.md", "# Name\n")
        # CR-092 (2026-08-15): claim_provenance.json's existence is now part
        # of the Stage 1 gate too (see test_contracts.py's equivalent fixture
        # update for the full reasoning).
        _write(self.folder, "claim_provenance.json", {"ran": True, "ok": True, "findings": []})
        require_stage_ready("stage1", str(self.folder))

    def test_stage1_raises_on_incomplete_packet(self):
        _write(
            self.folder,
            "authoring_packet.json",
            {
                "company": "TestCo",
                "packet_status": "incomplete",
                "incomplete_reasons": ["unmapped required: Foo"],
            },
        )
        _write(self.folder, "Resume.md", "# Name\n")
        _write(self.folder, "CoverLetter.md", "# Name\n")
        with self.assertRaises(StageGateNotReadyError) as ctx:
            require_stage_ready("stage1", str(self.folder))
        self.assertTrue(any("unmapped required" in e for e in ctx.exception.errors))


# ---------------------------------------------------------------------------
# add_force_args / parse_force_flags
# ---------------------------------------------------------------------------

class TestForceArgHelpers(StageGateTestCase):
    def test_add_force_args_stage0_has_force_only(self):
        parser = argparse.ArgumentParser()
        add_force_args(parser, "stage0")
        args = parser.parse_args([])
        self.assertFalse(args.force)
        self.assertFalse(hasattr(args, "force_reason"))
        args = parser.parse_args(["--force"])
        self.assertTrue(args.force)

    def test_add_force_args_stage2_has_both(self):
        parser = argparse.ArgumentParser()
        add_force_args(parser, "stage2")
        args = parser.parse_args(["--force", "--force-reason", "because"])
        self.assertTrue(args.force)
        self.assertEqual(args.force_reason, "because")

    def test_parse_force_flags_empty(self):
        self.assertEqual(parse_force_flags(["verify_submission.py", "data/submissions/x"]), (False, None))

    def test_parse_force_flags_force_only(self):
        self.assertEqual(
            parse_force_flags(["prog", "folder", "--force", "--audit"]),
            (True, None),
        )

    def test_parse_force_flags_force_reason_space(self):
        force, reason = parse_force_flags(
            ["prog", "folder", "--force", "--force-reason", "audit false positive"]
        )
        self.assertTrue(force)
        self.assertEqual(reason, "audit false positive")

    def test_parse_force_flags_force_reason_equals(self):
        force, reason = parse_force_flags(
            ["prog", "folder", "--force", "--force-reason=because"]
        )
        self.assertTrue(force)
        self.assertEqual(reason, "because")

    def test_parse_force_flags_reason_without_value_raises(self):
        with self.assertRaises(StageGateForceError):
            parse_force_flags(["prog", "--force-reason"])


# ---------------------------------------------------------------------------
# CR-075 Story 4.4 — finalize_submission_job logs Stage 3 --force overrides
# ---------------------------------------------------------------------------

class TestFinalizeStage3ForceLog(StageGateTestCase):
    def test_force_bypass_logs_stage3(self):
        from finalize_submission_job import NotReadyToFinalizeError, _require_ready
        import finalize_submission_job as fin

        # Point finalize at our temp folder layout: data/submissions/{slug}
        submissions = Path(self._tmpdir.name) / "submissions"
        submissions.mkdir()
        slug = "testco"
        (submissions / slug).mkdir()
        # Empty folder => check_finalize_ready fails

        prev_sub = fin._SUBMISSIONS_DIR
        fin._SUBMISSIONS_DIR = str(submissions)
        try:
            with self.assertRaises(NotReadyToFinalizeError):
                _require_ready(slug, force=False)
            self.assertEqual(self._read_log(), [])

            _require_ready(slug, force=True)
            records = self._read_log()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["stage"], "stage3")
            self.assertIn(slug, records[0]["folder"])
        finally:
            fin._SUBMISSIONS_DIR = prev_sub

    def test_force_when_already_ready_does_not_log(self):
        """Only log when force bypasses a *real* failure, not when the gate already passes."""
        from finalize_submission_job import _require_ready
        import finalize_submission_job as fin

        # If check_finalize_ready returns True, force should be a no-op for logging.
        with mock.patch.object(fin.contracts, "check_finalize_ready", return_value=(True, [])):
            _require_ready("anything", force=True)
        self.assertEqual(self._read_log(), [])

    def test_adopted_folder_without_stage2_receipt_blocks_finalize(self):
        """Workflow-adopted folders cannot DB-finalize on check_finalize_ready alone."""
        from finalize_submission_job import NotReadyToFinalizeError, _require_ready
        import finalize_submission_job as fin

        submissions = Path(self._tmpdir.name) / "submissions"
        submissions.mkdir(exist_ok=True)
        slug = "adoptedco"
        folder = submissions / slug
        folder.mkdir()
        (folder / "workflow_state.json").write_text(
            json.dumps({"status": "WAITING_FOR_LLM", "mode": "production"}),
            encoding="utf-8",
        )

        prev_sub = fin._SUBMISSIONS_DIR
        fin._SUBMISSIONS_DIR = str(submissions)
        try:
            with mock.patch.object(
                fin.contracts, "check_finalize_ready", return_value=(True, [])
            ):
                with self.assertRaises(NotReadyToFinalizeError) as ctx:
                    _require_ready(slug, force=False)
                self.assertIn("workflow authority", str(ctx.exception))
                self.assertIn("Stage 2", str(ctx.exception))

                _require_ready(slug, force=True)
                records = self._read_log()
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["stage"], "stage3")
        finally:
            fin._SUBMISSIONS_DIR = prev_sub


class TestApplyStage2Verdict(StageGateTestCase):
    """CR-075 Story 5.3 — binding vs mid-flow Stage 2 exit semantics."""

    def test_midflow_incomplete_does_not_bind(self):
        # No receipt, no rubric => INCOMPLETE but apply_stage2_verdict returns False (not binding).
        binding = stage_gate.apply_stage2_verdict(str(self.folder))
        self.assertFalse(binding)

    def test_rubric_present_incomplete_is_binding(self):
        _write(
            self.folder,
            "draft_manifest.json",
            {
                "company": "TestCo",
                "title": "PM",
                "verification_passed": False,
                "rubric_score": {
                    "resume": {"total": 72},
                    "cover_letter": {"total": 68},
                },
            },
        )
        binding = stage_gate.apply_stage2_verdict(str(self.folder))
        self.assertTrue(binding)

    def test_rubric_present_bare_force_raises(self):
        _write(
            self.folder,
            "draft_manifest.json",
            {
                "company": "TestCo",
                "title": "PM",
                "verification_passed": False,
                "rubric_score": {
                    "resume": {"total": 72},
                    "cover_letter": {"total": 68},
                },
            },
        )
        with self.assertRaises(StageGateForceError):
            stage_gate.apply_stage2_verdict(str(self.folder), force=True)

    def test_rubric_present_force_with_reason_logs_and_unbinds(self):
        _write(
            self.folder,
            "draft_manifest.json",
            {
                "company": "TestCo",
                "title": "PM",
                "verification_passed": False,
                "rubric_score": {
                    "resume": {"total": 72},
                    "cover_letter": {"total": 68},
                },
            },
        )
        binding = stage_gate.apply_stage2_verdict(
            str(self.folder),
            force=True,
            force_reason="Jason approved one-off send",
            argv=["verify_submission.py", "--force", "--force-reason", "Jason approved"],
        )
        self.assertFalse(binding)
        records = self._read_log()
        self.assertEqual(records[-1]["stage"], "stage2")
        self.assertEqual(records[-1]["reason"], "Jason approved one-off send")

    def test_strip_force_flags(self):
        from stage_gate import strip_force_flags

        self.assertEqual(
            strip_force_flags(
                ["--audit", "data/submissions/x", "--force", "--force-reason", "because"]
            ),
            ["--audit", "data/submissions/x"],
        )


if __name__ == "__main__":
    unittest.main()
