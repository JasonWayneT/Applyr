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
    _resolve_item_id,
    configured_provider_order,
    normalize_stage0_evidence_policy,
    validate_batch_response,
)


class TestStage0EvidenceCascade(unittest.TestCase):
    def setUp(self) -> None:
        from cost_eligibility import set_test_zero_charge_providers

        set_test_zero_charge_providers(["groq", "gemini", "local"])
        self._decl = patch(
            "cost_eligibility.declared_cost_class",
            side_effect=lambda provider, settings: {
                "groq": "free_only",
                "gemini": "free_only",
                "local": "offline",
            }.get(str(provider), "unknown"),
        )
        self._decl.start()
        self.addCleanup(self._decl.stop)

    def tearDown(self) -> None:
        from cost_eligibility import set_test_zero_charge_providers

        set_test_zero_charge_providers(None)

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

    def test_invented_sequential_id_is_rejected(self) -> None:
        """CR-112 Story 1.1: providers invent "req-001"/"pref-1" ids. Mapping
        those onto list position attaches HARD/NONE to the wrong requirement
        when numbering and content disagree. Hash-suffix and unique-ordinal
        fallbacks still identify one real id. Position mapping must not.
        Implements FR-296 / AC-393
        """
        items = [
            BatchItem("required:0:aaaaaaaaaaaaaaaa", "required", "Requirement one"),
            BatchItem("required:1:bbbbbbbbbbbbbbbb", "required", "Requirement two"),
            BatchItem("preferred:0:cccccccccccccccc", "preferred", "Preferred one"),
        ]
        expected = {item.item_id: item for item in items}
        self.assertIsNone(_resolve_item_id("req-001", expected))
        self.assertIsNone(_resolve_item_id("req-002", expected))
        self.assertIsNone(_resolve_item_id("pref-1", expected))
        # Unique hash suffix remains a display difference, not a guess.
        self.assertEqual(
            _resolve_item_id("aaaaaaaaaaaaaaaa", expected),
            "required:0:aaaaaaaaaaaaaaaa",
        )
        with self.assertRaises(CascadeValidationError) as ctx:
            validate_batch_response(
                {
                    "results": [
                        {"item_id": "req-001", "gate": "HARD", "evidence_level": 0,
                         "confidence": "high", "gap_source": "domain",
                         "reasoning": "no evidence for requirement two actually"},
                        {"item_id": "req-002", "gate": "NONE", "evidence_level": 3,
                         "confidence": "high",
                         "reasoning": "strong match for requirement one"},
                    ]
                },
                items,
            )
        self.assertIn("unknown batch item_id", str(ctx.exception))
        self.assertIn("req-001", str(ctx.exception))

    def test_shuffled_sequential_ids_do_not_remap_by_position(self) -> None:
        """CR-112 Story 1.1: if req-001's HARD reasoning names item two,
        position mapping would attach HARD to item one. Reject instead.
        Implements FR-296 / AC-393
        """
        items = [
            BatchItem("required:0:aaaaaaaaaaaaaaaa", "required", "Requirement one"),
            BatchItem("required:1:bbbbbbbbbbbbbbbb", "required", "Requirement two"),
        ]
        with self.assertRaises(CascadeValidationError):
            validate_batch_response(
                {
                    "results": [
                        {
                            "item_id": "req-001",
                            "gate": "HARD",
                            "evidence_level": 0,
                            "confidence": "high",
                            "gap_source": "domain",
                            "reasoning": "no evidence for requirement two",
                        },
                        {
                            "item_id": "req-002",
                            "gate": "NONE",
                            "evidence_level": 3,
                            "confidence": "high",
                            "reasoning": "strong match for requirement one",
                        },
                    ]
                },
                items,
            )
        # Unique ordinal and mangled-prefix-plus-hash remain valid.
        expected = {item.item_id: item for item in items}
        self.assertEqual(
            _resolve_item_id("1", expected),
            "required:1:bbbbbbbbbbbbbbbb",
        )
        self.assertEqual(
            _resolve_item_id("req-bbbbbbbbbbbbbbbb", expected),
            "required:1:bbbbbbbbbbbbbbbb",
        )

    def test_unknown_sequential_id_raises_even_when_partial(self) -> None:
        """Unknown ids are not missing-for-retry. partial=True still fails
        the whole response so valid siblings in the same payload are discarded.
        """
        items = [
            BatchItem("required:0:aaaaaaaaaaaaaaaa", "required", "Requirement one"),
            BatchItem("required:1:bbbbbbbbbbbbbbbb", "required", "Requirement two"),
        ]
        with self.assertRaises(CascadeValidationError) as ctx:
            validate_batch_response(
                {
                    "results": [
                        {
                            "item_id": "req-001",
                            "gate": "HARD",
                            "evidence_level": 0,
                            "confidence": "high",
                            "gap_source": "domain",
                            "reasoning": "no evidence for requirement two",
                        },
                        {
                            "item_id": "required:1:bbbbbbbbbbbbbbbb",
                            "gate": "NONE",
                            "evidence_level": 3,
                            "confidence": "high",
                            "reasoning": "strong match for requirement two",
                        },
                    ]
                },
                items,
                partial=True,
            )
        self.assertIn("unknown batch item_id", str(ctx.exception))

    def test_invented_sequential_ids_fall_back_to_next_provider(self) -> None:
        """CR-112 Story 1.1: Groq returns req-001/req-002; that is not a
        partial miss. The caller falls back to Gemini with the real ids.
        Simulated retry/fallback. No live call_llm. Implements FR-296 / AC-393.
        """
        from stage0_evidence_cascade import classify_requirements_batch

        item_one = BatchItem(
            "required:0:aaaaaaaaaaaaaaaa", "required", "Requirement one"
        )
        item_two = BatchItem(
            "required:1:bbbbbbbbbbbbbbbb", "required", "Requirement two"
        )
        sequential = json.dumps(
            {
                "results": [
                    {
                        "item_id": "req-001",
                        "gate": "HARD",
                        "gap_source": "domain",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "no evidence for requirement two",
                    },
                    {
                        "item_id": "req-002",
                        "gate": "NONE",
                        "evidence_level": 3,
                        "confidence": "high",
                        "reasoning": "strong match for requirement one",
                    },
                ]
            }
        )
        recovered = json.dumps(
            {
                "results": [
                    {
                        "item_id": item_one.item_id,
                        "gate": "NONE",
                        "evidence_level": 3,
                        "confidence": "high",
                        "reasoning": "strong match for requirement one",
                    },
                    {
                        "item_id": item_two.item_id,
                        "gate": "HARD",
                        "gap_source": "domain",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "no evidence for requirement two",
                    },
                ]
            }
        )
        events: list[tuple[str, str]] = []
        with patch("utils.call_llm", side_effect=[sequential, recovered]) as call:
            result = classify_requirements_batch(
                [item_one, item_two],
                settings={
                    "stage0_evidence_classification": {
                        "provider_order": ["groq", "gemini"],
                        "models": {"groq": "groq-test", "gemini": "gemini-test"},
                    }
                },
                provider_event_callback=lambda p, e: events.append((p, e)),
            )
        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args_list[0].kwargs["provider_override"], ["groq"])
        self.assertEqual(call.call_args_list[1].kwargs["provider_override"], ["gemini"])
        self.assertIn(("groq", "fallback"), events)
        self.assertIsNone(result[item_one.item_id]["gap_class"])
        self.assertEqual(result[item_one.item_id]["gate"], "NONE")
        self.assertEqual(result[item_two.item_id]["gap_class"], "HARD")
        self.assertEqual(result[item_two.item_id]["gate"], "HARD")

    def test_invented_sequential_ids_fail_closed_when_all_providers_invent(self) -> None:
        """If Groq and Gemini both return req-001, the cascade raises the
        unknown-id error. It must not remap by position on the last attempt.
        """
        from stage0_evidence_cascade import classify_requirements_batch

        item_one = BatchItem(
            "required:0:aaaaaaaaaaaaaaaa", "required", "Requirement one"
        )
        item_two = BatchItem(
            "required:1:bbbbbbbbbbbbbbbb", "required", "Requirement two"
        )
        sequential = json.dumps(
            {
                "results": [
                    {
                        "item_id": "req-001",
                        "gate": "HARD",
                        "gap_source": "domain",
                        "evidence_level": 0,
                        "confidence": "high",
                        "reasoning": "no evidence for requirement two",
                    },
                    {
                        "item_id": "req-002",
                        "gate": "NONE",
                        "evidence_level": 3,
                        "confidence": "high",
                        "reasoning": "strong match for requirement one",
                    },
                ]
            }
        )
        with patch("utils.call_llm", side_effect=[sequential, sequential]) as call:
            with self.assertRaises(CascadeValidationError) as ctx:
                classify_requirements_batch(
                    [item_one, item_two],
                    settings={
                        "stage0_evidence_classification": {
                            "provider_order": ["groq", "gemini"],
                            "models": {"groq": "groq-test", "gemini": "gemini-test"},
                        }
                    },
                )
        self.assertEqual(call.call_count, 2)
        self.assertIn("unknown batch item_id", str(ctx.exception))
        self.assertIn("req-001", str(ctx.exception))

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

    def test_partial_result_retries_missing_with_same_provider(self) -> None:
        """Truncated response: recovered items are kept, missing items retried with same provider."""
        from stage0_evidence_cascade import classify_requirements_batch

        items = [
            BatchItem(f"required:0:{c}", "required", f"Requirement {c}")
            for c in "abcde"
        ]
        # First call: returns 3 of 5 items (truncation)
        partial = json.dumps({"results": [
            {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
             "confidence": "high", "reasoning": f"evidence for {it.item_id}", "gap_source": ""}
            for it in items[:3]
        ]})
        # Retry: returns the remaining 2
        rest = json.dumps({"results": [
            {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
             "confidence": "high", "reasoning": f"evidence for {it.item_id}", "gap_source": ""}
            for it in items[3:]
        ]})
        with patch("utils.call_llm", side_effect=[partial, rest]) as call:
            result = classify_requirements_batch(
                items,
                settings={"stage0_evidence_classification": {
                    "provider_order": ["groq", "gemini"],
                    "models": {"groq": "groq-test", "gemini": "gemini-test"},
                }},
            )
        self.assertEqual(set(result.keys()), {it.item_id for it in items})
        self.assertEqual(call.call_count, 2)
        # Both calls went to Groq (same-provider retry)
        self.assertEqual(call.call_args_list[0].kwargs["provider_override"], ["groq"])
        self.assertEqual(call.call_args_list[1].kwargs["provider_override"], ["groq"])

    def test_partial_result_falls_back_for_remaining_items(self) -> None:
        """When same-provider retry also fails, fallback gets only the missing items."""
        from stage0_evidence_cascade import classify_requirements_batch

        items = [
            BatchItem(f"required:0:{c}", "required", f"Requirement {c}")
            for c in "abcde"
        ]
        partial = json.dumps({"results": [
            {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
             "confidence": "high", "reasoning": f"evidence for {it.item_id}", "gap_source": ""}
            for it in items[:3]
        ]})
        # Retry with Groq: also partial (returns nothing new)
        empty_retry = json.dumps({"results": []})
        # Gemini: returns the remaining 2
        rest = json.dumps({"results": [
            {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
             "confidence": "high", "reasoning": f"evidence for {it.item_id}", "gap_source": ""}
            for it in items[3:]
        ]})
        with patch("utils.call_llm", side_effect=[partial, empty_retry, rest]) as call:
            result = classify_requirements_batch(
                items,
                settings={"stage0_evidence_classification": {
                    "provider_order": ["groq", "gemini"],
                    "models": {"groq": "groq-test", "gemini": "gemini-test"},
                }},
            )
        self.assertEqual(set(result.keys()), {it.item_id for it in items})
        self.assertEqual(call.call_count, 3)
        # Third call (Gemini) should only have the 2 missing items
        gemini_prompt = call.call_args_list[2].args[1] if call.call_args_list[2].args else call.call_args_list[2].kwargs.get("user_prompt", "")
        # Check via the prompt content — the Gemini call's prompt should contain
        # only items d and e, not a, b, c
        # call_llm is called with (system_prompt, user_prompt, ...) so args[1] is the user prompt
        self.assertIn("required:0:d", call.call_args_list[2].args[1])
        self.assertIn("required:0:e", call.call_args_list[2].args[1])
        self.assertNotIn("required:0:a", call.call_args_list[2].args[1])

    def test_partial_retry_transport_error_falls_back_to_next_provider(self) -> None:
        """A transport error on the same-provider retry must fall back to the
        next configured provider, not crash out of classify_requirements_batch.

        Regression test: the retry call_llm() invocation in the partial-result
        recovery path was not wrapped in the same broad except Exception used
        for every other call_llm() call in this loop, so a timeout/connection
        error during retry propagated uncaught instead of falling back to
        Gemini like the original (pre-retry) provider-loop design guarantees.
        """
        from stage0_evidence_cascade import classify_requirements_batch

        items = [
            BatchItem(f"required:0:{c}", "required", f"Requirement {c}")
            for c in "abcde"
        ]
        partial = json.dumps({"results": [
            {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
             "confidence": "high", "reasoning": f"evidence for {it.item_id}", "gap_source": ""}
            for it in items[:3]
        ]})
        # Gemini fallback: returns the remaining 2
        rest = json.dumps({"results": [
            {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
             "confidence": "high", "reasoning": f"evidence for {it.item_id}", "gap_source": ""}
            for it in items[3:]
        ]})
        with patch(
            "utils.call_llm",
            side_effect=[partial, TimeoutError("groq retry timed out"), rest],
        ) as call:
            result = classify_requirements_batch(
                items,
                settings={"stage0_evidence_classification": {
                    "provider_order": ["groq", "gemini"],
                    "models": {"groq": "groq-test", "gemini": "gemini-test"},
                }},
            )
        self.assertEqual(set(result.keys()), {it.item_id for it in items})
        self.assertEqual(call.call_count, 3)
        self.assertEqual(call.call_args_list[2].kwargs["provider_override"], ["gemini"])

    def test_proactive_split_for_large_estimated_output(self) -> None:
        """When estimated output exceeds the safe threshold, the batch is split."""
        from stage0_evidence_cascade import (
            classify_requirements_batch,
            _estimate_output_tokens,
            _SAFE_OUTPUT_TOKENS,
        )

        # Create items with very long evidence excerpts to trigger the split
        items = [
            BatchItem(f"required:0:{i}", "required", f"Requirement {i}",
                      evidence_excerpt="x" * 2000)
            for i in range(10)
        ]
        # Verify the estimate exceeds the threshold
        self.assertGreater(_estimate_output_tokens(items), _SAFE_OUTPUT_TOKENS)

        def fake_call(system, prompt, **kwargs):
            # Extract item_ids from the prompt format: [required:0:N] bucket=...
            import re
            ids = re.findall(r'\[(required:0:\d+)\]', prompt)
            return json.dumps({"results": [
                {"item_id": item_id, "gate": "NONE", "evidence_level": 2,
                 "confidence": "high", "reasoning": "test evidence", "gap_source": ""}
                for item_id in ids
            ]})

        with patch("utils.call_llm", side_effect=fake_call) as call:
            result = classify_requirements_batch(
                items,
                settings={"stage0_evidence_classification": {
                    "provider_order": ["groq"],
                    "models": {"groq": "groq-test"},
                }},
            )
        self.assertEqual(set(result.keys()), {it.item_id for it in items})
        # Should have been split into 2 calls (3 items each)
        self.assertEqual(call.call_count, 2)

    def test_no_split_for_normal_sized_batch(self) -> None:
        """A normal-sized batch with moderate evidence is not split."""
        from stage0_evidence_cascade import (
            classify_requirements_batch,
            _estimate_output_tokens,
            _SAFE_OUTPUT_TOKENS,
        )

        items = [
            BatchItem(f"required:0:{c}", "required", f"Requirement {c}")
            for c in "abcde"
        ]
        self.assertLess(_estimate_output_tokens(items), _SAFE_OUTPUT_TOKENS)

        def fake_call(system, prompt, **kwargs):
            return json.dumps({"results": [
                {"item_id": it.item_id, "gate": "NONE", "evidence_level": 2,
                 "confidence": "high", "reasoning": "test", "gap_source": ""}
                for it in items
            ]})

        with patch("utils.call_llm", side_effect=fake_call) as call:
            result = classify_requirements_batch(
                items,
                settings={"stage0_evidence_classification": {
                    "provider_order": ["groq"],
                    "models": {"groq": "groq-test"},
                }},
            )
        self.assertEqual(set(result.keys()), {it.item_id for it in items})
        # One call, no split
        self.assertEqual(call.call_count, 1)


class TestSubscriptionEvidenceLiveFixes(unittest.TestCase):
    def _items(self, count: int) -> list[BatchItem]:
        return [
            BatchItem(f"req:{index}", "required", f"Need {index}", "excerpt")
            for index in range(count)
        ]

    def _row(self, item_id: str) -> dict:
        return {
            "item_id": item_id,
            "gate": "NONE",
            "gap_source": "",
            "evidence_level": 3,
            "confidence": "high",
            "reasoning": f"ok {item_id}",
        }

    def _result(self, item_ids: list[str], *, missing: list[str] | None = None, outcome: str = "ok"):
        from stage0_subscription_adapter import AdapterResult

        return AdapterResult(
            outcome,
            "evidence",
            [self._row(item_id) for item_id in item_ids],
            missing or [],
            "harness omitted item_ids" if missing else None,
            1,
            0.1,
            0.0,
            None,
            "k",
            ["agy"],
        )

    def test_subscription_evidence_chunks_like_smoke(self) -> None:
        from stage0_evidence_cascade import classify_requirements_batch

        sizes: list[int] = []

        def fake(_task, items, **_kwargs):
            ids = [item.item_id for item in items]
            sizes.append(len(ids))
            return self._result(ids)

        with patch("stage0_evidence_cascade._subscription_evidence_enabled", return_value=True):
            with patch("stage0_subscription_adapter.run_stage0_subscription", side_effect=fake):
                result = classify_requirements_batch(self._items(7))
        self.assertEqual(sizes, [3, 3, 1])
        self.assertEqual(len(result), 7)

    def test_subscription_evidence_retries_omitted_ids(self) -> None:
        from stage0_evidence_cascade import classify_requirements_batch

        calls: list[list[str]] = []

        def fake(_task, items, **_kwargs):
            ids = [item.item_id for item in items]
            calls.append(ids)
            if len(ids) == 2:
                return self._result(ids[:1], missing=[ids[1]], outcome="review")
            return self._result(ids)

        with patch("stage0_evidence_cascade._subscription_evidence_enabled", return_value=True):
            with patch("stage0_subscription_adapter.run_stage0_subscription", side_effect=fake):
                result = classify_requirements_batch(self._items(2))
        self.assertEqual(calls, [["req:0", "req:1"], ["req:1"]])
        self.assertEqual(set(result.keys()), {"req:0", "req:1"})

    def test_subscription_review_pause_kind_is_not_cost_authorization(self) -> None:
        from build_stage0_fit_gate import Stage0CostAuthorizationNeeded

        cost = Stage0CostAuthorizationNeeded(reason="no_eligible_provider")
        review = Stage0CostAuthorizationNeeded(
            reason="subscription_review:harness omitted item_ids",
            model_call_occurred=True,
        )
        self.assertEqual(cost.pause_kind(), "cost_authorization")
        self.assertEqual(review.pause_kind(), "subscription_review")


if __name__ == "__main__":
    unittest.main()
