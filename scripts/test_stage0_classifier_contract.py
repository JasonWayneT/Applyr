#!/usr/bin/env python3
"""Applyr Stage 0 classifier contract tests (CR-114 / FR-328)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage0_classifier_contract import (
    EXTRACTION_BUCKETS,
    EXTRACTION_USER_PREFIX,
    EVIDENCE_SYSTEM,
    EXTRACTION_SYSTEM,
    evidence_user_prompt,
    extraction_user_prompt,
    is_disposition_culture_line,
    parse_extraction_mapping,
)
import stage0_subscription_adapter as adapter


class Stage0ClassifierContractTests(unittest.TestCase):
    def test_extraction_packet_is_applyr_labeling_not_a_coding_task(self) -> None:
        prompt = extraction_user_prompt([("e0", "Experience with Jira")])
        self.assertIn("[e0] Experience with Jira", prompt)
        self.assertIn("Do not invent item_ids", prompt)
        self.assertIn("junk", EXTRACTION_BUCKETS)
        self.assertIn("junk", prompt)
        self.assertIn("duty verb", EXTRACTION_USER_PREFIX)
        self.assertIn("you are a person who", EXTRACTION_USER_PREFIX)
        self.assertIn("loves storytelling", EXTRACTION_USER_PREFIX)
        self.assertIn("Never use junk when unsure", EXTRACTION_USER_PREFIX)
        self.assertIn("Do not use tools", EXTRACTION_SYSTEM)
        self.assertIn(EXTRACTION_SYSTEM.split()[0], EXTRACTION_SYSTEM)

    def test_evidence_packet_includes_hard_gate_rules(self) -> None:
        self.assertIn("EVIDENCE SCALE", EVIDENCE_SYSTEM)
        self.assertIn("PREFERRED bucket NEVER gates", EVIDENCE_SYSTEM)
        self.assertIn("required:0:deadbeef", EVIDENCE_SYSTEM)
        self.assertIn("Copy each item_id EXACTLY from the packet", EVIDENCE_SYSTEM)
        prompt = evidence_user_prompt(
            [{
                "item_id": "required:0:abc",
                "bucket": "required",
                "requirement": "Experience with Jira",
                "evidence_excerpt": "Used Jira for sequencing",
            }]
        )
        self.assertIn("requirement=Experience with Jira", prompt)
        self.assertIn("evidence=Used Jira for sequencing", prompt)
        self.assertIn("bucket=required", prompt)

    def test_extraction_parser_accepts_results_array_and_legacy_index_map(self) -> None:
        ids = ["0", "1"]
        from_schema = parse_extraction_mapping(
            {"results": [{"item_id": "0", "bucket": "required"}]},
            ids,
        )
        from_legacy = parse_extraction_mapping({"0": "required", "1": "culture"}, ids)
        from_junk = parse_extraction_mapping(
            {"results": [{"item_id": "0", "bucket": "junk"}]},
            ids,
        )
        self.assertEqual(from_schema, {"0": "required"})
        self.assertEqual(from_legacy["0"], "required")
        self.assertEqual(from_legacy["1"], "culture")
        self.assertEqual(from_junk["0"], "junk")

    def test_disposition_lines_are_culture_checkable_quals_are_not(self) -> None:
        dispositions = [
            "Sees an inefficient process and cannot leave it alone.",
            "Vibe codes prototypes and immediately thinks about what it takes to productionize and put it into production.",
            "Tries every new AI tool the week it drops, and you've got the browser history to prove it.",
            "Loves storytelling and can walk a skeptical business leader through how an agent is going to change their workflow.",
            "You are excited to work in a startup environment, with the ambiguity and shifting priorities that might come with it at times",
            "Curiosity and building instinct: You are a natural builder and a curious one. You learn tools by using them on real work.",
            "User empathy: For both users of an agent experience: the developer or marketer directing the work, and the agent doing it.",
        ]
        checkable = [
            "Has shipped AI-enabled products into production.",
            "Has been building with LLMs, agents, and workflow tools long enough to have strong opinions about what's real and what's hype.",
            "Agentic fluency: You keep yourself at the front of agentic tools and practices and adopt them in your daily work.",
            "Written communication: A core requirement. You turn a messy problem into a clear, structured document a reader understands without a meeting.",
            "Technical depth: Working knowledge of APIs, the Model Context Protocol (MCP), cloud architecture, and modern web technologies.",
            "AI and automation: Hands-on with LLMs, agent design, tool and MCP integration, and the governance an agent needs to act safely.",
            "Stakeholder management: A track record of building and keeping relationships with customers, partners, and executive leadership.",
            "Recognized as an expert in product adoption, onboarding, and growth strategy, with strong working knowledge of the broader ActBlue product and technology stack.",
        ]
        for line in dispositions:
            self.assertTrue(is_disposition_culture_line(line), line)
        for line in checkable:
            self.assertFalse(is_disposition_culture_line(line), line)

    def test_subscription_transport_sends_applyr_evidence_rules(self) -> None:
        items = [
            adapter.Stage0Item(
                "required:0:abc",
                bucket="required",
                requirement="Experience with Jira",
                evidence_excerpt="Used Jira for sequencing",
            )
        ]
        prompt = adapter._prompt("evidence", items)
        self.assertIn("EVIDENCE SCALE", prompt)
        self.assertIn("HARD GATES", prompt)
        self.assertIn("Do not use tools", prompt)
        self.assertIn("requirement=Experience with Jira", prompt)
        self.assertNotIn("go investigate", prompt.lower())


if __name__ == "__main__":
    unittest.main()
