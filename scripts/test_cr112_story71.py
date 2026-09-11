#!/usr/bin/env python3
"""CR-112 Stories 7.1 and 7.2 — cost eligibility and unknown-is-not-zero telemetry."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import utils  # noqa: E402
from cost_eligibility import (  # noqa: E402
    CostPauseError,
    authorize_provider_chain,
    classify_provider,
    known_call_receipt,
    offline_zero_call_metrics,
    set_test_zero_charge_providers,
    unknown_refusal_receipt,
)
from stage0_evidence_cascade import (  # noqa: E402
    BatchItem,
    CascadeValidationError,
    classify_requirements_batch,
)


def _item() -> BatchItem:
    return BatchItem(
        item_id="required:0:abcdef0123456789",
        bucket="required",
        requirement="Own the platform",
        evidence_excerpt="Owned the platform.",
    )


class TestStory71Eligibility(unittest.TestCase):
    def tearDown(self) -> None:
        set_test_zero_charge_providers(None)

    def test_missing_class_is_unknown_and_not_callable(self) -> None:
        info = classify_provider("groq", {})
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)
        self.assertFalse(info.cost_known)

    def test_groq_gemini_name_is_not_free(self) -> None:
        settings = {"costClasses": {"groq": "free_only", "gemini": "free_only"}}
        groq = classify_provider("groq", settings)
        gemini = classify_provider("gemini", settings)
        self.assertEqual(groq.cost_class, "unknown")
        self.assertEqual(gemini.cost_class, "unknown")
        self.assertFalse(groq.eligible)
        self.assertFalse(gemini.eligible)

    def test_free_only_requires_zero_charge_assertion(self) -> None:
        set_test_zero_charge_providers(["groq"])
        settings = {"costClasses": {"groq": "free_only"}}
        info = classify_provider("groq", settings)
        self.assertEqual(info.cost_class, "free_only")
        self.assertTrue(info.eligible)
        self.assertTrue(info.cost_known)

    def test_settings_zero_charge_list_is_not_a_backdoor(self) -> None:
        settings = {
            "costClasses": {"groq": "free_only"},
            "testZeroChargeProviders": ["groq"],
        }
        info = classify_provider("groq", settings)
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)

    def test_declared_offline_on_groq_is_unknown(self) -> None:
        info = classify_provider("groq", {"costClasses": {"groq": "offline"}})
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "offline_not_local")

    def test_local_is_offline_by_default(self) -> None:
        info = classify_provider("local", {})
        self.assertEqual(info.cost_class, "offline")
        self.assertTrue(info.eligible)
        self.assertTrue(info.cost_known)
        self.assertEqual(info.estimated_cents, 0)

    def test_paid_budget_zero_is_ineligible(self) -> None:
        settings = {
            "costClasses": {"claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 0,
            "estimatedCentsPerCall": {"claude": 5},
        }
        info = classify_provider("claude", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "paid_budget_empty")

    def test_paid_not_allowlisted_is_ineligible(self) -> None:
        settings = {
            "costClasses": {"claude": "paid_with_budget"},
            "paidProviderAllowlist": ["gemini"],
            "paidBudgetCents": 100,
            "estimatedCentsPerCall": {"claude": 5},
        }
        info = classify_provider("claude", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "paid_not_allowlisted")

    def test_paid_unknown_estimate_is_not_callable(self) -> None:
        settings = {
            "costClasses": {"claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 100,
        }
        info = classify_provider("claude", settings, estimated_tokens=800)
        self.assertFalse(info.eligible)
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.cost_known)

    def test_paid_would_exceed_budget_stops_before_call(self) -> None:
        settings = {
            "costClasses": {"claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 4,
            "estimatedCentsPerCall": {"claude": 5},
        }
        info = classify_provider("claude", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "paid_would_exceed_budget")

    def test_free_to_paid_fallback_is_stripped(self) -> None:
        set_test_zero_charge_providers(["groq"])
        settings = {
            "costClasses": {"groq": "free_only", "claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 100,
            "estimatedCentsPerCall": {"claude": 5},
        }
        auth = authorize_provider_chain(["groq", "claude"], settings)
        self.assertEqual(auth.providers, ["groq"])
        self.assertTrue(auth.seen_free_only)
        paid = [row for row in auth.decisions if row.provider == "claude"][0]
        self.assertEqual(paid.reason, "free_to_paid_forbidden")
        self.assertFalse(paid.eligible)

    def test_default_groq_gemini_chain_pauses(self) -> None:
        auth = authorize_provider_chain(["groq", "gemini"], {})
        self.assertTrue(auth.pause)
        with self.assertRaises(CostPauseError) as ctx:
            from cost_eligibility import raise_if_pause

            raise_if_pause(auth)
        self.assertNotIn("api_cents", ctx.exception.receipt)
        self.assertFalse(ctx.exception.receipt["cost_known"])

    def test_call_llm_does_not_invoke_unknown_groq(self) -> None:
        settings = {"costClasses": {"groq": "unknown"}}
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq") as groq:
                        with self.assertRaises(CostPauseError):
                            utils.call_llm(
                                "sys",
                                "user",
                                provider_override=["groq"],
                                cost_settings=settings,
                            )
                        groq.assert_not_called()

    def test_call_llm_free_only_does_not_fall_back_to_paid(self) -> None:
        import cost_eligibility

        set_test_zero_charge_providers(["groq"])
        settings = {
            "costClasses": {"groq": "free_only", "claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 100,
            "estimatedCentsPerCall": {"claude": 5},
        }
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq", return_value=None) as groq:
                        with patch.object(utils, "_call_claude") as claude:
                            result = utils.call_llm(
                                "sys",
                                "user",
                                provider_override=["groq", "claude"],
                                cost_settings=settings,
                            )
        self.assertEqual(result, "")
        groq.assert_called_once()
        claude.assert_not_called()
        receipt = cost_eligibility.LAST_RECEIPT
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["cost_class"], "free_only")
        self.assertTrue(receipt["cost_known"])
        self.assertEqual(receipt["api_cents"], 0)
        self.assertEqual(receipt["reason"], "providers_exhausted")

    def test_stage0_unknown_chain_does_not_call_provider_adapters(self) -> None:
        settings = {
            "stage0_evidence_classification": {"provider_order": ["groq", "gemini"]}
        }
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq") as groq:
                        with patch.object(utils, "_call_gemini") as gemini:
                            with self.assertRaises(CostPauseError):
                                classify_requirements_batch(
                                    [_item()],
                                    settings=settings,
                                )
                            groq.assert_not_called()
                            gemini.assert_not_called()

    def test_stage0_free_only_does_not_fall_back_to_paid(self) -> None:
        set_test_zero_charge_providers(["groq"])
        settings = {
            "stage0_evidence_classification": {"provider_order": ["groq", "gemini"]},
            "costClasses": {"groq": "free_only", "gemini": "paid_with_budget"},
            "paidProviderAllowlist": ["gemini"],
            "paidBudgetCents": 100,
            "estimatedCentsPerCall": {"gemini": 5},
        }
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq", return_value="") as groq:
                        with patch.object(utils, "_call_gemini") as gemini:
                            with self.assertRaises((CostPauseError, CascadeValidationError)):
                                classify_requirements_batch(
                                    [_item()],
                                    settings=settings,
                                )
                            groq.assert_called()
                            gemini.assert_not_called()


class TestStory72Telemetry(unittest.TestCase):
    def test_unknown_refusal_omits_api_cents(self) -> None:
        row = unknown_refusal_receipt(provider="groq", estimated_tokens=12)
        self.assertFalse(row["cost_known"])
        self.assertEqual(row["cost_class"], "unknown")
        self.assertNotIn("api_cents", row)
        self.assertEqual(row["subscription_minutes"], 0)

    def test_known_free_may_record_zero(self) -> None:
        row = known_call_receipt(
            provider="groq",
            cost_class="free_only",
            estimated_tokens=12,
            api_cents=0,
        )
        self.assertTrue(row["cost_known"])
        self.assertEqual(row["api_cents"], 0)

    def test_offline_eval_metrics_are_known_zero(self) -> None:
        row = offline_zero_call_metrics()
        self.assertEqual(row["cost_class"], "offline")
        self.assertTrue(row["cost_known"])
        self.assertEqual(row["api_cents"], 0)
        self.assertEqual(row["invocations"], 0)

    def test_eval_harness_labels_offline_and_does_not_import_call_llm(self) -> None:
        from test_cr112_story61 import ImportGuard
        from run_cr112_eval import run_eval

        with tempfile.TemporaryDirectory() as tmp:
            guard = ImportGuard("call_llm")
            with patch("builtins.__import__", side_effect=guard):
                summary = run_eval(
                    Path(tmp) / "eval",
                    paid_llm=False,
                    assemble_packets=False,
                    sqlite_path=None,
                )
        self.assertTrue(summary["totals"]["cost_known"])
        self.assertEqual(summary["totals"]["cost_class"], "offline")
        self.assertEqual(summary["totals"]["api_cents"], 0)
        for folder in summary["folders"]:
            self.assertTrue(folder["cost_known"])
            self.assertEqual(folder["cost_class"], "offline")

    def test_call_llm_unknown_receipt_never_stores_zero_cents(self) -> None:
        import cost_eligibility

        settings = {}
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with self.assertRaises(CostPauseError):
                        utils.call_llm(
                            "sys",
                            "user",
                            provider_override=["gemini"],
                            cost_settings=settings,
                        )
        receipt = cost_eligibility.LAST_RECEIPT
        self.assertIsNotNone(receipt)
        self.assertFalse(receipt["cost_known"])
        self.assertNotIn("api_cents", receipt)
        self.assertNotEqual(receipt.get("api_cents", "missing"), 0)


if __name__ == "__main__":
    unittest.main()
