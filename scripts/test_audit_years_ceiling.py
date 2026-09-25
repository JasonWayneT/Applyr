#!/usr/bin/env python3
"""Years-ceiling right-number tests. Implements TEST-114D / FR-332."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_years_ceiling import audit_archive_years_ceiling
from seniority_gate import explain_years_requirement, parse_max_years_required

PREFS = {"experience_range": {"min": 2, "max": 7}}
_ROOT = Path(__file__).resolve().parents[1]


class TestYearsCeilingExplain(unittest.TestCase):
    def test_anchored_skip_is_stated(self) -> None:
        """An anchored 10+ years skip is a real ceiling."""
        jd = "Requirements: 10+ years of product management experience."
        explained = explain_years_requirement(jd, PREFS)
        self.assertEqual(explained["required"], 10)
        self.assertFalse(explained["gate_passes"])
        self.assertEqual(explained["wrong_number_flags"], [])

    def test_range_low_end_passes(self) -> None:
        """5-7 gates on 5 and passes. Range top is the wrong number."""
        jd = "Qualifications: 5-7 years of product management experience."
        explained = explain_years_requirement(jd, PREFS)
        self.assertEqual(explained["required"], 5)
        self.assertTrue(explained["gate_passes"])
        self.assertNotIn("range_top", explained["wrong_number_flags"])

    def test_range_8_12_skips_on_eight(self) -> None:
        """8-12 still skips because the floor is 8."""
        jd = "Qualifications: 8-12 years of product management experience."
        explained = explain_years_requirement(jd, PREFS)
        self.assertEqual(explained["required"], 8)
        self.assertFalse(explained["gate_passes"])
        self.assertNotIn("range_top", explained["wrong_number_flags"])

    def test_age_is_a_wrong_number_if_it_hits(self) -> None:
        """Must be eighteen years of age is not a years-of-experience hit."""
        jd = "Must be eighteen years of age or older."
        self.assertIsNone(parse_max_years_required(jd))
        explained = explain_years_requirement(jd, PREFS)
        self.assertTrue(explained["gate_passes"])
        self.assertIsNone(explained["required"])

    def test_word_number_experience_still_parses(self) -> None:
        jd = "Twelve+ years of product management experience"
        self.assertEqual(parse_max_years_required(jd), 12)
        explained = explain_years_requirement(jd, PREFS)
        self.assertEqual(explained["required"], 12)
        self.assertFalse(explained["gate_passes"])
        self.assertEqual(explained["wrong_number_flags"], [])

    def test_parse_matches_explain_required(self) -> None:
        jd = (
            "Requirements: minimum 8 years of experience. "
            "Also 10+ years of product management experience."
        )
        explained = explain_years_requirement(jd, PREFS)
        self.assertEqual(parse_max_years_required(jd), explained["required"])
        self.assertEqual(explained["required"], 10)


class TestYearsCeilingArchiveAudit(unittest.TestCase):
    def test_archive_years_skips_have_no_wrong_numbers(self) -> None:
        """Remaining years skips must not win on range top, age, or history."""
        archive = _ROOT / "data" / "archive" / "submissions"
        skipped = _ROOT / "data" / "archive" / "skipped"
        if not archive.is_dir() and not skipped.is_dir():
            self.skipTest("archive JDs are not present")
        audit = audit_archive_years_ceiling()
        self.assertGreater(audit["years_ceiling_count"], 0)
        self.assertEqual(
            audit["wrong_number_rows"],
            [],
            f"wrong numbers: {audit['wrong_number_rows'][:5]}",
        )


if __name__ == "__main__":
    unittest.main()
