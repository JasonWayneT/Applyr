#!/usr/bin/env python3
"""Tests for run_submission.py's Epic D console summary (observability design §5.1/§7).
Isolated from the CLI's full argparse/dispatch flow -- just the summary formatting, which reads
back whatever workflow.observability.append_event already wrote.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_run_submission_console_summary -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_submission  # noqa: E402
from workflow.observability import append_event  # noqa: E402


class TestFmtDuration(unittest.TestCase):
    def test_none_is_blank(self):
        self.assertEqual(run_submission._fmt_duration(None), "")

    def test_seconds(self):
        self.assertEqual(run_submission._fmt_duration(6.1), "6.1s")

    def test_minutes(self):
        self.assertEqual(run_submission._fmt_duration(180), "3m")


class TestPrintConsoleSummary(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _captured(self, before_count: int) -> str:
        buf = StringIO()
        with mock.patch("sys.stdout", buf):
            run_submission._print_console_summary(self.folder, before_count)
        return buf.getvalue()

    def test_only_events_after_before_count_are_printed(self):
        append_event(self.folder, "r1", "stage0", "start")
        append_event(self.folder, "r1", "stage0", "complete", duration_seconds=6.1, tier="Tier 2")
        out = self._captured(before_count=1)  # skip the "start" event
        self.assertNotIn("start", out)
        self.assertIn("complete", out)
        self.assertIn("tier=Tier 2", out)
        self.assertIn("6.1s", out)

    def test_no_new_events_prints_nothing(self):
        append_event(self.folder, "r1", "stage0", "start")
        out = self._captured(before_count=1)
        self.assertEqual(out, "")

    def test_findings_by_severity_renders_compactly(self):
        append_event(
            self.folder, "r1", "stage2.truth", "complete",
            duration_seconds=1.2, findings_by_severity={"WARN": 8, "BLOCK": 0},
        )
        out = self._captured(before_count=0)
        self.assertIn("findings=WARN:8,BLOCK:0", out)

    def test_never_crashes_on_an_event_with_only_the_required_fields(self):
        append_event(self.folder, "r1", "stage3", "failed")
        out = self._captured(before_count=0)
        self.assertIn("failed", out)


if __name__ == "__main__":
    unittest.main()
