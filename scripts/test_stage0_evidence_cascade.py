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

    def test_gemini_soft_gate_and_level_field_are_accepted(self) -> None:
        """CR-108 cascade testing (2026-09-01): confirmed live on a real archived
        JD -- Gemini returned gate="SOFT" (not the prompted HARD/NONE binary,
        plausibly bleeding in from this codebase's own gap_class vocabulary)
        and a field named "level" instead of "evidence_level". Both are label
        differences the strict validator used to reject outright, discarding an
        otherwise well-reasoned, safe response and failing the whole batch with
        no remaining provider to fall back to."""
        item = BatchItem("required:0:a", "required", "Bachelor's degree in a related field")
        results = validate_batch_response(
            {
                "results": [
                    {
                        "item_id": "a",  # bare hash suffix, no "required:0:" prefix
                        "bucket": "required",
                        "gate": "SOFT",
                        "level": 3,
                        "confidence": "high",
                        "reasoning": "Evidence shows a related business degree.",
                    }
                ]
            },
            [item],
        )
        self.assertEqual(results[item.item_id]["gate"], "NONE")
        self.assertEqual(results[item.item_id]["evidence_level"], 3)
        # evidence_level 3 (> 2) means well-supported -- no gap at all, same
        # as it would be under the literal "NONE" gate the prompt specifies.
        self.assertIsNone(results[item.item_id]["gap_class"])

    def test_bare_hash_item_id_is_rejected_when_ambiguous(self) -> None:
        """The bare-hash fallback must never guess between two items that
        happen to share a hash suffix -- safety over convenience."""
        items = [
            BatchItem("required:0:abc123", "required", "Requirement one"),
            BatchItem("preferred:0:abc123", "preferred", "Requirement two"),
        ]
        with self.assertRaises(CascadeValidationError):
            validate_batch_response(
                {
                    "results": [
                        {
                            "item_id": "abc123",
                            "gate": "NONE",
                            "evidence_level": 2,
                            "confidence": "high",
                            "reasoning": "ambiguous",
                        }
                    ]
                },
                items,
            )

    def test_validator_passes_model_flagged_confirmation_through(self) -> None:
        """CR-108 Epic 7.2: the Layer C schema's needs_user_confirmation /
        canonical_skill / skill_kind fields are honored, not dropped, so the
        fit gate can create the durable pending item the model flagged."""
        item = BatchItem("required:0:a", "required", "Experience with Acme Platform")
        results = validate_batch_response(
            {
                "results": [
                    {
                        "item_id": item.item_id,
                        "gate": "NONE",
                        "gap_source": "",
                        "evidence_level": 2,
                        "confidence": "high",
                        "reasoning": "Acme Platform is not documented in the profile.",
                        "needs_user_confirmation": True,
                        "canonical_skill": "Acme Platform",
                        "skill_kind": "tool",
                    }
                ]
            },
            [item],
        )
        normalized = results[item.item_id]
        self.assertIs(normalized["needs_user_confirmation"], True)
        self.assertEqual(normalized["canonical_skill"], "acme platform")
        self.assertEqual(normalized["skill_kind"], "tool")

    def test_validator_coerces_flag_variants_and_defaults_false(self) -> None:
        item = BatchItem("required:0:a", "required", "Requirement")
        for raw_flag in (True, "true", 1, "1", "yes"):
            with self.subTest(flag=raw_flag):
                results = validate_batch_response(
                    {
                        "results": [
                            {
                                "item_id": item.item_id,
                                "gate": "NONE",
                                "evidence_level": 0,
                                "confidence": "high",
                                "reasoning": "ok",
                                "needs_user_confirmation": raw_flag,
                                "canonical_skill": "skill_x",
                                "skill_kind": "tool",
                            }
                        ]
                    },
                    [item],
                )
                self.assertIs(results[item.item_id]["needs_user_confirmation"], True)
        results = validate_batch_response(
            {
                "results": [
                    {
                        "item_id": item.item_id,
                        "gate": "NONE",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "ok",
                    }
                ]
            },
            [item],
        )
        self.assertIs(results[item.item_id]["needs_user_confirmation"], False)

    def test_validator_rejects_flag_without_canonical_skill(self) -> None:
        """Fail closed: a flagged item with no skill key must never silently
        finalize as a permanent anonymous gap -- the batch falls back so the
        next provider in the chain gets the chance to name it."""
        item = BatchItem("required:0:a", "required", "Requirement")
        with self.assertRaises(CascadeValidationError):
            validate_batch_response(
                {
                    "results": [
                        {
                            "item_id": item.item_id,
                            "gate": "NONE",
                            "evidence_level": 0,
                            "confidence": "high",
                            "reasoning": "ok",
                            "needs_user_confirmation": True,
                        }
                    ]
                },
                [item],
            )

    def test_flag_with_domain_skill_kind_is_not_a_tool_question(self) -> None:
        """skill_kind=domain or role with the flag is not a tool-presence
        question -- it scores normally (documented non-question case)."""
        item = BatchItem("required:0:a", "required", "Requirement")
        results = validate_batch_response(
            {
                "results": [
                    {
                        "item_id": item.item_id,
                        "gate": "NONE",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "ok",
                        "needs_user_confirmation": True,
                        "canonical_skill": "healthcare",
                        "skill_kind": "domain",
                    }
                ]
            },
            [item],
        )
        self.assertEqual(results[item.item_id]["skill_kind"], "domain")
        self.assertIs(results[item.item_id]["needs_user_confirmation"], True)

    def test_batch_falls_back_when_flag_lacks_canonical_skill(self) -> None:
        from stage0_evidence_cascade import classify_requirements_batch

        item = BatchItem("required:0:a", "required", "Requires a nursing license")
        flagged = json.dumps(
            {
                "results": [
                    {
                        "item_id": item.item_id,
                        "gate": "NONE",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "ok",
                        "needs_user_confirmation": True,
                    }
                ]
            }
        )
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
        with patch("utils.call_llm", side_effect=[flagged, valid]) as call:
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

    def test_genuinely_invalid_gate_value_is_still_rejected(self) -> None:
        """Tolerance for known synonyms (SOFT) must not become tolerance for
        anything -- an unrecognized gate value still fails closed."""
        item = BatchItem("required:0:a", "required", "Requirement")
        with self.assertRaises(CascadeValidationError):
            validate_batch_response(
                {
                    "results": [
                        {
                            "item_id": "required:0:a",
                            "gate": "MAYBE",
                            "evidence_level": 2,
                            "confidence": "high",
                            "reasoning": "unclear",
                        }
                    ]
                },
                [item],
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
