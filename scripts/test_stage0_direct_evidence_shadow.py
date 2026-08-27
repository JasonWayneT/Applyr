from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stage0_direct_evidence_shadow import direct_evidence_candidate, evaluate_gate


class TestDirectEvidenceShadow(unittest.TestCase):
    def setUp(self):
        self.phrases = {
            "jira": {"skill:product"},
            "roadmap prioritization": {"ACC-201-PM"},
            "product": {"ACC-generic"},
        }

    def test_requires_exact_specific_verified_phrase(self):
        result = direct_evidence_candidate(
            "Experience with Jira and roadmap prioritization.", self.phrases
        )
        self.assertEqual(result["matched_phrases"], ["roadmap prioritization", "jira"])
        self.assertIsNone(direct_evidence_candidate("Own the product strategy.", self.phrases))

    def test_marks_only_direct_llm_judgments_as_agreement(self):
        gate = {
            "company": "Example",
            "role": "PM",
            "required": [{
                "item": "Experience with Jira",
                "gap_class": None,
                "evidence_level": 3,
            }],
            "preferred": [{
                "item": "Roadmap prioritization",
                "gap_class": "SOFT",
                "evidence_level": 2,
            }],
        }
        rows = evaluate_gate(gate, self.phrases)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["scored_by_llm"])
        self.assertTrue(rows[0]["agrees_direct"])
        self.assertFalse(rows[1]["agrees_direct"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
