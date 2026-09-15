#!/usr/bin/env python3
"""CR-112 Stories 7.1 and 7.2 — cost eligibility and unknown-is-not-zero telemetry."""
from __future__ import annotations

import contextlib
import json
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

    def test_unproven_free_only_does_not_unlock_paid(self) -> None:
        settings = {
            "costClasses": {"groq": "free_only", "claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 100,
            "estimatedCentsPerCall": {"claude": 5},
        }
        auth = authorize_provider_chain(["groq", "claude"], settings)
        self.assertTrue(auth.pause)
        self.assertEqual(auth.providers, [])
        paid = [row for row in auth.decisions if row.provider == "claude"][0]
        self.assertEqual(paid.reason, "free_to_paid_forbidden")
        self.assertFalse(paid.eligible)
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq") as groq:
                        with patch.object(utils, "_call_claude") as claude:
                            with self.assertRaises(CostPauseError) as ctx:
                                utils.call_llm(
                                    "sys",
                                    "user",
                                    provider_override=["groq", "claude"],
                                    cost_settings=settings,
                                )
                            groq.assert_not_called()
                            claude.assert_not_called()
        self.assertEqual(ctx.exception.receipt["authorization_mode"], "free_only")
        self.assertNotIn("api_cents", ctx.exception.receipt)

    def test_two_paid_calls_share_ledger_and_stop_before_second(self) -> None:
        from cost_eligibility import budget_ledger_from_settings

        settings = {
            "costClasses": {"claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 5,
            "estimatedCentsPerCall": {"claude": 5},
        }
        ledger = budget_ledger_from_settings(settings)
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_claude", return_value="ok") as claude:
                        first = utils.call_llm(
                            "sys",
                            "user",
                            provider_override=["claude"],
                            cost_settings=settings,
                            cost_ledger=ledger,
                        )
                        self.assertEqual(first, "ok")
                        with self.assertRaises(CostPauseError):
                            utils.call_llm(
                                "sys",
                                "user",
                                provider_override=["claude"],
                                cost_settings=settings,
                                cost_ledger=ledger,
                            )
                        self.assertEqual(claude.call_count, 1)

    def test_manual_paste_never_calls_cloud(self) -> None:
        settings = {"costClasses": {"groq": "manual_paste", "gemini": "manual_paste"}}
        with patch.object(utils, "load_llm_settings", return_value=settings):
            with patch.object(utils, "_is_configured", return_value=True):
                with patch.object(utils, "check_rate_limits", return_value=True):
                    with patch.object(utils, "_call_groq") as groq:
                        with patch.object(utils, "_call_gemini") as gemini:
                            with self.assertRaises(CostPauseError):
                                utils.call_llm(
                                    "sys",
                                    "user",
                                    provider_override=["groq", "gemini"],
                                    cost_settings=settings,
                                )
                            groq.assert_not_called()
                            gemini.assert_not_called()

    def test_classify_does_not_consume_unbound_import_file(self) -> None:
        item = _item()
        settings = {
            "stage0_evidence_classification": {"provider_order": ["groq"]}
        }
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "item_id": item.item_id,
                                "gate": "NONE",
                                "evidence_level": 4,
                                "confidence": "high",
                                "reasoning": "Owned the platform in prior work.",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(utils, "_call_groq") as groq:
                with self.assertRaises(CostPauseError):
                    classify_requirements_batch(
                        [item],
                        settings=settings,
                        folder=folder,
                    )
                groq.assert_not_called()

    def test_invalid_cascade_import_does_not_call_providers(self) -> None:
        from stage0_evidence_cascade import try_load_cascade_import

        item = _item()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "stage0_cascade_import.json").write_text(
                "{not json",
                encoding="utf-8",
            )
            with patch.object(utils, "_call_groq") as groq:
                with self.assertRaises(CascadeValidationError):
                    try_load_cascade_import(
                        folder,
                        [item],
                        submission_slug=folder.name,
                        jd_sha256="abc",
                    )
                groq.assert_not_called()

    def test_run_stage0_cost_pause_writes_waiting_for_input(self) -> None:
        from build_stage0_fit_gate import Stage0CostAuthorizationNeeded
        from workflow.runner import run_stage0
        from workflow.receipts import write_state, load_receipt
        from workflow.state import init_state
        import contracts

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "acme"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text("Product Manager\n", encoding="utf-8")
            state = init_state(str(folder))
            write_state(str(folder), state)
            pause = Stage0CostAuthorizationNeeded(
                authorization_mode="unknown",
                reason="unknown_cost_class",
                ineligible_providers=[
                    {"provider": "groq", "cost_class": "unknown", "reason": "unknown_cost_class"}
                ],
                model_call_occurred=False,
            )
            with patch("workflow.runner.build_stage0_fit_gate", side_effect=pause):
                out = run_stage0(str(folder), state)
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            self.assertEqual(out["active_stage"], "stage0")
            receipt = load_receipt(str(folder), "stage0")
            self.assertEqual(receipt["status"], "WAITING_FOR_INPUT")
            self.assertEqual(receipt["result"]["pause_kind"], "cost_authorization")
            self.assertFalse(receipt["result"]["model_call_occurred"])
            msg = contracts.waiting_for_input_message(str(folder))
            self.assertIn("Do not paste authoring_prompt.md", msg)
            self.assertIn("cost authorization", msg)
            ok, errors = contracts.check_workflow_complete(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("cost authorization" in e for e in errors))
            self.assertTrue(any("No model API call occurred" in e for e in errors))
            self.assertTrue(any("Do not paste authoring_prompt.md" in e for e in errors))


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


_SECTIONS = {
    "required": ["Own the platform roadmap"],
    "preferred": [],
    "responsibilities": [],
    "culture": [],
}


def _fill_template(template: dict) -> dict:
    filled = json.loads(json.dumps(template))
    for row in filled.get("results") or []:
        row["reasoning"] = "Owned the platform roadmap in prior work."
    return filled


class TestStory71FollowUpContracts(unittest.TestCase):
    def _db(self, folder: Path) -> str:
        path = folder / "review.sqlite"
        path.touch()
        return str(path)

    def _stage0_ctx(self, settings: dict, db_path: str, *, groq=None, gemini=None):
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
        groq_patch = stack.enter_context(
            patch.object(utils, "_call_groq", side_effect=groq)
        )
        gemini_patch = stack.enter_context(
            patch.object(utils, "_call_gemini", side_effect=gemini)
        )
        return stack, groq_patch, gemini_patch

    def _pause_once(self, folder: Path, db_path: str):
        from workflow.runner import run_stage0
        from workflow.state import init_state
        from workflow.receipts import write_state

        settings = {
            "stage0_evidence_classification": {"provider_order": ["groq"]},
            "costClasses": {"groq": "unknown"},
        }
        state = init_state(str(folder))
        write_state(str(folder), state)
        stack, groq, gemini = self._stage0_ctx(settings, db_path)
        with stack:
            out = run_stage0(str(folder), state)
        return out, groq, gemini

    def test_persisted_budget_survives_new_ledger(self) -> None:
        from cost_eligibility import (
            budget_ledger_from_settings,
            overlay_persisted_budget,
        )
        from stage0_checkpoint import get_run_metadata, start_run, update_run_metadata

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ckpt.sqlite"
            start_run(
                db_path,
                run_key="run-1",
                opportunity_key="example-co",
                jd_hash="jd",
                prompt_version="v1",
                provider_policy_hash="policy",
                evidence_index_hash="index",
            )
            update_run_metadata(db_path, "run-1", {"paid_remaining_cents": 3})
            settings = {
                "paidBudgetCents": 10,
                "paidBatchBudgetCents": 10,
            }
            ledger = budget_ledger_from_settings(settings)
            self.assertEqual(ledger.remaining_cents, 10)
            overlay_persisted_budget(ledger, get_run_metadata(db_path, "run-1"))
            self.assertEqual(ledger.remaining_cents, 3)

    def test_second_call_cannot_receive_original_full_budget(self) -> None:
        from cost_eligibility import budget_ledger_from_settings

        settings = {
            "costClasses": {"claude": "paid_with_budget"},
            "paidProviderAllowlist": ["claude"],
            "paidBudgetCents": 5,
            "estimatedCentsPerCall": {"claude": 5},
        }
        ledger = budget_ledger_from_settings(settings)
        with patch.object(utils, "_is_configured", return_value=True):
            with patch.object(utils, "check_rate_limits", return_value=True):
                with patch.object(utils, "_call_claude", return_value="ok"):
                    utils.call_llm(
                        "sys",
                        "user",
                        provider_override=["claude"],
                        cost_settings=settings,
                        cost_ledger=ledger,
                    )
                    with self.assertRaises(CostPauseError):
                        utils.call_llm(
                            "sys",
                            "user",
                            provider_override=["claude"],
                            cost_settings=settings,
                            cost_ledger=ledger,
                        )
        self.assertLess(ledger.remaining_cents, 5)

    def test_real_builder_cost_pause_is_waiting_not_failed(self) -> None:
        from workflow.receipts import load_receipt
        import contracts

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            out, groq, gemini = self._pause_once(folder, db_path)
            groq.assert_not_called()
            gemini.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            self.assertNotEqual(out["status"], "FAILED")
            receipt = load_receipt(str(folder), "stage0")
            self.assertEqual(receipt["result"]["pause_kind"], "cost_authorization")
            self.assertFalse(receipt["result"]["model_call_occurred"])
            self.assertFalse(receipt["result"]["cost_applicable"])
            self.assertNotIn("api_cents", receipt["result"])
            self.assertTrue((folder / "stage0_cascade_import.template.json").is_file())
            msg = contracts.waiting_for_input_message(str(folder))
            self.assertIn(str(folder), msg)
            self.assertIn("--resume", msg)
            self.assertIn("stage0_cascade_import.json", msg)
            ok, errors = contracts.check_workflow_complete(str(folder))
            self.assertFalse(ok)
            self.assertTrue(any("cost authorization" in e for e in errors))

    def test_resume_without_new_input_stays_paused_and_makes_zero_calls(self) -> None:
        from workflow.runner import run_until_stage1_complete
        from workflow.receipts import load_receipt

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            first = load_receipt(str(folder), "stage0")
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            stack, groq, gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_until_stage1_complete(str(folder), adopt=False)
            groq.assert_not_called()
            gemini.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            second = load_receipt(str(folder), "stage0")
            self.assertEqual(second["result"]["pause_kind"], "cost_authorization")
            self.assertEqual(
                second["result"]["model_call_occurred"],
                first["result"]["model_call_occurred"],
            )

    def test_stage1_docs_cannot_enter_paste_before_stage0_completes(self) -> None:
        from workflow.runner import run_until_stage1_complete

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            (folder / "Resume.md").write_text("# Name\n", encoding="utf-8")
            (folder / "CoverLetter.md").write_text("Dear Hiring Manager,\n", encoding="utf-8")
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_until_stage1_complete(str(folder), adopt=False)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            self.assertEqual(out["active_stage"], "stage0")
            self.assertNotEqual(out.get("status"), "WAITING_FOR_LLM")
            self.assertFalse((folder / "authoring_prompt.md").exists())

    def test_bound_manual_import_resumes_same_run(self) -> None:
        from workflow.runner import run_stage0
        from workflow.receipts import load_receipt
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(_fill_template(template), indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            gemini.assert_not_called()
            self.assertEqual(out["stages"]["stage0"]["status"], "COMPLETE")
            self.assertNotEqual(out["status"], "WAITING_FOR_LLM")
            receipt = load_receipt(str(folder), "stage0")
            self.assertEqual(receipt["status"], "COMPLETE")
            self.assertFalse(receipt["result"]["model_call_occurred"])
            self.assertFalse(receipt["result"]["cost_applicable"])
            self.assertIn("stage0_cascade_import.consumed.json", receipt["input_hashes"])
            self.assertTrue((folder / "stage0_cascade_import.consumed.json").is_file())
            self.assertFalse((folder / "stage0_cascade_import.json").is_file())

    def test_stale_jd_import_fails(self) -> None:
        from workflow.runner import run_stage0
        from workflow.receipts import load_receipt
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own a different roadmap\n",
                encoding="utf-8",
            )
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(_fill_template(template), indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            receipt = load_receipt(str(folder), "stage0")
            self.assertEqual(receipt["result"]["reason"], "invalid_cascade_import")

    def test_wrong_submission_import_fails(self) -> None:
        from workflow.runner import run_stage0
        from workflow.receipts import load_receipt
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            filled = _fill_template(template)
            filled["submission_slug"] = "other-co"
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(filled, indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            self.assertEqual(
                load_receipt(str(folder), "stage0")["result"]["reason"],
                "invalid_cascade_import",
            )

    def test_invented_sequential_id_import_fails(self) -> None:
        from workflow.runner import run_stage0
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            filled = _fill_template(template)
            filled["results"][0]["item_id"] = "req-001"
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(filled, indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")

    def test_import_cannot_set_workflow_status(self) -> None:
        from workflow.runner import run_stage0
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            filled = _fill_template(template)
            filled["workflow_status"] = "COMPLETE"
            filled["verification_passed"] = True
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(filled, indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            self.assertNotEqual(out["status"], "COMPLETE")

    def test_import_missing_expected_item_ids_fails(self) -> None:
        from workflow.runner import run_stage0
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            filled = _fill_template(template)
            del filled["expected_item_ids"]
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(filled, indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")

    def test_import_missing_created_at_fails(self) -> None:
        from workflow.runner import run_stage0
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            filled = _fill_template(template)
            del filled["created_at"]
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(filled, indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")

    def test_invalid_utf8_import_pauses_without_corrupting_state(self) -> None:
        from workflow.runner import run_stage0
        from workflow.receipts import write_state
        from workflow.state import init_state, load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            (folder / "stage0_cascade_import.json").write_bytes(b"\xff\xfe not utf-8")
            db_path = self._db(folder)
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = init_state(str(folder))
            write_state(str(folder), state)
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            self.assertEqual(out["status"], "WAITING_FOR_INPUT")
            self.assertNotEqual(out["status"], "FAILED")
            reloaded = load_state(str(folder))
            self.assertEqual(reloaded["status"], "WAITING_FOR_INPUT")
            self.assertTrue((folder / "Original_JD.txt").is_file())

    def test_changing_consumed_import_invalidates_stage0_receipt(self) -> None:
        from workflow.runner import run_stage0, reconcile
        from workflow.state import load_state

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "example-co"
            folder.mkdir()
            (folder / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Own the platform roadmap\n",
                encoding="utf-8",
            )
            db_path = self._db(folder)
            self._pause_once(folder, db_path)
            template = json.loads(
                (folder / "stage0_cascade_import.template.json").read_text(encoding="utf-8")
            )
            (folder / "stage0_cascade_import.json").write_text(
                json.dumps(_fill_template(template), indent=2),
                encoding="utf-8",
            )
            settings = {
                "stage0_evidence_classification": {"provider_order": ["groq"]},
                "costClasses": {"groq": "unknown"},
            }
            state = load_state(str(folder))
            stack, groq, _gemini = self._stage0_ctx(settings, db_path)
            with stack:
                out = run_stage0(str(folder), state)
            groq.assert_not_called()
            consumed = folder / "stage0_cascade_import.consumed.json"
            consumed.write_text(consumed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            stale = reconcile(str(folder), load_state(str(folder)))
            self.assertEqual(stale["stages"]["stage0"]["status"], "STALE")


if __name__ == "__main__":
    unittest.main()
