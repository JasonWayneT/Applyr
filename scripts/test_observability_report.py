#!/usr/bin/env python3
"""Tests for observability_report.py (Epic C). Real-data testing during development already
caught one genuine bug in the report's own math (a duplicate finding id in a real submission's
truth_findings.json made severity counts and disposition counts disagree) -- these tests pin
that specific regression alongside the more usual empty/degraded-input cases.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_observability_report -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import observability_report as obs_report  # noqa: E402


def _write(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


class TestGatherAndRenderDegradeGracefully(unittest.TestCase):
    """A folder with nothing in it at all (e.g. a stage0-only Skip) must not crash."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_folder_renders_without_crashing(self):
        data = obs_report.gather(self.folder)
        report = obs_report.render(data)
        self.assertIn("Observability Report", report)
        self.assertIn("not reached", report)

    def test_no_events_shows_the_predates_instrumentation_note(self):
        data = obs_report.gather(self.folder)
        report = obs_report.render(data)
        self.assertIn("predates this instrumentation", report)


class TestDispositionTableMath(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _base_data(self):
        return {
            "slug": "test-co",
            "folder": self.folder,
            "workflow_state": {"status": "COMPLETE", "stages": {}},
            "receipts": {"stage0": None, "stage1": None, "stage2": None, "stage3": None},
            "stage0_fit_gate": {},
            "findings": {"truth": None, "ats": None, "hm": None, "mech": None, "policy": None},
            "dispositions": {},
            "verify_history": [],
            "events": [],
        }

    def test_every_disposition_type_is_counted_in_its_own_column_not_lumped_into_other(self):
        data = self._base_data()
        data["findings"]["truth"] = {
            "findings": [
                {"id": "a", "severity": "WARN"},
                {"id": "b", "severity": "WARN"},
                {"id": "c", "severity": "WARN"},
                {"id": "d", "severity": "WARN"},
                {"id": "e", "severity": "WARN"},
            ]
        }
        data["dispositions"] = {
            "by_finding_id": {
                "a": "RESOLVED_EDIT",
                "b": "ACCEPTED_AS_CORRECT",
                "c": "NOT_APPLICABLE",
                "d": "FALSE_POSITIVE",
                "e": "HUMAN_ACCEPTED_RISK",
            }
        }
        report = obs_report.render(data)
        row = [l for l in report.splitlines() if l.startswith("| truth")][0]
        # BLOCK WARN Resolved Accepted N/A False+ Risk-accepted Undisposed
        self.assertEqual(row, "| truth | 0 | 5 | 1 | 1 | 1 | 1 | 1 | 0 |")

    def test_undisposed_is_genuinely_separate_from_valid_dispositions(self):
        data = self._base_data()
        data["findings"]["truth"] = {"findings": [{"id": "a", "severity": "WARN"}]}
        data["dispositions"] = {"by_finding_id": {}}
        report = obs_report.render(data)
        row = [l for l in report.splitlines() if l.startswith("| truth")][0]
        self.assertTrue(row.endswith("| 1 |"))  # undisposed == 1

    def test_duplicate_finding_ids_are_counted_once_and_flagged(self):
        """Real-data regression: a real submission's truth_findings.json had the same finding
        id appear twice. Severity/disposition counts must be computed per unique id, not per
        raw list entry, or the row's own numbers don't add up to its WARN count."""
        data = self._base_data()
        data["findings"]["truth"] = {
            "findings": [
                {"id": "dup", "severity": "WARN"},
                {"id": "dup", "severity": "WARN"},
                {"id": "unique", "severity": "WARN"},
            ]
        }
        data["dispositions"] = {"by_finding_id": {"dup": "ACCEPTED_AS_CORRECT", "unique": "ACCEPTED_AS_CORRECT"}}
        report = obs_report.render(data)
        row = [l for l in report.splitlines() if l.startswith("| truth")][0]
        # WARN counted per unique id (2), not per raw list entry (3)
        self.assertEqual(row, "| truth | 0 | 2 | 0 | 2 | 0 | 0 | 0 | 0 |")
        self.assertIn("emitted the same finding id more than once", report)
        self.assertIn("dup", report)


if __name__ == "__main__":
    unittest.main()
