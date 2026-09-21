#!/usr/bin/env python3
"""Tests for scripts/blocked_tools.py."""
from __future__ import annotations

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blocked_tools import epic_match_is_agile_noun, hard_blocked_tool_pattern, hard_blocked_tools_lint_alternation


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

    def test_epic_in_list_phrasing_not_flagged(self) -> None:
        """Live miss (lexipol, 2026-09-20): "epics" in a list with other Agile
        nouns, not the narrow "epics and stories" adjacency the original fix
        covered."""
        text = (
            "defining technical Requirements, epics, and detailed User "
            "Stories while using AI tools"
        )
        self.assertIsNone(hard_blocked_tool_pattern().search(text))

    def test_epic_structures_and_acceptance_criteria_not_flagged(self) -> None:
        """Live miss (lexipol, 2026-09-20): "epic structures" with no
        "story"/"stories" word at all -- only "acceptance criteria" nearby."""
        text = (
            "established a standardized Agile and Kanban framework that "
            "defined requirements, epic structures, and acceptance criteria "
            "across all three regions"
        )
        self.assertIsNone(hard_blocked_tool_pattern().search(text))

    def test_plural_epics_never_matches_regardless_of_context(self) -> None:
        """2026-09-21: plural "epics" is excluded unconditionally now (see
        _epic_pattern's docstring) since every real company mention is
        singular, title-case -- so this live miss (peoplefinders, the Agile
        qualifying word "roadmap" coming BEFORE "epics", which the old
        forward-only regex lookahead couldn't see) is now fixed at the regex
        level, no bidirectional scan needed for the plural form at all."""
        line = "giving teams realistic bandwidth bands for new roadmap epics."
        self.assertIsNone(hard_blocked_tool_pattern().search(line))

    def test_epic_match_is_agile_noun_catches_backward_context_singular(self) -> None:
        """Singular "epic" is still genuinely ambiguous (Agile item vs. the
        company) and keeps the forward-lookahead regex plus
        epic_match_is_agile_noun()'s bidirectional scan as backup for a
        backward-only-context sentence, same shape as the plural miss above
        before that got the simpler, unconditional fix."""
        line = "giving teams realistic bandwidth bands for a new roadmap epic."
        m = hard_blocked_tool_pattern().search(line)
        self.assertIsNotNone(m, "sanity: the bare regex still matches -- that's the known gap")
        self.assertTrue(epic_match_is_agile_noun(line, m.start(), m.end()))

    def test_epic_match_is_agile_noun_still_flags_real_company(self) -> None:
        line = "migrated data out of Epic into the new platform."
        m = hard_blocked_tool_pattern().search(line)
        self.assertIsNotNone(m)
        self.assertFalse(epic_match_is_agile_noun(line, m.start(), m.end()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
