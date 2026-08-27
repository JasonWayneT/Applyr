#!/usr/bin/env python3
"""Stage 0 extract/score model pin, VRAM handoff, and anchor cleanup — no live LLM."""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["STAGE0_SECTION_MODE"] = "deterministic"

from build_stage0_fit_gate import (  # noqa: E402
    STAGE0_EXTRACT_MODEL,
    build_stage0_fit_gate,
)
from evidence_scale import STAGE0_SCORE_MODEL, classify_requirement  # noqa: E402
from model_manager import _tag_matches, unload_resident_models  # noqa: E402
from test_build_stage0_fit_gate import (  # noqa: E402
    _CLEAN_PM_JD,
    _DB_CLEAR,
    _PREFS_MINIMAL,
    _make_submission_folder,
)


class TestScoreModelPin(unittest.TestCase):
    def setUp(self):
        import evidence_scale
        evidence_scale._score_model_ready_for = None

    def test_classify_requirement_pins_score_model(self):
        payload = json.dumps({
            "gate": "NONE",
            "gap_source": "",
            "evidence_level": 3,
            "confidence": "high",
            "reasoning": "documented product management work",
        })
        with patch("model_manager.ensure_local_model_available") as avail:
            with patch("llm_stages.call_llm_stage", return_value=payload) as mock_call:
                with patch("fit_rubric_examples.retrieve_examples", return_value=[]):
                    with patch(
                        "evidence_scale.build_evidence_context",
                        return_value="Cision product work",
                    ):
                        classify_requirement(
                            "5+ years of product management experience",
                            "Cision product work",
                        )
        avail.assert_called_once_with(STAGE0_SCORE_MODEL)
        self.assertEqual(mock_call.call_args.kwargs.get("model"), STAGE0_SCORE_MODEL)

    def test_fit_model_env_still_overrides_for_bakeoffs(self):
        payload = json.dumps({
            "gate": "NONE",
            "gap_source": "",
            "evidence_level": 2,
            "confidence": "medium",
            "reasoning": "override",
        })
        with patch.dict(os.environ, {"FIT_MODEL": "qwen2.5:7b-instruct-q4_K_M"}):
            with patch("model_manager.ensure_local_model_available") as avail:
                with patch("llm_stages.call_llm_stage", return_value=payload) as mock_call:
                    with patch("fit_rubric_examples.retrieve_examples", return_value=[]):
                        with patch(
                            "evidence_scale.build_evidence_context",
                            return_value="Cision product work",
                        ):
                            classify_requirement(
                                "5+ years of product management experience",
                                "Cision product work",
                            )
        avail.assert_called_once_with("qwen2.5:7b-instruct-q4_K_M")
        self.assertEqual(
            mock_call.call_args.kwargs.get("model"),
            "qwen2.5:7b-instruct-q4_K_M",
        )


class TestDegreeHardGateNormalization(unittest.TestCase):
    def setUp(self):
        import evidence_scale
        evidence_scale._score_model_ready_for = None

    def _classify(self, item: str, *, is_required: bool = True):
        payload = json.dumps({
            "gate": "HARD",
            "gap_source": "degree",
            "evidence_level": 0,
            "confidence": "high",
            "reasoning": "The posting names a master's degree education requirement.",
        })
        with patch("model_manager.ensure_local_model_available"):
            with patch("llm_stages.call_llm_stage", return_value=payload):
                with patch("fit_rubric_examples.retrieve_examples", return_value=[]):
                    with patch(
                        "evidence_scale.build_evidence_context",
                        return_value="Bachelor of Business Administration",
                    ):
                        return classify_requirement(
                            item,
                            "Bachelor of Business Administration",
                            is_required=is_required,
                        )

    def test_bachelor_requirement_cannot_hard_gate(self):
        judgment = self._classify(
            "A bachelor's degree in Business Analytics, Information Technology, "
            "Project Management, or a related field."
        )
        self.assertEqual(judgment.gate, "NONE")
        self.assertEqual(judgment.evidence_level, 3)
        self.assertEqual(judgment.confidence, "high")

    def test_preferred_bachelor_requirement_cannot_hard_gate(self):
        judgment = self._classify(
            "Education: A High School Diploma or GED is required. A Bachelor's "
            "degree is preferred."
        )
        self.assertEqual(judgment.gate, "NONE")
        self.assertEqual(judgment.evidence_level, 3)

    def test_unhedged_masters_requirement_remains_hard_gate(self):
        judgment = self._classify("Master's degree in computer science required.")
        self.assertEqual(judgment.gate, "HARD")
        self.assertEqual(judgment.gap_source, "degree")


class TestUnloadResident(unittest.TestCase):
    def test_tag_matches_exact_and_latest(self):
        self.assertTrue(_tag_matches("gemma2:2b-instruct-q8_0", "gemma2:2b-instruct-q8_0"))
        self.assertTrue(_tag_matches("gemma2:2b-instruct-q8_0", "gemma2:2b-instruct-q8_0:latest"))
        self.assertFalse(_tag_matches("gemma2:2b-instruct-q8_0", "qwen2.5:7b-instruct-q4_K_M"))

    def test_unload_hits_ps_resident_and_explicit_names(self):
        ps = MagicMock()
        ps.status_code = 200
        ps.json.return_value = {
            "models": [{"name": STAGE0_EXTRACT_MODEL}],
        }
        chat = MagicMock()
        chat.status_code = 200

        def _post(url, json=None, timeout=5):
            return chat

        with patch("model_manager.requests.get", return_value=ps):
            with patch("model_manager.requests.post", side_effect=_post) as post:
                unloaded = unload_resident_models(also=(STAGE0_SCORE_MODEL,))
        names = [c.kwargs["json"]["model"] for c in post.call_args_list]
        self.assertIn(STAGE0_EXTRACT_MODEL, names)
        self.assertIn(STAGE0_SCORE_MODEL, names)
        self.assertIn(STAGE0_EXTRACT_MODEL, unloaded)
        self.assertIn(STAGE0_SCORE_MODEL, unloaded)


class TestExtractToScoreHandoff(unittest.TestCase):
    def test_same_model_skips_before_score_unload(self):
        """When extract and score use the same model (default since
        2026-08-22), the before-score VRAM unload is skipped — no point
        unloading and reloading the same tag."""
        sections = {
            "required": ["Define and own the product roadmap for our core platform"],
            "preferred": [],
            "responsibilities": ["Partner with engineering to deliver features end-to-end"],
            "culture": [],
            "internal_terms": [],
        }
        order: list[str] = []

        def extract(_jd):
            order.append("extract")
            return sections

        def release(reason, required=False):
            order.append(f"unload:{reason}")

        def classify(*_a, **_k):
            order.append("score")
            return [], [], []

        folder = _make_submission_folder(_CLEAN_PM_JD)
        with patch.dict(os.environ, {"STAGE0_SECTION_MODE": "llm"}):
            with patch("build_stage0_fit_gate._extract_sections_llm", side_effect=extract):
                with patch("build_stage0_fit_gate._release_stage0_vram", side_effect=release):
                    with patch("build_stage0_fit_gate._prepare_stage0_score_model"):
                        with patch("build_stage0_fit_gate.classify_gaps", side_effect=classify):
                            build_stage0_fit_gate(
                                folder,
                                db_gate_result=_DB_CLEAR,
                                prefs=_PREFS_MINIMAL,
                            )
        # Same model: no unload:before-score
        self.assertEqual(
            order[:3],
            ["unload:before-extract", "extract", "score"],
        )
        self.assertNotIn("unload:before-score", order)
        self.assertIn("unload:after-stage0", order)

    def test_different_model_still_unloads_before_score(self):
        """When FIT_MODEL overrides the score model to a different tag,
        the before-score VRAM unload fires as before."""
        sections = {
            "required": ["Define and own the product roadmap for our core platform"],
            "preferred": [],
            "responsibilities": ["Partner with engineering to deliver features end-to-end"],
            "culture": [],
            "internal_terms": [],
        }
        order: list[str] = []

        def extract(_jd):
            order.append("extract")
            return sections

        def release(reason, required=False):
            order.append(f"unload:{reason}")

        def classify(*_a, **_k):
            order.append("score")
            return [], [], []

        folder = _make_submission_folder(_CLEAN_PM_JD)
        with patch.dict(os.environ, {
            "STAGE0_SECTION_MODE": "llm",
            "FIT_MODEL": "gemma2:2b-instruct-q8_0",
        }):
            with patch("build_stage0_fit_gate._extract_sections_llm", side_effect=extract):
                with patch("build_stage0_fit_gate._release_stage0_vram", side_effect=release):
                    with patch("build_stage0_fit_gate._prepare_stage0_score_model"):
                        with patch("build_stage0_fit_gate.classify_gaps", side_effect=classify):
                            build_stage0_fit_gate(
                                folder,
                                db_gate_result=_DB_CLEAR,
                                prefs=_PREFS_MINIMAL,
                            )
        # Different model: unload:before-score is present
        self.assertEqual(
            order[:4],
            ["unload:before-extract", "extract", "unload:before-score", "score"],
        )
        self.assertIn("unload:after-stage0", order)


class TestCleanAnchor(unittest.TestCase):
    """Tests for _clean_anchor post-processing (2026-08-22 anchor quality fix)."""

    def setUp(self):
        from evidence_scale import _clean_anchor
        self._clean = _clean_anchor

    def test_strips_candidate_filler(self):
        raw = "The candidate has experience with Jira and Productboard at Cision. This aligns with the requirement."
        result = self._clean(raw)
        self.assertNotIn("The candidate has", result)
        self.assertIn("Jira", result)

    def test_strips_aligns_filler(self):
        raw = "This aligns with the candidate's product roadmap experience. ACC-109 quarterly roadmap at Cision."
        result = self._clean(raw)
        self.assertNotIn("This aligns", result)
        self.assertIn("ACC-109", result)

    def test_strips_requirement_filler(self):
        raw = "The requirement states 5+ years PM experience. Candidate has 7 years at Cision with $40M ARR platform."
        result = self._clean(raw)
        self.assertNotIn("The requirement states", result)
        self.assertIn("$40M ARR", result)

    def test_truncates_at_sentence_boundary(self):
        raw = (
            "Jira, Productboard, Pendo at Cision. ACC-109 quarterly roadmap. "
            "ACC-102 lifecycle delivery. $40M ARR platform ownership. "
            "Cross-functional alignment with Engineering and DBA teams. "
            "Stakeholder management across Sales and Customer Support."
        )
        result = self._clean(raw)
        self.assertLessEqual(len(result), 200)
        # Should end at a sentence boundary, not mid-word
        self.assertTrue(result.endswith("."), f"Expected sentence boundary, got: ...{result[-20:]}")

    def test_preserves_concise_evidence(self):
        raw = "Jira, Productboard, Pendo at Cision; ACC-109 quarterly roadmap; $40M ARR platform"
        result = self._clean(raw)
        self.assertEqual(raw, result)

    def test_empty_returns_none(self):
        self.assertEqual(self._clean(""), "none")
        self.assertEqual(self._clean(None), "none")

    def test_strips_whitespace_only(self):
        self.assertEqual(self._clean("   "), "none")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
