"""CR-114 Story 4: shadow evidence matcher abstains and cannot skip."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage0_evidence_matcher import (
    ReviewedCase,
    as_shadow_row,
    load_reviewed_cases,
    match_requirement,
)


CASES = [
    ReviewedCase("jira-tool", ("jira",), "jason", "2026-09-17"),
    ReviewedCase("sql-tool", ("sql",), "jason", "2026-09-17"),
]


class Stage0EvidenceMatcherTests(unittest.TestCase):
    def test_reviewed_alias_in_both_sides_matches(self) -> None:
        result = match_requirement(
            "Experience with Jira",
            "Used Jira to sequence platform work",
            CASES,
        )
        self.assertEqual(result.decision, "match")
        self.assertEqual(result.case_id, "jira-tool")
        self.assertEqual(result.matched_alias, "jira")

    def test_unreviewed_file_rows_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps({
                "cases": [
                    {"id": "poison", "aliases": ["jira"], "reviewed_by": "llm", "reviewed_at": "2026-09-17"},
                    {"id": "jira-tool", "aliases": ["jira"], "reviewed_by": "jason", "reviewed_at": "2026-09-17"},
                ]
            }), encoding="utf-8")
            loaded = load_reviewed_cases(path)
        self.assertEqual([case.case_id for case in loaded], ["jira-tool"])

    def test_generic_capability_abstains(self) -> None:
        result = match_requirement(
            "Strong critical thinking and communication",
            "Shows critical thinking in incident reviews",
            [ReviewedCase("soft", ("critical thinking",), "jason", "2026-09-17", "trait")],
        )
        self.assertEqual(result.decision, "abstain")

    def test_requirement_only_hit_abstains(self) -> None:
        result = match_requirement(
            "Experience with Jira",
            "Owned roadmap sequencing across engineering",
            CASES,
        )
        self.assertEqual(result.decision, "abstain")

    def test_no_cases_abstains(self) -> None:
        result = match_requirement("Experience with Jira", "Used Jira", [])
        self.assertEqual(result.decision, "abstain")

    def test_shadow_row_has_no_hard_or_skip(self) -> None:
        row = as_shadow_row(match_requirement("Experience with Jira", "Used Jira", CASES))
        self.assertNotIn("gate", row)
        self.assertNotIn("skip", row)
        blob = json.dumps(row).lower()
        self.assertNotIn("hard", blob)
        self.assertNotIn("skip", blob)

    def test_ambiguous_two_cases_abstain(self) -> None:
        result = match_requirement(
            "Experience with Jira and SQL",
            "Used Jira and SQL on the same team",
            CASES,
        )
        self.assertEqual(result.decision, "abstain")


if __name__ == "__main__":
    unittest.main()
