#!/usr/bin/env python3
"""Observability design (2026-08-30) — tests for workflow.observability's append-only event log.

See docs/spec/08-implementation/OBSERVABILITY-DESIGN-2026-08-30-stage0-3-replay-reporting.md §4/§7
(Epic B). Isolated unit tests only — runner.py integration is covered by
test_workflow_authority.py's existing stage-flow tests once wired in.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_observability -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflow.observability import append_event, events_path, new_run_id, read_events  # noqa: E402


class TestNewRunId(unittest.TestCase):
    def test_looks_sortable_and_unique(self):
        a = new_run_id()
        b = new_run_id()
        self.assertTrue(a.startswith("run_"))
        self.assertNotEqual(a, b)


class TestAppendAndReadEvents(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_read_events_on_a_folder_with_no_log_returns_empty_not_an_error(self):
        self.assertEqual(read_events(self.folder), [])

    def test_append_creates_the_observability_directory(self):
        append_event(self.folder, "run_x", "stage0", "start")
        self.assertTrue(os.path.exists(events_path(self.folder)))

    def test_appended_event_round_trips_with_schema_fields(self):
        append_event(self.folder, "run_x", "stage0", "complete", duration_seconds=6.1, tier="Tier 2")
        events = read_events(self.folder)
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["schema_version"], 1)
        self.assertEqual(e["run_id"], "run_x")
        self.assertEqual(e["stage"], "stage0")
        self.assertEqual(e["event"], "complete")
        self.assertEqual(e["duration_seconds"], 6.1)
        self.assertEqual(e["tier"], "Tier 2")
        self.assertIn("timestamp", e)

    def test_multiple_appends_preserve_order_as_separate_lines(self):
        append_event(self.folder, "run_x", "stage0", "start")
        append_event(self.folder, "run_x", "stage0", "complete", duration_seconds=1.0)
        append_event(self.folder, "run_y", "stage1", "start")
        events = read_events(self.folder)
        self.assertEqual([e["event"] for e in events], ["start", "complete", "start"])
        self.assertEqual([e["run_id"] for e in events], ["run_x", "run_x", "run_y"])

    def test_never_overwrites_a_prior_run_replaying_the_same_opportunity(self):
        append_event(self.folder, "run_x", "stage0", "complete", tier="Tier 2")
        append_event(self.folder, "run_z", "stage0", "complete", tier="Tier 1")
        events = read_events(self.folder)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["tier"], "Tier 2")
        self.assertEqual(events[1]["tier"], "Tier 1")

    def test_a_corrupt_last_line_does_not_break_reading_earlier_valid_lines(self):
        append_event(self.folder, "run_x", "stage0", "start")
        with open(events_path(self.folder), "a", encoding="utf-8") as f:
            f.write("{not valid json\n")
        events = read_events(self.folder)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "start")

    def test_blank_lines_are_skipped(self):
        path = events_path(self.folder)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"schema_version": 1, "run_id": "r", "stage": "s", "event": "e", "timestamp": "t"}) + "\n")
            f.write("\n")
            f.write(json.dumps({"schema_version": 1, "run_id": "r", "stage": "s", "event": "e2", "timestamp": "t"}) + "\n")
        events = read_events(self.folder)
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
