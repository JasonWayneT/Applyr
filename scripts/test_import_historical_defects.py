"""CR-099 historical baseline isolation tests."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from import_historical_defects import confirm, scan  # noqa: E402


class HistoricalBaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "archive"
        self.baseline = self.root / "baseline.json"

    def _history(self, slug="acme"):
        path = self.archive / slug / "stage1_first_draft"
        path.mkdir(parents=True)
        (path / "verify_history.json").write_text(
            json.dumps([{
                "attempt": 1,
                "observed_at": "2026-08-01T00:00:00Z",
                "violations": [{
                    "rule_id": "LR-016",
                    "doc": "cover_letter",
                    "line": 8,
                }],
            }]),
            encoding="utf-8",
        )

    def test_scan_imports_structured_candidates_only(self):
        self._history()
        folder = self.archive / "acme"
        (folder / "CoverLetter.md").write_text("I have not done this before", encoding="utf-8")
        result = scan(self.archive, self.baseline)
        self.assertEqual(len(result["records"]), 1)
        record = result["records"][0]
        self.assertEqual(record["status"], "needs_review")
        self.assertFalse(record["live_promotion_eligible"])
        self.assertFalse(record["post_launch_metric_eligible"])
        self.assertEqual(record["evidence_type"], "historical_verify_history")

    def test_scan_is_idempotent(self):
        self._history()
        first = scan(self.archive, self.baseline)
        second = scan(self.archive, self.baseline)
        self.assertEqual([r["id"] for r in first["records"]], [r["id"] for r in second["records"]])

    def test_confirmation_requires_note_and_stays_excluded(self):
        self._history()
        scan(self.archive, self.baseline)
        record_id = json.loads(self.baseline.read_text(encoding="utf-8"))["records"][0]["id"]
        with self.assertRaises(ValueError):
            confirm(record_id, "", "jason", self.baseline)
        record = confirm(record_id, "Verified against the archived first-draft receipt.", "jason", self.baseline)
        self.assertEqual(record["status"], "human_confirmed")
        self.assertFalse(record["live_promotion_eligible"])
        self.assertFalse(record["post_launch_metric_eligible"])

    def test_unknown_categories_are_not_imported(self):
        path = self.archive / "unknown" / "stage1_first_draft"
        path.mkdir(parents=True)
        (path / "verify_history.json").write_text(
            json.dumps([{"violations": [{"rule_id": "LR-999", "doc": "resume"}]}]),
            encoding="utf-8",
        )
        self.assertEqual(scan(self.archive, self.baseline)["records"], [])


if __name__ == "__main__":
    unittest.main()
