#!/usr/bin/env python3
"""CR-097 Epic 2 — scan_authoring_defects ledger + 2-occurrence trigger.

Run:
    .venv\\Scripts\\python.exe -m unittest scripts.test_scan_authoring_defects -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scan_authoring_defects import (  # noqa: E402
    EXIT_PENDING,
    scan_ledger,
)


def _write_history(folder: Path, slug: str, rule_id: str = "LR-014") -> None:
    dest = folder / slug / "stage1_first_draft"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "verify_history.json").write_text(
        json.dumps(
            [
                {
                    "attempt": 1,
                    "observed_at": "2026-08-21T12:00:00Z",
                    "passed": False,
                    "resume_sha256": "abc",
                    "cover_sha256": "def",
                    "rule_digest_version": "v1",
                    "example_bank_version": "",
                    "violations": [
                        {
                            "rule_id": rule_id,
                            "severity": "HARD_BLOCK",
                            "doc": "resume",
                            "line": 3,
                            "category": "forbidden_punctuation",
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )


class ScanAuthoringDefectsTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.root = Path(self._tmpdir.name)
        self.subs = self.root / "submissions"
        self.subs.mkdir()
        self.ledger = self.root / "authoring_defect_ledger.json"

    def test_one_slug_opens_no_review(self):
        _write_history(self.subs, "acme")
        result = scan_ledger(self.subs, self.ledger)
        self.assertEqual(len(result["occurrences"]), 1)
        self.assertEqual(result["reviews"], [])

    def test_two_slugs_same_category_opens_one_review(self):
        _write_history(self.subs, "acme")
        _write_history(self.subs, "beta")
        result = scan_ledger(self.subs, self.ledger)
        self.assertEqual(len(result["occurrences"]), 2)
        self.assertEqual(len(result["reviews"]), 1)
        review = result["reviews"][0]
        self.assertEqual(review["category"], "forbidden_punctuation")
        self.assertEqual(review["status"], "pending_review")
        self.assertEqual(set(review["distinct_slugs"]), {"acme", "beta"})

    def test_rescan_is_idempotent(self):
        _write_history(self.subs, "acme")
        _write_history(self.subs, "beta")
        scan_ledger(self.subs, self.ledger)
        again = scan_ledger(self.subs, self.ledger)
        self.assertEqual(len(again["occurrences"]), 2)
        self.assertEqual(len(again["reviews"]), 1)

    def test_declined_plus_two_new_slugs_reopens(self):
        _write_history(self.subs, "acme")
        _write_history(self.subs, "beta")
        first = scan_ledger(self.subs, self.ledger)
        first["reviews"][0]["status"] = "declined"
        first["reviews"][0]["resolution_note"] = "not generalizable"
        self.ledger.write_text(json.dumps(first, indent=2), encoding="utf-8")

        _write_history(self.subs, "gamma")
        _write_history(self.subs, "delta")
        again = scan_ledger(self.subs, self.ledger)
        statuses = [r["status"] for r in again["reviews"]]
        self.assertEqual(statuses.count("declined"), 1)
        self.assertEqual(statuses.count("pending_review"), 1)
        pending = [r for r in again["reviews"] if r["status"] == "pending_review"][0]
        self.assertEqual(set(pending["distinct_slugs"]), {"gamma", "delta"})

    def test_malformed_history_is_skipped_without_raising(self):
        dest = self.subs / "broken" / "stage1_first_draft"
        dest.mkdir(parents=True)
        (dest / "verify_history.json").write_text("{not-json", encoding="utf-8")
        _write_history(self.subs, "acme")
        result = scan_ledger(self.subs, self.ledger)
        self.assertEqual(len(result["occurrences"]), 1)
        self.assertEqual(result["reviews"], [])

    def test_status_exit_code_pending_versus_clean(self):
        from scan_authoring_defects import main

        _write_history(self.subs, "acme")
        code = main(
            ["--status"],
            submissions_root=self.subs,
            ledger_path=self.ledger,
        )
        self.assertEqual(code, 0)

        _write_history(self.subs, "beta")
        scan_ledger(self.subs, self.ledger)
        code = main(
            ["--status"],
            submissions_root=self.subs,
            ledger_path=self.ledger,
        )
        self.assertEqual(code, EXIT_PENDING)

    def test_promote_writes_ineligible_skeleton(self):
        from scan_authoring_defects import promote_review

        _write_history(self.subs, "acme")
        _write_history(self.subs, "beta")
        ledger = scan_ledger(self.subs, self.ledger)
        review_id = ledger["reviews"][0]["id"]
        bank_path = self.root / "authoring_example_bank.json"
        bank_path.write_text(
            json.dumps({"schema_version": 1, "description": "", "categories": [], "entries": []}),
            encoding="utf-8",
        )
        entry = promote_review(
            review_id, ledger_path=self.ledger, bank_path=bank_path
        )
        self.assertFalse(entry["few_shot_eligible"])
        self.assertEqual(entry["before"], "TODO")
        updated = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(updated["reviews"][0]["status"], "promoted")
        self.assertEqual(updated["reviews"][0]["bank_entry_id"], entry["id"])

    def test_decline_requires_note_and_sets_status(self):
        from scan_authoring_defects import decline_review

        _write_history(self.subs, "acme")
        _write_history(self.subs, "beta")
        ledger = scan_ledger(self.subs, self.ledger)
        review_id = ledger["reviews"][0]["id"]
        with self.assertRaises(ValueError):
            decline_review(review_id, "", ledger_path=self.ledger)
        decline_review(review_id, "idiosyncrasy", ledger_path=self.ledger)
        updated = json.loads(self.ledger.read_text(encoding="utf-8"))
        self.assertEqual(updated["reviews"][0]["status"], "declined")
        self.assertEqual(updated["reviews"][0]["resolution_note"], "idiosyncrasy")

    def test_report_splits_with_and_without_bank(self):
        from scan_authoring_defects import format_report

        _write_history(self.subs, "acme")
        _write_history(self.subs, "beta")
        ledger = scan_ledger(self.subs, self.ledger)
        text = format_report(ledger, last_n=10)
        self.assertIn("forbidden_punctuation", text)
        self.assertIn("without-bank=", text)


class TestWrongJobBleed(unittest.TestCase):
    """CR-097 Epic 5 — company-name bleed is WARN, precision-first."""

    def test_flags_other_known_company(self):
        from submission_linter import check_wrong_job_company_bleed

        hits = check_wrong_job_company_bleed(
            resume="Worked at Cision on the platform.",
            cover_letter="This is the same problem I solved for Lightcast last month.",
            jd_text="Product Manager at Gravitee",
            own_company="Gravitee",
            known_names={"Lightcast", "Gravitee", "Cision"},
        )
        self.assertTrue(any(v.rule_id == "LW-032" and "Lightcast" in v.message for v in hits))
        self.assertFalse(any("Gravitee" in v.message for v in hits))
        self.assertFalse(any("Cision" in v.message for v in hits))

    def test_own_company_does_not_warn(self):
        from submission_linter import check_wrong_job_company_bleed

        hits = check_wrong_job_company_bleed(
            resume="",
            cover_letter="I want to join Lightcast because the platform work matches.",
            jd_text="Product Manager",
            own_company="Lightcast",
            known_names={"Lightcast", "Gravitee"},
        )
        self.assertEqual(hits, [])

    def test_jd_mention_does_not_warn(self):
        from submission_linter import check_wrong_job_company_bleed

        hits = check_wrong_job_company_bleed(
            resume="",
            cover_letter="Partnering the way Lightcast is named in this posting.",
            jd_text="We compete with Lightcast in this market.",
            own_company="Gravitee",
            known_names={"Lightcast", "Gravitee"},
        )
        self.assertEqual(hits, [])

    def test_missing_db_does_not_raise(self):
        from submission_linter import known_company_names

        names = known_company_names(
            db_path="/nonexistent/jobagent.sqlite",
            submissions_root="/nonexistent",
        )
        self.assertEqual(names, set())


if __name__ == "__main__":
    unittest.main()
