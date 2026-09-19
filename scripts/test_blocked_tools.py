#!/usr/bin/env python3
"""Tests for scripts/blocked_tools.py."""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blocked_tools import hard_blocked_tool_pattern, hard_blocked_tools_lint_alternation


class TestEpicAgileFalsePositive(unittest.TestCase):
    """Found 2026-09-19 on binance: "epic" is blocked as the Epic EHR/healthcare
    company, but it also matched the ordinary Agile noun ("epics and stories"),
    which is Jason's own approved language (ACC-179: "drafting epics and
    stories"). Mirrors the existing `workday` / "workday hours" exclusion.
    """

    def test_agile_epic_and_stories_not_flagged(self) -> None:
        text = "utilizing AI tools to accelerate epic and user story drafting"
        self.assertIsNone(hard_blocked_tool_pattern().search(text))
        self.assertIsNone(
            re.search(
                r"\b(?:" + hard_blocked_tools_lint_alternation() + r")\b",
                text,
                re.I,
            )
        )

    def test_agile_epics_and_stories_plural_not_flagged(self) -> None:
        text = "drafting epics and stories from the pillar structure"
        self.assertIsNone(hard_blocked_tool_pattern().search(text))

    def test_epic_hierarchy_not_flagged(self) -> None:
        text = "establishing clear epic and story hierarchies"
        self.assertIsNone(hard_blocked_tool_pattern().search(text))

    def test_real_epic_ehr_company_still_flagged(self) -> None:
        for text in (
            "integrated with Epic Systems for patient records",
            "hands-on experience with Epic EHR configuration",
            "migrated data out of Epic into the new platform",
        ):
            self.assertIsNotNone(hard_blocked_tool_pattern().search(text), text)

    def test_workday_hours_exclusion_unaffected(self) -> None:
        self.assertIsNone(hard_blocked_tool_pattern().search("logged workday hours"))
        self.assertIsNotNone(hard_blocked_tool_pattern().search("implemented Workday HCM"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
