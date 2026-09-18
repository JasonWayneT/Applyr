#!/usr/bin/env python3
"""Years boundary tests. Implements FR-332 / AC-430 / CR-117.

A range gates on its low end, the minimum the posting will accept.
A single stated figure stays as-is. Age, company history, and tenure
are not years-of-experience hits.
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seniority_gate import check_years_gate, parse_max_years_required

PREFS = {"experience_range": {"min": 2, "max": 7}}


class TestYearsRangeLowEnd(unittest.TestCase):
    def test_range_3_7_parses_low_end_and_passes(self) -> None:
        """3-7 years is mid-level. The floor is 3, not 7."""
        jd = "3-7 years of product management experience"
        self.assertEqual(parse_max_years_required(jd), 3)
        ok, _ = check_years_gate(jd, PREFS)
        self.assertTrue(ok)

    def test_range_4_7_passes(self) -> None:
        jd = "4-7 years of product management experience"
        self.assertEqual(parse_max_years_required(jd), 4)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_range_5_7_passes(self) -> None:
        jd = "5-7 years of product management experience"
        self.assertEqual(parse_max_years_required(jd), 5)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_range_5_8_passes(self) -> None:
        jd = "5-8 years of experience in product management"
        self.assertEqual(parse_max_years_required(jd), 5)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_range_6_10_passes(self) -> None:
        jd = "6-10 years of Product Management experience"
        self.assertEqual(parse_max_years_required(jd), 6)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_range_4_6_parses_four_not_six(self) -> None:
        jd = "4-6 years of product management experience"
        self.assertEqual(parse_max_years_required(jd), 4)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_range_7_10_skips(self) -> None:
        jd = "7-10 years of experience in product management"
        self.assertEqual(parse_max_years_required(jd), 7)
        ok, reason = check_years_gate(jd, PREFS)
        self.assertFalse(ok)
        self.assertIn("exceeds_max", reason)

    def test_range_8_12_skips_on_low_end(self) -> None:
        jd = "requires 8-12 years"
        self.assertEqual(parse_max_years_required(jd), 8)
        ok, reason = check_years_gate(jd, PREFS)
        self.assertFalse(ok)
        self.assertIn("exceeds_max", reason)

    def test_range_2_8_plus_uses_low_end(self) -> None:
        """2-8+ is a range whose floor is 2, not an 8+ skip."""
        jd = "2-8+ years of product management or software experience"
        self.assertEqual(parse_max_years_required(jd), 2)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_single_seven_plus_still_skips(self) -> None:
        jd = "7+ years of experience"
        self.assertEqual(parse_max_years_required(jd), 7)
        self.assertFalse(check_years_gate(jd, PREFS)[0])


class TestYearsAgeAndHistory(unittest.TestCase):
    def test_eighteen_years_of_age_is_not_a_hit(self) -> None:
        jd = "Minimum Qualifications: Must be eighteen years of age or older."
        self.assertIsNone(parse_max_years_required(jd))
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_company_tenure_fourteen_years_is_not_a_hit(self) -> None:
        jd = (
            "We have been delivering deep energy savings to our customers "
            "for fourteen years, and we are now growing faster than ever."
        )
        self.assertIsNone(parse_max_years_required(jd))
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_company_over_years_boilerplate_is_not_a_hit(self) -> None:
        jd = (
            "With over 20 years of experience building long-term client "
            "relationships, System Soft Technologies is hiring."
        )
        self.assertIsNone(parse_max_years_required(jd))
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_apostrophe_years_experience(self) -> None:
        jd = "10 years’ experience as a Product Manager"
        self.assertEqual(parse_max_years_required(jd), 10)

    def test_spelled_out_twelve_years_experience(self) -> None:
        jd = "Twelve+ years in product management"
        self.assertEqual(parse_max_years_required(jd), 12)

    def test_years_in_product_management(self) -> None:
        jd = "5 years in product management"
        self.assertEqual(parse_max_years_required(jd), 5)

    def test_word_range_five_to_seven_uses_low_end(self) -> None:
        jd = "Five to seven years of product management experience"
        self.assertEqual(parse_max_years_required(jd), 5)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_jackson_lab_ignores_history(self) -> None:
        jd = (
            "The Jackson Laboratory celebrates 90 years of genetics research. "
            "Requirements: 5+ years of product management experience."
        )
        self.assertEqual(parse_max_years_required(jd), 5)
        self.assertTrue(check_years_gate(jd, PREFS)[0])

    def test_civica_ignores_founded_years(self) -> None:
        jd = "Founded 21 years ago. Qualifications: minimum 4 years of PM experience."
        self.assertEqual(parse_max_years_required(jd), 4)

    def test_boundary_six_passes_seven_fails(self) -> None:
        self.assertTrue(check_years_gate("6 years of experience required", PREFS)[0])
        ok7, reason7 = check_years_gate("7 years of experience required", PREFS)
        self.assertFalse(ok7)
        self.assertIn("7", reason7)


if __name__ == "__main__":
    unittest.main()
