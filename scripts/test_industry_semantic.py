#!/usr/bin/env python3
"""
Tests for CR-110 Gap A: LLM-based industry classification and Gap B: JD content validation.

Run:
  .venv\\Scripts\\python.exe -m unittest scripts.test_industry_semantic -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestIndustrySemantic(unittest.TestCase):
    """Tests for the LLM-based industry classification module."""

    def _mock_llm_response(self, blocked_industry: str, confidence: str, reasoning: str) -> str:
        """Build a mock LLM JSON response string."""
        return json.dumps({
            "blocked_industry": blocked_industry,
            "confidence": confidence,
            "reasoning": reasoning,
        })

    def test_classify_industry_blocks_gambling(self):
        """LLM identifies a gambling company that the keyword gate misses."""
        from industry_semantic import classify_industry

        jd = """
        Senior Product Manager
        We are a leading online entertainment platform serving millions of users.
        Our products include casino-style games, sports betting odds, and lottery
        applications for regulated markets. You will own the roadmap for our
        player experience suite.
        """
        mock_response = self._mock_llm_response(
            "Gambling", "high",
            "Company makes casino games and sports betting software",
        )
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = classify_industry(jd, ["Gambling", "Ad Tech", "Crypto"])

        self.assertEqual(result["blocked_industry"], "Gambling")
        self.assertEqual(result["confidence"], "high")

    def test_classify_industry_no_match_returns_empty(self):
        """LLM correctly identifies a non-blocked industry."""
        from industry_semantic import classify_industry

        jd = """
        Senior Product Manager
        We are a B2B SaaS platform for customer experience management. Our product
        helps enterprises track customer feedback across channels.
        """
        mock_response = self._mock_llm_response("", "high", "Not in any blocked industry")
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = classify_industry(jd, ["Gambling", "Ad Tech", "Crypto"])

        self.assertEqual(result["blocked_industry"], "")

    def test_classify_industry_normalizes_to_configured_spelling(self):
        """LLM returns 'gambling' but it normalizes to the configured 'Gambling'."""
        from industry_semantic import classify_industry

        jd = "Casino game platform PM role. We build online casino games and sports betting software for regulated markets."
        mock_response = self._mock_llm_response(
            "gambling", "high", "casino games = gambling",
        )
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = classify_industry(jd, ["Gambling"])

        self.assertEqual(result["blocked_industry"], "Gambling")

    def test_classify_industry_rejects_unlisted_industry(self):
        """LLM returns an industry not in the blocked list — treated as no match."""
        from industry_semantic import classify_industry

        jd = "Healthcare PM role"
        mock_response = self._mock_llm_response(
            "Healthcare", "high", "healthcare company",
        )
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = classify_industry(jd, ["Gambling", "Ad Tech"])

        self.assertEqual(result["blocked_industry"], "")

    def test_classify_industry_safe_fails_open_on_error(self):
        """classify_industry_safe returns no-block on LLM failure."""
        from industry_semantic import classify_industry_safe, IndustryClassificationError

        with mock.patch(
            "llm_stages.call_llm_stage",
            side_effect=RuntimeError("API down"),
        ):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = classify_industry_safe("some JD text that is long enough to pass the minimum length check here", ["Gambling"])

        self.assertEqual(result["blocked_industry"], "")
        self.assertTrue(result.get("_gate_failed"))

    def test_classify_industry_empty_blocked_list_short_circuits(self):
        """No blocked industries = no LLM call needed."""
        from industry_semantic import classify_industry

        result = classify_industry("some JD text here", [])
        self.assertEqual(result["blocked_industry"], "")
        self.assertEqual(result["confidence"], "high")

    def test_classify_industry_short_jd_short_circuits(self):
        """Very short JD text = no LLM call needed."""
        from industry_semantic import classify_industry

        result = classify_industry("short", ["Gambling"])
        self.assertEqual(result["blocked_industry"], "")


class TestJDContentValidation(unittest.TestCase):
    """Tests for JD content validation (bracket placeholders + network pages)."""

    def test_bracket_company_placeholder_detected(self):
        """[Company X] template placeholder is caught."""
        from jd_content_validation import check_jd_placeholders

        jd = "Product Manager at [Company X]\n\nWe are a SaaS platform."
        rejects = check_jd_placeholders(jd)
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["code"], "jd_placeholder")
        self.assertIn("Company", rejects[0]["reason"])

    def test_bracket_contact_placeholder_detected(self):
        """[phone] and [email] placeholders are caught."""
        from jd_content_validation import check_jd_placeholders

        jd = "Contact: [phone] [email]\n\nProduct Manager role at Acme."
        rejects = check_jd_placeholders(jd)
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["code"], "jd_placeholder")

    def test_bracket_your_company_placeholder_detected(self):
        """[Your Company] template placeholder is caught."""
        from jd_content_validation import check_jd_placeholders

        jd = "Join [Your Company] as a PM.\n\nWe build SaaS tools."
        rejects = check_jd_placeholders(jd)
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["code"], "jd_placeholder")

    def test_clean_jd_no_placeholder_rejects(self):
        """A clean JD with no placeholders passes."""
        from jd_content_validation import check_jd_placeholders

        jd = """
        Senior Product Manager at Stripe
        We are a financial infrastructure platform. You will own the
        payments dashboard roadmap and work with engineering teams.
        """
        rejects = check_jd_placeholders(jd)
        self.assertEqual(len(rejects), 0)

    def test_network_page_detected(self):
        """Talent-matching network page is caught."""
        from jd_content_validation import check_network_page

        jd = "Apply once and get matched with hundreds of employers. Join our talent network today."
        rejects = check_network_page(jd)
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["code"], "network_page")

    def test_network_page_talent_pool_detected(self):
        """'Join our talent pool' is caught."""
        from jd_content_validation import check_network_page

        jd = "Join our talent pool and get matched with companies hiring PMs."
        rejects = check_network_page(jd)
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0]["code"], "network_page")

    def test_normal_jd_not_flagged_as_network_page(self):
        """A normal single-employer JD is not flagged."""
        from jd_content_validation import check_network_page

        jd = """
        Senior Product Manager at Acme
        We are looking for a PM to join our team. You will own the roadmap
        for our SaaS platform and work cross-functionally with engineering.
        """
        rejects = check_network_page(jd)
        self.assertEqual(len(rejects), 0)

    def test_empty_jd_no_rejects(self):
        """Empty JD text produces no rejects."""
        from jd_content_validation import check_jd_placeholders, check_network_page

        self.assertEqual(check_jd_placeholders(""), [])
        self.assertEqual(check_network_page(""), [])


class TestPrefsGateIntegration(unittest.TestCase):
    """Integration tests verifying the new checks are wired into run_prefs_gate."""

    def _mock_prefs(self):
        return {
            "blocked_industries": ["Gambling", "Ad Tech", "Crypto"],
            "blocked_titles": ["Junior", "Associate"],
            "blocked_role_titles": ["Junior", "Associate"],
            "blocked_companies": [],
            "experience_range": {"min": 2, "max": 7},
            "preferences": {
                "avoid_solo_pm_trap": True,
                "no_zero_to_one": True,
            },
            "po_solo_backlog_flags": [],
            "po_solo_backlog_mitigators": [],
        }

    def test_jd_placeholder_blocks_in_prefs_gate(self):
        """run_prefs_gate rejects a JD with bracket placeholders."""
        from stage0_prefs_gate import run_prefs_gate

        jd = "Product Manager at [Company X]\n\nWe are a SaaS platform."
        result = run_prefs_gate("Acme", jd, self._mock_prefs())
        self.assertFalse(result["passed"])
        codes = [r["code"] for r in result["rejects"]]
        self.assertIn("jd_placeholder", codes)

    def test_network_page_is_flag_not_skip_in_prefs_gate(self):
        """run_prefs_gate flags a talent-matching network page and does not skip."""
        from stage0_prefs_gate import run_prefs_gate

        jd = "Apply once and get matched with employers. Join our talent network."
        result = run_prefs_gate("Acme", jd, self._mock_prefs())
        codes = [r["code"] for r in result["rejects"]]
        self.assertNotIn("network_page", codes)
        flag_codes = [r["code"] for r in result["flags"]]
        self.assertIn("network_page", flag_codes)

    def test_llm_industry_blocks_when_keyword_misses(self):
        """LLM semantic gate blocks when the keyword gate does not."""
        from stage0_prefs_gate import run_prefs_gate

        jd = """
        Senior Product Manager
        We are a leading online entertainment platform. Our products include
        casino-style games and sports betting odds for regulated markets.
        You will own the roadmap for our player experience suite.
        """
        mock_response = json.dumps({
            "blocked_industry": "Gambling",
            "confidence": "high",
            "reasoning": "casino games and sports betting = gambling",
        })
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = run_prefs_gate("EntertainmentCo", jd, self._mock_prefs())

        self.assertFalse(result["passed"])
        codes = [r["code"] for r in result["rejects"]]
        self.assertIn("blocked_industry_semantic", codes)

    def test_llm_industry_low_confidence_is_flag_not_reject(self):
        """Low-confidence LLM classification is a soft flag, not a hard reject."""
        from stage0_prefs_gate import run_prefs_gate

        jd = """
        Senior Product Manager
        We are a technology company building engagement tools.
        """
        mock_response = json.dumps({
            "blocked_industry": "Gambling",
            "confidence": "low",
            "reasoning": "possibly gambling-adjacent but unclear",
        })
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = run_prefs_gate("TechCo", jd, self._mock_prefs())

        # Should pass (low confidence = flag only, not reject)
        self.assertTrue(result["passed"])
        flag_codes = [f["code"] for f in result["flags"]]
        self.assertIn("blocked_industry_semantic_low", flag_codes)

    def test_llm_industry_fails_open_on_error(self):
        """LLM failure does not block — keyword gate result stands."""
        from stage0_prefs_gate import run_prefs_gate

        jd = """
        Senior Product Manager
        We are a B2B SaaS platform for customer experience management.
        """
        with mock.patch(
            "llm_stages.call_llm_stage",
            side_effect=RuntimeError("API down"),
        ):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = run_prefs_gate("SaaS Co", jd, self._mock_prefs())

        # Should pass — LLM failed, keyword gate didn't block, JD is clean
        self.assertTrue(result["passed"])

    def test_clean_jd_passes_all_new_gates(self):
        """A clean JD with no placeholders, no network-page text, and no blocked
        industry passes all new gates."""
        from stage0_prefs_gate import run_prefs_gate

        jd = """
        Senior Product Manager at Stripe
        We are a financial infrastructure platform. You will own the
        payments dashboard roadmap and work with engineering teams.
        5+ years of product management experience required.
        """
        mock_response = json.dumps({
            "blocked_industry": "",
            "confidence": "high",
            "reasoning": "fintech, not in blocked list",
        })
        with mock.patch("llm_stages.call_llm_stage", return_value=mock_response):
            with mock.patch("pipeline_env.fit_llm_timeout_sec", return_value=30):
                with mock.patch("pipeline_env.fit_num_predict", return_value=1024):
                    result = run_prefs_gate("Stripe", jd, self._mock_prefs())

        # May have rejects from other gates (e.g., revenue/billing), but should
        # NOT have placeholder, network_page, or blocked_industry_semantic rejects
        codes = [r["code"] for r in result["rejects"]]
        self.assertNotIn("jd_placeholder", codes)
        self.assertNotIn("network_page", codes)
        self.assertNotIn("blocked_industry_semantic", codes)


if __name__ == "__main__":
    unittest.main()
