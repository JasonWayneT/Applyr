"""Tests for scripts/pm_years.py."""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pm_years import parse_pm_years_of_experience, pm_years_hard_constraint


class TestPmYears(unittest.TestCase):
    def test_parses_section_1_0_figure(self) -> None:
        we = (
            "### 1.0 Contact Information\n"
            "Jason is a PM with **7 years** of experience in platforms.\n"
            "### 1.0a References\n"
            "with **6 years** of experience should not win.\n"
        )
        self.assertEqual(parse_pm_years_of_experience(we), 7)

    def test_missing_figure_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_pm_years_of_experience("### 1.0 Contact\nNo years here.\n")

    def test_constraint_matches_rentana_wording(self) -> None:
        text = pm_years_hard_constraint(7)
        self.assertEqual(
            text,
            "Total product management experience: 7 years "
            "(write 'seven years' or '7 years'; never 4, 5, or 6)",
        )


if __name__ == "__main__":
    unittest.main()
