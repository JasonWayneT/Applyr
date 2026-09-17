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
    list_open_confirmations,
    list_pending_for_opportunity,
    model_flagged_named_skill,
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
    _ROOT / "server" / "migrations" / "022_add_bad_data_answer.sql",
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

    def test_model_flagged_review_requires_grounded_named_tool(self) -> None:
        self.assertTrue(model_flagged_named_skill(
            "Acme Platform", "Experience with Acme Platform integrations"
        ))
        self.assertFalse(model_flagged_named_skill(
            "Critical Thinking", "Strong critical thinking and collaboration"
        ))
        self.assertFalse(model_flagged_named_skill(
            "Acme Platform", "Strong critical thinking and collaboration"
        ))
        self.assertFalse(model_flagged_named_skill(
            "Trello", "Experience with Trello"
        ))
        self.assertTrue(model_flagged_named_skill(
            "acme platform", "Experience with Acme Platform integrations"
        ))

    def test_generic_degree_and_field_words_are_not_treated_as_tools(self) -> None:
        """CR-108 cascade testing (2026-09-01): once named_skill_candidates() feeds a
        BLOCKING gate (Stage0NeedsInput), a false positive here isn't a cheap glance-
        and-dismiss WARN anymore -- it's an individually-blocking review question per
        company. Confirmed live on a real archived JD (early_warning): all 12 of these
        terms fired as false "named tool" hits before this fix."""
        candidates = named_skill_candidates(
            [
                "Bachelor's degree in Computer Science, Engineering, or related field.",
                "Background in STEM or Information Systems preferred.",
                "Experience in Data Architecture, Data Engineering, or Analytics Engineering.",
                "Familiarity with Software Engineering and Platform Engineering practices.",
                "Prior work in Data Product Management or Platform Product Management.",
                "Must be authorized to work without Visa sponsorship.",
                "Bachelor's degree in Business, Healthcare Administration, or Public Health.",
            ],
        )
        self.assertEqual(candidates, [])

    def test_jd_label_shapes_are_not_treated_as_tools(self) -> None:
        """CR-109 / BUG-001 (2026-09-02): live Review Center queues asked Jason
        "Have you used Spirit in your work?" and "Have you used Preferred in
        your work?" because JD label shapes ("Entrepreneurial Spirit: ...",
        "(Highly Preferred): ...") matched the mid-sentence capitalization
        heuristic. The regex can only start mid-run (a line-leading word has
        no [a-z,] whitespace before it), so "Spirit" matched even though
        "Entrepreneurial" could not. Candidates followed by ":" or ")" are
        labels/qualifiers, not products."""
        candidates = named_skill_candidates(
            [
                "Entrepreneurial Spirit: Demonstrate a track record of delivering results.",
                "Systems Thinking: The ability to map complex data flows.",
                "Ruthless Prioritization: The ability to use data to make tough decisions.",
                "Technical Fluency: Comfortable speaking with engineers.",
                "Integration Methodologies: Strong understanding of REST APIs.",
                "Key Competencies",
            ],
        )
        self.assertEqual(candidates, [])

    def test_abstract_noun_suffix_guard_filters_soft_skills(self) -> None:
        """CR-109 follow-up 2 (2026-09-02): Jason flagged "Have you used
        Judgment in your work?" as an absurd card. Soft skills, traits, and
        competencies are evaluated through evidence comparison, not binary
        tool questions. Words ending in abstract-noun suffixes (-tion, -ment,
        -ship, -ity, -ness, -ance, -ence, etc.) are English derivations, not
        tool/product names. The suffix guard is the structural complement to
        the stopword list so we don't whack-a-mole every English trait word."""
        candidates = named_skill_candidates(
            [
                "Uses Judgment and strategic thinking to prioritize roadmap investments.",
                "Strong Leadership and Mentorship capabilities.",
                "Demonstrate Resilience and Adaptability in fast-moving environments.",
                "Build Alignment across Engineering and cross-functional teams.",
                "Drive Engagement and Empowerment across the organization.",
                "Ensure Governance and Compliance across all data flows.",
                "Scalability and Agility in product architecture decisions.",
                "Influence and Persuasion skills for stakeholder management.",
                "Awareness of industry trends and best practices.",
                "Partnership and Collaboration with external vendors.",
            ],
        )
        self.assertEqual(candidates, [])

    def test_blocked_tool_inside_longer_candidate_is_excluded(self) -> None:
        """CR-109 / BUG-001: "workday" is hard-blocked, yet "Workday Ecosystem",
        "Workday Web Services", and "Workday Recruiting" all queued as blocking
        questions because the blocked check compared only the whole key."""
        candidates = named_skill_candidates(
            [
                "The Workday Ecosystem (Highly Preferred): Hands-on familiarity with "
                "Workday Web Services (WWS), Studio, EIB, Extend, and Workday "
                "Recruiting/HCM data models.",
            ],
        )
        names = [candidate.display_name for candidate in candidates]
        self.assertNotIn("Workday Ecosystem", names)
        self.assertNotIn("Workday Web Services", names)
        self.assertNotIn("Workday Recruiting", names)
        self.assertNotIn("Preferred", names)
        # Real Workday-adjacent tools without a blocked token stay askable.
        self.assertEqual(sorted(names), ["EIB", "Extend", "Studio"])

    def test_bad_data_answer_is_durable_and_never_asked_again(self) -> None:
        """CR-109 / FR-287: BAD_DATA records an extraction false positive as
        durable memory so the same candidate is never queued again, at
        evidence level 0, with no evidence-enrichment follow-up."""
        create_skill_confirmation(
            db_path=self.db_path,
            skill_key="spirit",
            display_name="Spirit",
            requirement="Entrepreneurial Spirit: Demonstrate a track record.",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
        )
        result = answer_confirmation(
            db_path=self.db_path,
            review_key="skill:spirit",
            answer="BAD_DATA",
        )
        self.assertEqual(result.status, "completed")
        memory = get_skill_memory("spirit", self.db_path)
        self.assertIsNotNone(memory)
        self.assertEqual(memory["decision"], "BAD_DATA")
        self.assertEqual(memory["evidence_level"], 0)
        # No evidence-enrichment follow-up is created for bad data.
        self.assertEqual(list_pending_for_opportunity("acme", self.db_path), [])
        history_conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                history_conn.execute(
                    "SELECT answer FROM review_answer_history WHERE review_key = ?",
                    ("skill:spirit",),
                ).fetchone()[0],
                "BAD_DATA",
            )
        finally:
            history_conn.close()

    def test_real_named_ai_tools_still_flagged_alongside_generic_words(self) -> None:
        """The generic-word stopword additions must not swallow a genuinely
        unverified named tool sitting in the same line -- confirmed live
        alongside the false positives above (bamboo_health): ChatGPT and
        Copilot correctly stayed flagged as real ask-the-human candidates."""
        candidates = named_skill_candidates(
            [
                "Active use of AI-supported tools such as ChatGPT, Claude, or Copilot.",
            ],
            known_terms={"claude"},
        )
        self.assertEqual(
            sorted(c.display_name for c in candidates),
            ["ChatGPT", "Copilot"],
        )

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
            ["CONFIRMED_USE", "NOT_PRESENT", "UNSURE_NO_REASK", "BAD_DATA"],
        )
        self.assertEqual(question["affected_opportunities"], ["acme"])

    def test_review_card_stores_basis_and_uncertainty(self) -> None:
        create_skill_confirmation(
            db_path=self.db_path,
            skill_key="Jira",
            display_name="Jira",
            requirement="Experience with Jira",
            opportunity_key="acme",
            opportunity_company="Acme",
            opportunity_title="Product Manager",
            evidence_excerpt="Named tool is in the JD.",
            decision_basis="Deterministic named-tool scan.",
            uncertainty="unknown_named_tool",
        )
        rows = list_open_confirmations(self.db_path)
        self.assertEqual(rows[0]["decision_basis"], "Deterministic named-tool scan.")
        self.assertEqual(rows[0]["uncertainty"], "unknown_named_tool")
        self.assertEqual(rows[0]["evidence_excerpt"], "Named tool is in the JD.")

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
                    import re
                    item_id = re.search(r"\[(\S+)\] bucket=", prompt).group(1)
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

    def test_model_flagged_unknown_tool_creates_pending_and_pauses(self) -> None:
        """CR-108 Epic 7.2: when the deterministic extractor misses a named
        tool (patched to find nothing) and the batch model flags it with
        needs_user_confirmation + canonical_skill, the fit gate creates the
        same durable pending item the deterministic path would have, pauses
        WAITING_FOR_INPUT, and resumes reusing the persisted checkpoint."""
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            (folder_path / "Original_JD.txt").write_text(
                "Product Manager\n\nRequirements\n- Experience with Acme Platform integrations\n",
                encoding="utf-8",
            )
            db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
            os.close(db_fd)
            try:
                sections = {
                    "required": ["Experience with Acme Platform integrations"],
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
                    import re
                    item_id = re.search(r"\[(\S+)\] bucket=", prompt).group(1)
                    return json.dumps(
                        {
                            "results": [
                                {
                                    "item_id": item_id,
                                    "gate": "NONE",
                                    "gap_source": "",
                                    "evidence_level": 2,
                                    "confidence": "high",
                                    "reasoning": (
                                        "Acme Platform appears in the JD but not in "
                                        "verified work history."
                                    ),
                                    "needs_user_confirmation": True,
                                    "canonical_skill": "Acme Platform",
                                    "skill_kind": "tool",
                                }
                            ]
                        }
                    )

                # The deterministic extractor misses the tool on purpose.
                with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "1"}):
                    with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                        with patch("build_stage0_fit_gate.named_skill_candidates", return_value=[]):
                            with patch("utils.load_llm_settings", return_value=settings):
                                with patch("utils.call_llm", side_effect=provider_response):
                                    with self.assertRaises(Stage0NeedsInput) as raised:
                                        build_stage0_fit_gate(
                                            folder_path,
                                            db_gate_result={"action": "clear"},
                                            prefs={"blocked_companies": []},
                                            confirmation_db_path=db_path,
                                        )
                pending = list_pending_for_opportunity(folder_path.name, db_path)
                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["question_type"], "skill_presence")
                self.assertEqual(pending[0]["skill_key"], "acme_platform")
                self.assertEqual(pending[0]["status"], "open")
                self.assertEqual(
                    raised.exception.pending[0]["review_key"],
                    "skill:acme_platform",
                )
                self.assertEqual(len(calls), 1)

                answer_confirmation(
                    db_path=db_path,
                    review_key=raised.exception.pending[0]["review_key"],
                    answer="CONFIRMED_USE",
                )
                with patch.dict(os.environ, {"STAGE0_EVIDENCE_CASCADE": "1"}):
                    with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                        with patch("build_stage0_fit_gate.named_skill_candidates", return_value=[]):
                            with patch("utils.load_llm_settings", return_value=settings):
                                with patch(
                                    "utils.call_llm",
                                    side_effect=AssertionError("resume should reuse the cached judgment"),
                                ):
                                    result = build_stage0_fit_gate(
                                        folder_path,
                                        db_gate_result={"action": "clear"},
                                        prefs={"blocked_companies": []},
                                        confirmation_db_path=db_path,
                                    )
                self.assertFalse(
                    result.get("decision") == "SKIP" and result.get("skip_reason_code") == "hard_gap"
                )
                self.assertEqual(len(calls), 1)
            finally:
                os.unlink(db_path)

    def test_model_flagged_soft_skill_does_not_create_review_card(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            folder_path = Path(folder)
            requirement = "Strong critical thinking and collaboration"
            (folder_path / "Original_JD.txt").write_text(
                f"Product Manager\n\nRequirements\n- {requirement}\n",
                encoding="utf-8",
            )
            db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
            os.close(db_fd)
            try:
                sections = {
                    "required": [requirement],
                    "preferred": [],
                    "responsibilities": [],
                    "culture": [],
                }

                def provider_response(_system: str, prompt: str, **_kwargs: object) -> str:
                    import re
                    item_id = re.search(r"\[(\S+)\] bucket=", prompt).group(1)
                    return json.dumps({"results": [{
                        "item_id": item_id,
                        "gate": "NONE",
                        "gap_source": "",
                        "evidence_level": 2,
                        "confidence": "high",
                        "reasoning": "General PM competency.",
                        "needs_user_confirmation": True,
                        "canonical_skill": "Critical Thinking",
                        "skill_kind": "skill",
                    }]})

                with patch("build_stage0_fit_gate._extract_sections_nlp", return_value=sections):
                    with patch("utils.load_llm_settings", return_value={
                        "stage0_evidence_classification": {
                            "provider_order": ["groq"],
                            "models": {"groq": "groq-test"},
                        }
                    }):
                        with patch("utils.call_llm", side_effect=provider_response):
                            build_stage0_fit_gate(
                                folder_path,
                                db_gate_result={"action": "clear"},
                                prefs={"blocked_companies": []},
                                confirmation_db_path=db_path,
                            )
                self.assertEqual(list_pending_for_opportunity(folder_path.name, db_path), [])
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
                    import re
                    item_id = re.search(r"\[(\S+)\] bucket=", prompt).group(1)
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
                            with patch(
                                "stage0_db_gate.evaluate_db_gate",
                                return_value={"action": "clear"},
                            ):
                                with patch("stage0_skip_ledger.lookup_skip", return_value=None):
                                    with patch("utils.call_llm", side_effect=provider_response):
                                        paused = run_stage0(folder, init_state(folder))
                self.assertEqual(paused["status"], "WAITING_FOR_INPUT")
                receipt = load_receipt(folder, "stage0")
                self.assertIsNotNone(receipt)
                self.assertEqual(receipt["result"]["pause_kind"], "review_center")
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
                            with patch(
                                "stage0_db_gate.evaluate_db_gate",
                                return_value={"action": "clear"},
                            ):
                                with patch("stage0_skip_ledger.lookup_skip", return_value=None):
                                    with patch(
                                        "utils.call_llm",
                                        side_effect=AssertionError("resume did not reuse checkpoint"),
                                    ):
                                        resumed = run_stage0(folder, paused)
                self.assertEqual(resumed["status"], "IN_PROGRESS")
                self.assertEqual(resumed["stages"]["stage0"]["status"], "COMPLETE")
            finally:
                os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
