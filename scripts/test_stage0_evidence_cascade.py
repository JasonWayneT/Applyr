#!/usr/bin/env python3
"""Offline tests for the CR-108 batched Stage 0 evidence cascade."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage0_evidence_cascade import (  # noqa: E402
    CascadeValidationError,
    BatchItem,
    _build_batch_prompt,
    configured_provider_order,
    normalize_stage0_evidence_policy,
    validate_batch_response,
)


class TestStage0EvidenceCascade(unittest.TestCase):
    def test_default_provider_order_is_cloud_first(self) -> None:
        self.assertEqual(
            configured_provider_order(
                {"stage0_evidence_classification": {"provider_order": ["groq", "gemini"]}}
            ),
            ["groq", "gemini"],
        )

    def test_local_is_only_selected_explicitly(self) -> None:
        self.assertEqual(
            configured_provider_order(
                {"stage0_evidence_classification": {"provider_order": ["local"]}}
            ),
            ["local"],
        )

    def test_policy_normalization_has_provider_specific_models(self) -> None:
        policy = normalize_stage0_evidence_policy(
            {
                "stage0_evidence_classification": {
                    "provider_order": ["gemini", "groq", "invalid", "gemini"],
                    "models": {"gemini": " gemini-custom ", "groq": "groq-custom"},
                }
            }
        )
        self.assertEqual(policy["provider_order"], ["gemini", "groq"])
        self.assertEqual(
            policy["models"],
            {"gemini": "gemini-custom", "groq": "groq-custom"},
        )
        self.assertFalse(policy["local_only"])
        self.assertEqual(
            configured_provider_order(
                {"stage0_evidence_classification": {"local_only": True}}
            ),
            ["local"],
        )

    def test_batch_prompt_keeps_requirement_and_retrieved_evidence_separate(self) -> None:
        prompt = _build_batch_prompt(
            [
                BatchItem(
                    "required:0:license",
                    "required",
                    "Requires an active nursing license",
                    "## Professional Experience\nManaged clinical workflows.",
                )
            ]
        )
        self.assertIn("requirement=Requires an active nursing license", prompt)
        self.assertIn("evidence=## Professional Experience", prompt)
        self.assertNotIn("Contact Information", prompt)

    def test_batch_requires_exactly_one_result_for_each_item(self) -> None:
        items = [
            BatchItem("required:0:a", "required", "Experience with Trello"),
            BatchItem("preferred:0:b", "preferred", "Experience with Salesforce"),
        ]
        payload = {
            "results": [
                {
                    "item_id": "required:0:a",
                    "gate": "NONE",
                    "gap_source": "",
                    "evidence_level": 1,
                    "confidence": "high",
                    "reasoning": "tool presence only",
                },
                {
                    "item_id": "preferred:0:b",
                    "gate": "NONE",
                    "gap_source": "",
                    "evidence_level": 3,
                    "confidence": "high",
                    "reasoning": "Salesforce appears in verified work history",
                },
            ]
        }
        results = validate_batch_response(payload, items)
        self.assertEqual(set(results), {"required:0:a", "preferred:0:b"})
        self.assertEqual(results["required:0:a"]["gap_class"], "SOFT")

    def test_low_confidence_hard_is_held_as_non_hard(self) -> None:
        item = BatchItem("required:0:a", "required", "Requires a nursing license")
        results = validate_batch_response(
            {
                "results": [
                    {
                        "item_id": "required:0:a",
                        "gate": "HARD",
                        "gap_source": "certification",
                        "evidence_level": 0,
                        "confidence": "medium",
                        "reasoning": "license requirement",
                    }
                ]
            },
            [item],
        )
        self.assertEqual(results[item.item_id]["gap_class"], "SOFT")
        self.assertEqual(results[item.item_id]["confidence"], "low")
        self.assertIn("held", results[item.item_id]["anchor"].lower())

    def test_missing_or_duplicate_item_is_rejected(self) -> None:
        items = [BatchItem("required:0:a", "required", "Experience with Trello")]
        with self.assertRaises(CascadeValidationError):
            validate_batch_response({"results": []}, items)
        with self.assertRaises(CascadeValidationError):
            validate_batch_response(
                {
                    "results": [
                        {
                            "item_id": "required:0:a",
                            "gate": "NONE",
                            "gap_source": "",
                            "evidence_level": 2,
                            "confidence": "high",
                            "reasoning": "first",
                        },
                        {
                            "item_id": "required:0:a",
                            "gate": "NONE",
                            "gap_source": "",
                            "evidence_level": 2,
                            "confidence": "high",
                            "reasoning": "duplicate",
                        },
                    ]
                },
                items,
            )

    def test_batch_uses_configured_provider_then_falls_back_after_invalid_response(self) -> None:
        from stage0_evidence_cascade import classify_requirements_batch

        item = BatchItem("required:0:a", "required", "Requires a nursing license")
        invalid = json.dumps({"results": []})
        valid = json.dumps(
            {
                "results": [
                    {
                        "item_id": item.item_id,
                        "gate": "HARD",
                        "gap_source": "certification",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "nursing license is required",
                    }
                ]
            }
        )
        with patch("utils.call_llm", side_effect=[invalid, valid]) as call:
            result = classify_requirements_batch(
                [item],
                settings={
                    "stage0_evidence_classification": {
                        "provider_order": ["groq", "gemini"],
                        "models": {"groq": "groq-test", "gemini": "gemini-test"},
                    }
                },
            )
        self.assertEqual(result[item.item_id]["gap_class"], "HARD")
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args_list[0].kwargs["provider_override"], ["groq"])
        self.assertEqual(call.call_args_list[1].kwargs["provider_override"], ["gemini"])

    def test_batch_falls_back_after_provider_transport_error(self) -> None:
        from stage0_evidence_cascade import classify_requirements_batch

        item = BatchItem("required:0:a", "required", "Requires a nursing license")
        valid = json.dumps(
            {
                "results": [
                    {
                        "item_id": item.item_id,
                        "gate": "HARD",
                        "gap_source": "certification",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "nursing license is required",
                    }
                ]
            }
        )
        with patch("utils.call_llm", side_effect=[TimeoutError("Groq timed out"), valid]) as call:
            result = classify_requirements_batch(
                [item],
                settings={
                    "stage0_evidence_classification": {
                        "provider_order": ["groq", "gemini"],
                        "models": {"groq": "groq-test", "gemini": "gemini-test"},
                    }
                },
            )
        self.assertEqual(result[item.item_id]["gap_class"], "HARD")
        self.assertEqual(call.call_count, 2)


if __name__ == "__main__":
    unittest.main()
