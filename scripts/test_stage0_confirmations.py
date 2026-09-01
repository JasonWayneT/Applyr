#!/usr/bin/env python3
"""Tests for the shared Stage 0 confirmation boundary (CR-108)."""
from __future__ import annotations

import os
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stage0_confirmations import (
    answer_confirmation,
    answer_hard_gate_review,
    canonical_skill_key,
    create_hard_gate_review,
    create_skill_confirmation,
    get_skill_memory,
    list_pending_for_opportunity,
    named_skill_candidates,
    verify_evidence_promotion,
)
from build_stage0_fit_gate import (
    Stage0NeedsInput,
    build_stage0_fit_gate,
)
from stage0_harness import next_question
from workflow.runner import run_stage0
from workflow.receipts import load_receipt
from workflow.state import init_state, load_state


_ROOT = Path(__file__).resolve().parents[1]
_MIGRATIONS = (
    _ROOT / "server" / "migrations" / "018_add_review_center.sql",
    _ROOT / "server" / "migrations" / "019_add_stage0_checkpoints.sql",
    _ROOT / "server" / "migrations" / "020_add_review_answer_history.sql",
    _ROOT / "server" / "migrations" / "021_add_evidence_promotion_proposals.sql",
)


class TestStage0Confirmations(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.conn = sqlite3.connect(self.db_path)
        for migration in _MIGRATIONS:
            self.conn.executescript(migration.read_text(encoding="utf-8"))
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        os.unlink(self.db_path)

    def test_canonical_skill_key_handles_product_punctuation(self) -> None:
        self.assertEqual(canonical_skill_key("Monday.com"), "monday_com")
        self.assertEqual(canonical_skill_key("ServiceNow (ITSM)"), "servicenow_itsm")
        self.assertEqual(canonical_skill_key("  Google Workspace  "), "google_workspace")

    def test_unknown_named_skill_is_conservative_and_catalog_terms_are_excluded(self) -> None:
        candidates = named_skill_candidates(
            [
                "Experience with Trello and Acme Platform integrations.",
                "Strong stakeholder communication and roadmap ownership.",
            ],
            known_terms={"trello"},
        )
        self.assertEqual([candidate.display_name for candidate in candidates], ["Acme Platform"])

    def test_confirmation_creation_is_idempotent_per_opportunity(self) -> None:
        first = create_skill_confirmation(
            db_path=self.db_path,
            skill_key="Trello",
            display_name="Trello",
            requirement="Experience with Trello",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        second = create_skill_confirmation(
            db_path=self.db_path,
            skill_key="trello",
            display_name="Trello",
            requirement="Experience with Trello",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(len(list_pending_for_opportunity("acme", self.db_path)), 1)

    def test_confirmation_answer_is_durable_and_does_not_create_verified_evidence(self) -> None:
        create_skill_confirmation(
            db_path=self.db_path,
            skill_key="trello",
            display_name="Trello",
            requirement="Experience with Trello",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        result = answer_confirmation(
            db_path=self.db_path,
            review_key="skill:trello",
            answer="CONFIRMED_USE",
        )
        self.assertEqual(result.status, "completed")
        memory = get_skill_memory("trello", self.db_path)
        self.assertIsNotNone(memory)
        self.assertEqual(memory["decision"], "CONFIRMED_USE")
        self.assertEqual(memory["evidence_level"], 1)
        self.assertNotEqual(memory["decision"], "VERIFIED_EVIDENCE")
        history_conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                history_conn.execute(
                    "SELECT count(*) FROM review_answer_history WHERE review_key = ?",
                    ("skill:trello",),
                ).fetchone()[0],
                1,
            )
        finally:
            history_conn.close()

    def test_promotion_requires_source_verification(self) -> None:
        """Require reviewed details to exist in workExperience before promotion."""
        create_skill_confirmation(
            db_path=self.db_path,
            skill_key="trello",
            display_name="Trello",
            requirement="Experience with Trello",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        answer_confirmation(
            db_path=self.db_path,
            review_key="skill:trello",
            answer="CONFIRMED_USE",
        )
        result = answer_confirmation(
            db_path=self.db_path,
            review_key="skill:trello:evidence",
            answer="CONFIRMED_USE",
            details={
                "context": "Acme",
                "activity": "configured workflows",
                "timeframe": "2024",
            },
            promote_to_verified_evidence=True,
        )
        self.assertIsNotNone(result.promotion_id)
        self.assertFalse(
            verify_evidence_promotion(
                result.promotion_id or "",
                source_path=Path(self.db_path).with_suffix(".md"),
                db_path=self.db_path,
            )
        )
        source_path = Path(self.db_path).with_suffix(".md")
        source_path.write_text(
            "At Acme, configured workflows during 2024 using Trello.",
            encoding="utf-8",
        )
        try:
            self.assertTrue(
                verify_evidence_promotion(
                    result.promotion_id or "",
                    source_path=source_path,
                    db_path=self.db_path,
                )
            )
            self.assertEqual(
                get_skill_memory("trello", self.db_path)["decision"],
                "VERIFIED_EVIDENCE",
            )
            repeated = answer_confirmation(
                db_path=self.db_path,
                review_key="skill:trello",
                answer="CONFIRMED_USE",
                details={
                    "context": "Acme",
                    "activity": "configured workflows",
                    "timeframe": "2024",
                },
                promote_to_verified_evidence=True,
            )
            self.assertEqual(repeated.promotion_id, result.promotion_id)
            self.assertEqual(get_skill_memory("trello", self.db_path)["evidence_level"], 2)
        finally:
            source_path.unlink()

    def test_yes_creates_optional_enrichment_and_not_present_closes_it(self) -> None:
        create_skill_confirmation(
            db_path=self.db_path,
            skill_key="trello",
            display_name="Trello",
            requirement="Experience with Trello",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        answer_confirmation(
            db_path=self.db_path,
            review_key="skill:trello",
            answer="CONFIRMED_USE",
        )
        pending = list_pending_for_opportunity("acme", self.db_path)
        self.assertEqual({row["question_type"] for row in pending}, {"evidence_enrichment"})
        answer_confirmation(
            db_path=self.db_path,
            review_key="skill:trello:evidence",
            answer="NOT_PRESENT",
        )
        self.assertEqual(list_pending_for_opportunity("acme", self.db_path), [])

    def test_stage0_builder_pauses_for_unknown_named_skill_before_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Experience with Acme Platform\n",
                encoding="utf-8",
            )
            sections = {
                "required": ["Experience with Acme Platform"],
                "preferred": [],
                "responsibilities": [],
                "culture": [],
            }
            with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                with self.assertRaises(Stage0NeedsInput) as raised:
                    build_stage0_fit_gate(
                        folder,
                        db_gate_result={"action": "clear"},
                        prefs={"blocked_companies": []},
                        confirmation_db_path=self.db_path,
                    )
            self.assertEqual(raised.exception.opportunity_key, Path(folder).name)
            self.assertEqual(raised.exception.pending[0]["skill_key"], "acme_platform")
            self.assertEqual(list_pending_for_opportunity(Path(folder).name, self.db_path)[0]["title"], "Acme Platform")

    def test_harness_emits_the_same_actionable_question_record(self) -> None:
        create_skill_confirmation(
            db_path=self.db_path,
            skill_key="Acme Platform",
            display_name="Acme Platform",
            requirement="Experience with Acme Platform",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        question = next_question(self.db_path)
        self.assertEqual(question["type"], "stage0_skill_confirmation")
        self.assertEqual(question["question_type"], "skill_presence")
        self.assertEqual(question["review_key"], "skill:acme_platform")
        self.assertEqual(
            question["options"],
            ["CONFIRMED_USE", "NOT_PRESENT", "UNSURE_NO_REASK"],
        )
        self.assertEqual(question["affected_opportunities"], ["acme"])

    def test_hard_gate_requires_explicit_action_and_more_info_stays_open(self) -> None:
        review = create_hard_gate_review(
            db_path=self.db_path,
            item_key="required:0:license",
            requirement="Requires an active professional license",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        self.assertEqual(
            answer_hard_gate_review(
                db_path=self.db_path,
                review_key=review.review_key,
                answer="NEEDS_MORE_INFO",
            ).status,
            "open",
        )
        self.assertEqual(
            answer_hard_gate_review(
                db_path=self.db_path,
                review_key=review.review_key,
                answer="CONFIRM_HARD",
            ).status,
            "completed",
        )


class TestWorkflowWaitingForInput(unittest.TestCase):
    def test_stage0_waiting_is_persisted_as_a_distinct_workflow_state(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Original_JD.txt").write_text("Product Manager\n", encoding="utf-8")
            pending = [{"review_key": "skill:acme_platform", "skill_key": "acme_platform"}]
            with patch(
                "workflow.runner.build_stage0_fit_gate",
                side_effect=Stage0NeedsInput("acme", pending),
            ):
                state = run_stage0(folder, init_state(folder))
            self.assertEqual(state["status"], "WAITING_FOR_INPUT")
            self.assertEqual(state["active_stage"], "stage0")
            self.assertEqual(state["stages"]["stage0"]["status"], "WAITING_FOR_INPUT")
            self.assertEqual(load_state(folder)["status"], "WAITING_FOR_INPUT")


class TestEnabledCascadeBuilder(unittest.TestCase):
    def test_cascade_spools_reviews_and_reuses_completed_judgment(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            (folder_path / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Requires an active nursing license\n",
                encoding="utf-8",
            )
            db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
            os.close(db_fd)
            try:
                sections = {
                    "required": ["Requires an active nursing license"],
                    "preferred": [],
                    "responsibilities": [],
                    "culture": [],
                }
                settings = {
                    "stage0_evidence_classification": {
                        "provider_order": ["groq", "gemini"],
                        "models": {"groq": "groq-test", "gemini": "gemini-test"},
                    }
                }
                calls: list[str] = []

                def provider_response(_system: str, prompt: str, **_kwargs: object) -> str:
                    calls.append(prompt)
                    item_id = prompt.split("[", 1)[1].split("]", 1)[0]
                    return json.dumps(
                        {
                            "results": [
                                {
                                    "item_id": item_id,
                                    "gate": "HARD",
                                    "gap_source": "certification",
                                    "evidence_level": 4,
                                    "confidence": "high",
                                    "reasoning": "active nursing license requirement",
                                }
                            ]
                        }
                    )

                with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "1"}):
                    with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                        with patch("utils.load_llm_settings", return_value=settings):
                            with patch("utils.call_llm", side_effect=provider_response):
                                with self.assertRaises(Stage0NeedsInput) as raised:
                                    build_stage0_fit_gate(
                                        folder_path,
                                        db_gate_result={"action": "clear"},
                                        prefs={"blocked_companies": []},
                                        confirmation_db_path=db_path,
                                    )
                self.assertEqual(raised.exception.pending[0]["question_type"], "hard_gate_review")
                spool_files = list((folder_path / ".stage0_spool").glob("*.json"))
                self.assertEqual({path.name.split(".")[-3] for path in spool_files}, {"request", "response"})
                self.assertEqual(len(calls), 1)
                checkpoint = sqlite3.connect(db_path)
                checkpoint.row_factory = sqlite3.Row
                run = checkpoint.execute(
                    "SELECT request_spool_path, request_hash, response_spool_path, response_hash, metadata_json "
                    "FROM stage0_runs"
                ).fetchone()
                checkpoint.close()
                self.assertIsNotNone(run)
                for path_column, hash_column in (
                    ("request_spool_path", "request_hash"),
                    ("response_spool_path", "response_hash"),
                ):
                    spool_path = Path(run[path_column])
                    serialized = spool_path.read_bytes()
                    self.assertEqual(hashlib.sha256(serialized).hexdigest(), run[hash_column])
                telemetry = json.loads(run["metadata_json"])
                self.assertEqual(telemetry["stage0_cascade_provider_calls"], 1)
                self.assertEqual(telemetry["stage0_cascade_fallbacks"], 0)

                answer_hard_gate_review(
                    db_path=db_path,
                    review_key=raised.exception.pending[0]["review_key"],
                    answer="KEEP_ELIGIBLE",
                )
                with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "1"}):
                    with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                        with patch("utils.load_llm_settings", return_value=settings):
                            with patch("utils.call_llm", side_effect=AssertionError("cached judgment was not reused")):
                                result = build_stage0_fit_gate(
                                    folder_path,
                                    db_gate_result={"action": "clear"},
                                    prefs={"blocked_companies": []},
                                    confirmation_db_path=db_path,
                                )
                self.assertFalse(result["decision"] == "SKIP" and result.get("skip_reason_code") == "hard_gap")
                self.assertEqual(len(calls), 1)
            finally:
                os.unlink(db_path)

    def test_workflow_pauses_then_resumes_after_hard_gate_answer(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            (folder_path / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Requires an active nursing license\n",
                encoding="utf-8",
            )
            db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
            os.close(db_fd)
            try:
                sections = {
                    "required": ["Requires an active nursing license"],
                    "preferred": [],
                    "responsibilities": [],
                    "culture": [],
                }
                settings = {
                    "stage0_evidence_classification": {
                        "provider_order": ["groq"],
                        "models": {"groq": "groq-test"},
                    }
                }
                response = json.dumps(
                    {
                        "results": [
                            {
                                "item_id": "required:0:9b1f",
                                "gate": "HARD",
                                "gap_source": "certification",
                                "evidence_level": 4,
                                "confidence": "high",
                                "reasoning": "active nursing license requirement",
                            }
                        ]
                    }
                )

                def provider_response(_system: str, prompt: str, **_kwargs: object) -> str:
                    item_id = prompt.split("[", 1)[1].split("]", 1)[0]
                    return response.replace("required:0:9b1f", item_id)

                with patch.dict(
                    os.environ,
                    {
                        "STAGE0_EVIDENCE_CASCADE": "1",
                        "STAGE0_SECTION_MODE": "deterministic",
                        "APPLYR_STAGE0_REVIEW_DB": db_path,
                    },
                ):
                    with patch("build_stage0_fit_gate._extract_sections", return_value=sections):
                        with patch("utils.load_llm_settings", return_value=settings):
                            with patch("utils.call_llm", side_effect=provider_response):
                                paused = run_stage0(folder, init_state(folder))
                self.assertEqual(paused["status"], "WAITING_FOR_INPUT")
                receipt = load_receipt(folder, "stage0")
                self.assertIsNotNone(receipt)
                review_key = receipt["result"]["pending_confirmations"][0]["review_key"]
                answer_hard_gate_review(
                    db_path=db_path,
                    review_key=review_key,
                    answer="KEEP_ELIGIBLE",
                )
                with patch.dict(
                    os.environ,
                    {
                        "STAGE0_EVIDENCE_CASCADE": "1",
                        "STAGE0_SECTION_MODE": "deterministic",
                        "APPLYR_STAGE0_REVIEW_DB": db_path,
                    },
                ):
                    with patch("build_stage0_fit_gate._extract_sections", return_value=sections):
                        with patch("utils.load_llm_settings", return_value=settings):
                            with patch("utils.call_llm", side_effect=AssertionError("resume did not reuse checkpoint")):
                                resumed = run_stage0(folder, paused)
                self.assertEqual(resumed["status"], "IN_PROGRESS")
                self.assertEqual(resumed["stages"]["stage0"]["status"], "COMPLETE")
            finally:
                os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
