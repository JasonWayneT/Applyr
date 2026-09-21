"""CR-114 Story 3: uncertain extraction uses the subscription adapter when enabled."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_stage0_fit_gate as fit_gate
import stage0_subscription_adapter as adapter


QUEUE = [
    ("[HEADER] required: Must have SQL", "Must have SQL", "required"),
    ("[HEADER] required: Nice Jira experience", "Nice Jira experience", "required"),
]


def _buckets() -> dict[str, list[str]]:
    return fit_gate._empty_extraction_buckets()


class SubscriptionExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.pop(adapter.ENABLED_ENV, None)

    def tearDown(self) -> None:
        if self._env is None:
            os.environ.pop(adapter.ENABLED_ENV, None)
        else:
            os.environ[adapter.ENABLED_ENV] = self._env

    def test_disabled_switch_keeps_groq_path(self) -> None:
        os.environ[adapter.CLOUD_LLM_ENV] = "1"
        self.addCleanup(os.environ.pop, adapter.CLOUD_LLM_ENV, None)
        with patch.object(fit_gate, "_resolve_uncertain_extraction_llm", return_value=[]) as llm, patch.object(
            fit_gate, "_resolve_uncertain_extraction_subscription"
        ) as sub:
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, _buckets())
        self.assertEqual(unresolved, [])
        llm.assert_called_once()
        sub.assert_not_called()

    def test_disabled_switch_without_cloud_llm_does_not_call_groq(self) -> None:
        os.environ.pop(adapter.CLOUD_LLM_ENV, None)
        with patch.object(fit_gate, "_resolve_uncertain_extraction_llm") as llm, patch.object(
            fit_gate, "_resolve_uncertain_extraction_subscription"
        ) as sub:
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, _buckets())
        llm.assert_not_called()
        sub.assert_not_called()
        self.assertEqual(len(unresolved), 2)
        self.assertEqual(unresolved[0]["reason"], "subscription_adapter_required")
        self.assertFalse(unresolved[0]["model_call_occurred"])

    def test_enabled_switch_never_calls_llm(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "ok", "extraction",
            [{"item_id": "e0", "bucket": "required"}, {"item_id": "e1", "bucket": "preferred"}],
            [], None, 1, 0.2, 0.003, None, "k", ["npx"],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result) as run, patch(
            "utils.call_llm"
        ) as llm:
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        self.assertEqual(unresolved, [])
        self.assertEqual(buckets["required"], ["Must have SQL"])
        self.assertEqual(buckets["preferred"], ["Nice Jira experience"])
        run.assert_called_once()
        llm.assert_not_called()
        self.assertEqual(run.call_args.args[0], "extraction")
        self.assertEqual([item.item_id for item in run.call_args.args[1]], ["e0", "e1"])

    def test_partial_mapping_preserves_missing_line(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "review", "extraction",
            [{"item_id": "e0", "bucket": "required"}],
            ["e1"], "harness omitted item_ids", 1, 0.1, 0.001, None, "k", ["npx"],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result):
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        self.assertEqual(buckets["required"], ["Must have SQL"])
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["text"], "Nice Jira experience")
        self.assertEqual(unresolved[0]["reason"], "partial_mapping_unresolved")
        self.assertTrue(unresolved[0]["model_call_occurred"])
        self.assertNotIn("Nice Jira experience", buckets["responsibilities"])

    def test_timeout_goes_to_review_not_a_bucket(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "review", "extraction", [], ["e0", "e1"], "harness timed out",
            1, 5.0, 5.0 / 60.0, None, "k", ["npx"],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result):
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        self.assertEqual(len(unresolved), 2)
        self.assertTrue(all(row["reason"] == "parse_failure" for row in unresolved))
        self.assertEqual(buckets["required"], [])
        self.assertEqual(buckets["responsibilities"], [])

    def test_exhausted_cap_preserves_every_line(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "exhausted", "extraction", [], ["e0", "e1"], "call ceiling exhausted",
            8, 0.0, 0.0, None, None, [],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result):
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        self.assertEqual([row["text"] for row in unresolved], ["Must have SQL", "Nice Jira experience"])
        self.assertTrue(all(row["reason"] == "no_provider" for row in unresolved))

    def test_cache_hit_does_not_call_llm(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "cache_hit", "extraction",
            [{"item_id": "e0", "bucket": "culture"}, {"item_id": "e1", "bucket": "responsibilities"}],
            [], None, 0, 0.0, 0.0, None, "k", [],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result), patch(
            "utils.call_llm"
        ) as llm:
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        self.assertEqual(unresolved, [])
        self.assertEqual(buckets["culture"], ["Must have SQL"])
        llm.assert_not_called()

    def test_junk_label_lands_in_junk_not_culture(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "ok", "extraction",
            [
                {"item_id": "e0", "bucket": "junk"},
                {"item_id": "e1", "bucket": "required"},
            ],
            [], None, 1, 0.2, 0.003, None, "k", ["npx"],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result), patch(
            "utils.call_llm"
        ) as llm:
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        self.assertEqual(unresolved, [])
        self.assertEqual(buckets["junk"], ["Must have SQL"])
        self.assertEqual(buckets["required"], ["Nice Jira experience"])
        self.assertEqual(buckets["culture"], [])
        llm.assert_not_called()

    def test_disposition_agy_required_is_forced_to_culture(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        queue = [
            (
                "[HEADER] The Role: You are excited to work in a startup environment",
                "You are excited to work in a startup environment",
                "The Role",
            ),
            (
                "[HEADER] The Role: Has shipped AI-enabled products into production.",
                "Has shipped AI-enabled products into production.",
                "The Role",
            ),
        ]
        result = adapter.AdapterResult(
            "ok", "extraction",
            [
                {"item_id": "e0", "bucket": "required"},
                {"item_id": "e1", "bucket": "required"},
            ],
            [], None, 1, 0.2, 0.003, None, "k", ["npx"],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result), patch(
            "utils.call_llm"
        ) as llm:
            unresolved = fit_gate._resolve_uncertain_extraction(queue, buckets)
        self.assertEqual(unresolved, [])
        self.assertEqual(buckets["culture"], ["You are excited to work in a startup environment"])
        self.assertEqual(buckets["required"], ["Has shipped AI-enabled products into production."])
        llm.assert_not_called()

    def test_malformed_adapter_result_does_not_lose_lines(self) -> None:
        os.environ[adapter.ENABLED_ENV] = "1"
        result = adapter.AdapterResult(
            "review", "extraction", [], ["e0", "e1"], "invalid harness output",
            1, 0.1, 0.001, None, "k", ["npx"],
        )
        buckets = _buckets()
        with patch.object(adapter, "run_stage0_subscription", return_value=result), patch(
            "utils.call_llm"
        ) as llm:
            unresolved = fit_gate._resolve_uncertain_extraction(QUEUE, buckets)
        llm.assert_not_called()
        self.assertEqual(len(unresolved), 2)
        self.assertTrue(all(row["model_call_occurred"] for row in unresolved))


if __name__ == "__main__":
    unittest.main()
