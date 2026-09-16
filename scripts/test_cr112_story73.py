#!/usr/bin/env python3
"""CR-112 Story 7.3 — operator free-tier attestation (groq/gemini) as certify_zero_charge.

Implements AC-424. All tests are offline: provider adapters are mocked, no
network, no production SQLite, no submission folders. The attestation is the
only settings-based form of the certify_zero_charge resume path (FR-326);
everything else about Stories 7.1/7.2 (paid allowlist, budgets, estimates,
free->paid stripping, cascade import, pause contract) must stay unchanged.
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import utils  # noqa: E402
import cost_eligibility  # noqa: E402
from cost_eligibility import (  # noqa: E402
    OPERATOR_FREE_TIER_ASSERTION_MAX_AGE_DAYS,
    OPERATOR_FREE_TIER_CERTIFIABLE,
    OPERATOR_FREE_TIER_STATEMENT,
    adapter_can_assert_zero_charge,
    authorize_provider_chain,
    classify_provider,
    operator_asserted_at,
    operator_free_tier_assertion,
    set_test_zero_charge_providers,
)


def _attestation(provider_name: str, **overrides) -> dict:
    """A valid operator attestation record for provider_name, unless overridden."""
    record = {
        "provider": provider_name,
        "acknowledged": True,
        "statement": OPERATOR_FREE_TIER_STATEMENT[provider_name],
        "asserted_at": datetime.now(timezone.utc).isoformat(),
    }
    record.update(overrides)
    return record


def _free_settings(provider_name: str = "groq", **attestation_overrides) -> dict:
    """Declared free_only plus a matching attestation for one provider."""
    return {
        "costClasses": {provider_name: "free_only"},
        "freeTierAssertions": {
            provider_name: _attestation(provider_name, **attestation_overrides)
        },
    }


class TestStory73AttestationShape(unittest.TestCase):
    def tearDown(self) -> None:
        set_test_zero_charge_providers(None)

    def test_constants_cover_exactly_groq_and_gemini(self) -> None:
        self.assertEqual(OPERATOR_FREE_TIER_CERTIFIABLE, frozenset({"groq", "gemini"}))
        self.assertEqual(set(OPERATOR_FREE_TIER_STATEMENT), {"groq", "gemini"})
        self.assertEqual(OPERATOR_FREE_TIER_ASSERTION_MAX_AGE_DAYS, 30)
        for provider, statement in OPERATOR_FREE_TIER_STATEMENT.items():
            self.assertIn(provider.capitalize(), statement)
            self.assertIn("cannot incur a charge", statement)

    def test_valid_attestation_plus_declared_free_only_is_eligible(self) -> None:
        for provider in ("groq", "gemini"):
            with self.subTest(provider=provider):
                settings = _free_settings(provider)
                info = classify_provider(provider, settings)
                self.assertEqual(info.cost_class, "free_only")
                self.assertTrue(info.eligible)
                self.assertTrue(info.cost_known)
                self.assertEqual(info.estimated_cents, 0)
                self.assertTrue(adapter_can_assert_zero_charge(provider, settings))

    def test_declared_free_only_without_attestation_stays_unknown(self) -> None:
        settings = {"costClasses": {"groq": "free_only"}}
        info = classify_provider("groq", settings)
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "free_only_assertion_missing")

    def test_attestation_without_declaration_is_inert(self) -> None:
        settings = {"freeTierAssertions": {"groq": _attestation("groq")}}
        info = classify_provider("groq", settings)
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "unknown_cost_class")

    def test_statement_one_character_drift_is_invalid(self) -> None:
        drifted = OPERATOR_FREE_TIER_STATEMENT["groq"][:-1] + "X"
        settings = _free_settings("groq", statement=drifted)
        info = classify_provider("groq", settings)
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "free_only_assertion_invalid")

    def test_provider_field_mismatch_is_invalid(self) -> None:
        settings = _free_settings("groq", provider="gemini")
        info = classify_provider("groq", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "free_only_assertion_invalid")

    def test_acknowledged_must_be_strict_true(self) -> None:
        for bad in (1, "true", "yes", None):
            with self.subTest(acknowledged=bad):
                settings = _free_settings("groq", acknowledged=bad)
                info = classify_provider("groq", settings)
                self.assertEqual(info.cost_class, "unknown")
                self.assertFalse(info.eligible)
                self.assertEqual(info.reason, "free_only_assertion_invalid")
        record = _attestation("groq")
        del record["acknowledged"]
        settings = {
            "costClasses": {"groq": "free_only"},
            "freeTierAssertions": {"groq": record},
        }
        info = classify_provider("groq", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "free_only_assertion_invalid")

    def test_claude_and_perplexity_are_not_certifiable(self) -> None:
        for provider in ("claude", "perplexity"):
            with self.subTest(provider=provider):
                record = {
                    "provider": provider,
                    "acknowledged": True,
                    "statement": "I certify anything.",
                    "asserted_at": datetime.now(timezone.utc).isoformat(),
                }
                settings = {
                    "costClasses": {provider: "free_only"},
                    "freeTierAssertions": {provider: record},
                }
                info = classify_provider(provider, settings)
                self.assertEqual(info.cost_class, "unknown")
                self.assertFalse(info.eligible)
                self.assertEqual(info.reason, "free_only_assertion_not_certifiable")

    def test_expired_attestation_is_unknown(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(
            days=OPERATOR_FREE_TIER_ASSERTION_MAX_AGE_DAYS + 1
        )
        settings = _free_settings("groq", asserted_at=old.isoformat())
        info = classify_provider("groq", settings)
        self.assertEqual(info.cost_class, "unknown")
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "free_only_assertion_expired")

    def test_naive_or_garbage_timestamp_is_invalid(self) -> None:
        for bad in ("2026-09-01T00:00:00", "not a date", "", None, 12345):
            with self.subTest(asserted_at=bad):
                settings = _free_settings("groq", asserted_at=bad)
                info = classify_provider("groq", settings)
                self.assertFalse(info.eligible)
                self.assertEqual(info.reason, "free_only_assertion_invalid")

    def test_fresh_attestation_at_day_29_is_still_valid(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(days=29)
        settings = _free_settings("gemini", asserted_at=recent.isoformat())
        info = classify_provider("gemini", settings)
        self.assertTrue(info.eligible)
        self.assertEqual(info.cost_class, "free_only")

    def test_unknown_blob_keys_are_ignored(self) -> None:
        settings = {
            "freeTierAssertions": {"local": _attestation("groq", provider="local")}
        }
        ok, reason = operator_free_tier_assertion("local", settings)
        self.assertFalse(ok)
        self.assertEqual(reason, "free_only_assertion_not_certifiable")
        # local stays offline regardless of the stray key.
        info = classify_provider("local", settings)
        self.assertEqual(info.cost_class, "offline")
        self.assertTrue(info.eligible)
        # A near-miss key does not unlock the real provider.
        settings = {
            "costClasses": {"groq": "free_only"},
            "freeTierAssertions": {" Groq": _attestation("groq")},
        }
        info = classify_provider("groq", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "free_only_assertion_missing")

    def test_malformed_inputs_never_raise(self) -> None:
        for settings in (
            None,
            {},
            {"freeTierAssertions": None},
            {"freeTierAssertions": ["groq"]},
            {"freeTierAssertions": "groq"},
            {"freeTierAssertions": {"groq": None}},
            {"freeTierAssertions": {"groq": "yes"}},
            {"freeTierAssertions": {"groq": []}},
            {"freeTierAssertions": {"groq": {}}},
        ):
            with self.subTest(settings=settings):
                self.assertFalse(adapter_can_assert_zero_charge("groq", settings))

    def test_assertion_never_unlocks_paid_class(self) -> None:
        # An attestation does not change a paid declaration; paid rules still govern.
        settings = _free_settings("groq")
        settings["costClasses"]["groq"] = "paid_with_budget"
        info = classify_provider("groq", settings)
        self.assertFalse(info.eligible)
        self.assertEqual(info.reason, "paid_not_allowlisted")


class TestStory73ChainAndTelemetry(unittest.TestCase):
    def tearDown(self) -> None:
        set_test_zero_charge_providers(None)

    def test_attested_call_receipt_marks_operator_assertion(self) -> None:
        settings = _free_settings("groq")
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq", return_value="ok") as groq:
                        result = utils.call_llm(
                            "sys",
                            "user",
                            provider_override=["groq"],
                            cost_settings=settings,
                        )
        self.assertEqual(result, "ok")
        groq.assert_called_once()
        receipt = cost_eligibility.LAST_RECEIPT
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["cost_class"], "free_only")
        self.assertTrue(receipt["cost_known"])
        self.assertEqual(receipt["cost_confidence"], "zero")
        self.assertEqual(receipt["api_cents"], 0)
        self.assertEqual(receipt["zero_charge_basis"], "operator_assertion")
        self.assertEqual(
            receipt["assertion_asserted_at"],
            settings["freeTierAssertions"]["groq"]["asserted_at"],
        )
        self.assertEqual(receipt["subscription_minutes"], 0)

    def test_stub_free_call_has_no_operator_basis(self) -> None:
        set_test_zero_charge_providers(["groq"])
        settings = {"costClasses": {"groq": "free_only"}}
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq", return_value="ok"):
                        utils.call_llm(
                            "sys",
                            "user",
                            provider_override=["groq"],
                            cost_settings=settings,
                        )
        receipt = cost_eligibility.LAST_RECEIPT
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["api_cents"], 0)
        self.assertNotIn("zero_charge_basis", receipt)
        self.assertNotIn("assertion_asserted_at", receipt)

    def test_operator_asserted_at_echo(self) -> None:
        settings = _free_settings("gemini")
        self.assertEqual(
            operator_asserted_at("gemini", settings),
            settings["freeTierAssertions"]["gemini"]["asserted_at"],
        )
        self.assertIsNone(operator_asserted_at("gemini", {}))
        self.assertIsNone(operator_asserted_at("local", settings))

    def test_attested_groq_strips_paid_claude_in_one_chain(self) -> None:
        settings = _free_settings("groq")
        settings["costClasses"]["claude"] = "paid_with_budget"
        settings["paidProviderAllowlist"] = ["claude"]
        settings["paidBudgetCents"] = 100
        settings["estimatedCentsPerCall"] = {"claude": 5}
        auth = authorize_provider_chain(["groq", "claude"], settings)
        self.assertEqual(auth.providers, ["groq"])
        paid = [row for row in auth.decisions if row.provider == "claude"][0]
        self.assertEqual(paid.reason, "free_to_paid_forbidden")
        self.assertFalse(paid.eligible)
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

    def test_invalid_attestation_chain_pauses_without_api_cents(self) -> None:
        settings = _free_settings("groq", statement="I certify nothing in particular.")
        auth = authorize_provider_chain(["groq"], settings)
        self.assertTrue(auth.pause)
        with self.assertRaises(cost_eligibility.CostPauseError) as ctx:
            cost_eligibility.raise_if_pause(auth)
        receipt = ctx.exception.receipt
        self.assertEqual(receipt["reason"], "free_only_assertion_invalid")
        self.assertEqual(receipt["authorization_mode"], "free_only")
        self.assertFalse(receipt["model_call_occurred"])
        self.assertNotIn("api_cents", receipt)
        ineligible = receipt["ineligible_providers"][0]
        self.assertEqual(ineligible["provider"], "groq")
        self.assertEqual(ineligible["reason"], "free_only_assertion_invalid")

    def test_default_install_pause_shape_unchanged(self) -> None:
        # No attestation anywhere: byte-identical default behavior to Story 7.1.
        auth = authorize_provider_chain(["groq", "gemini"], {})
        self.assertTrue(auth.pause)
        with self.assertRaises(cost_eligibility.CostPauseError) as ctx:
            cost_eligibility.raise_if_pause(auth)
        receipt = ctx.exception.receipt
        self.assertEqual(receipt["cost_class"], "unknown")
        self.assertFalse(receipt["cost_known"])
        self.assertNotIn("api_cents", receipt)
        reasons = {row["reason"] for row in receipt["ineligible_providers"]}
        self.assertEqual(reasons, {"unknown_cost_class"})


_SECTIONS = {
    "required": ["Own the platform roadmap"],
    "preferred": [],
    "responsibilities": [],
    "culture": [],
}


class TestStory73Stage0Pause(unittest.TestCase):
    """run_stage0 with an expired attestation pauses; no model call occurs."""

    def tearDown(self) -> None:
        set_test_zero_charge_providers(None)

    def _stage0_ctx(self, settings: dict, db_path: str):
        env = {
            "STAGE0_SECTION_MODE": "deterministic",
            "APPLYR_STAGE0_REVIEW_DB": db_path,
        }
        stack = contextlib.ExitStack()
        stack.enter_context(patch.dict(os.environ, env, clear=False))
        stack.enter_context(
            patch("build_stage0_fit_gate._extract_sections", return_value=_SECTIONS)
        )
        stack.enter_context(patch("utils.load_llm_settings", return_value=settings))
        stack.enter_context(
            patch("utils.load_candidate_preferences", return_value={"blocked_companies": []})
        )
        stack.enter_context(
            patch("stage0_db_gate.evaluate_db_gate", return_value={"action": "clear"})
        )
        stack.enter_context(patch("stage0_skip_ledger.lookup_skip", return_value=None))
        stack.enter_context(
            patch("utils.load_file", return_value="Owned the platform roadmap.")
        )
        stack.enter_context(patch.object(utils, "_is_configured", return_value=True))
        stack.enter_context(patch("utils.check_rate_limits", return_value=True))
        groq_patch = stack.enter_context(patch.object(utils, "_call_groq"))
        gemini_patch = stack.enter_context(patch.object(utils, "_call_gemini"))
        return stack, groq_patch, gemini_patch

    def test_run_stage0_expired_attestation_pauses_with_reason(self) -> None:
        from workflow.runner import run_stage0
        from workflow.receipts import load_receipt, write_state
        from workflow.state import init_state

        old = datetime.now(timezone.utc) - timedelta(
            days=OPERATOR_FREE_TIER_ASSERTION_MAX_AGE_DAYS + 1
        )
        settings = {
            "stage0_evidence_classification": {"provider_order": ["groq"]},
            "costClasses": {"groq": "free_only"},
            "freeTierAssertions": {"groq": _attestation("groq", asserted_at=old.isoformat())},
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = Path(tmp) / "review.sqlite"
            db_path.touch()
            state = init_state(str(folder))
            write_state(str(folder), state)
            stack, groq, gemini = self._stage0_ctx(settings, str(db_path))
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            gemini.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            receipt = load_receipt(str(folder), "stage0")
            result = receipt["result"]
            self.assertEqual(result["pause_kind"], "cost_authorization")
            self.assertFalse(result["model_call_occurred"])
            self.assertNotIn("api_cents", result)
            self.assertEqual(result["reason"], "free_only_assertion_expired")
            self.assertIn("certify_zero_charge", result["next_paths"])
            ineligible = result["ineligible_providers"][0]
            self.assertEqual(ineligible["provider"], "groq")
            self.assertEqual(ineligible["reason"], "free_only_assertion_expired")


if __name__ == "__main__":
    unittest.main()
