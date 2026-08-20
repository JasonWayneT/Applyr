#!/usr/bin/env python3
"""Stage 0 extract/score model pin and VRAM handoff — no live LLM."""
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

    def test_classify_requirement_pins_gemma(self):
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
    def test_unloads_between_qwen_extract_and_gemma_score(self):
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
        self.assertEqual(
            order[:4],
            ["unload:before-extract", "extract", "unload:before-score", "score"],
        )
        self.assertIn("unload:after-stage0", order)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
