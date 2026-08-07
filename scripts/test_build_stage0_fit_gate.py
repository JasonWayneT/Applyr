#!/usr/bin/env python3
"""
Tests for build_stage0_fit_gate.py and stage0_prefs_gate.py — no real DB, no LLM.

All fixture JDs are inline strings. DB gate is mocked to return "clear" so tests
don't need a real SQLite file for non-DB cases. Tests that exercise DB logic pass
their own in-memory connection via the stage0_db_gate._conn kwarg.

Run with:
    .venv\Scripts\python.exe -m unittest scripts.test_stage0_db_gate scripts.test_build_stage0_fit_gate -q
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_stage0_fit_gate import (
    _parse_url_and_jd,
    _detect_thin_jd,
    _detect_stage_signal,
    _extract_sections,
    classify_gaps,
    build_stage0_fit_gate,
    _load_anchor_vocab,
)
from stage0_prefs_gate import (
    run_prefs_gate,
    _check_people_management,
    _check_revenue_billing,
    _check_ai_ml_ownership,
    _check_travel,
    _check_zero_to_one,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PREFS_MINIMAL: dict = {
    "blocked_companies": ["Apex Systems", "Unity"],
    "blocked_industries": ["Gambling", "Gaming"],
    "blocked_role_titles": ["VP", "Director", "Staff"],
    "blocked_focus_area_words": ["Growth"],
    "experience_range": {"min": 2, "max": 8, "total_years_observed": 6},
    "preferences": {"avoid_solo_pm_trap": True, "structured_team_required": True},
}

# A clean, full-featured PM JD — should always be Tier 1 or Tier 2, never Skip.
_CLEAN_PM_JD = textwrap.dedent("""
    Senior Product Manager

    We are a B2B SaaS company building a platform for enterprise customers.
    You will own the product roadmap, work cross-functionally with Engineering,
    Design, and Sales, and drive measurable outcomes.

    What you'll do
    - Define and own the product roadmap for our core platform
    - Partner with engineering to deliver features end-to-end
    - Run stakeholder reviews and communicate progress to the C-suite
    - Analyze customer feedback and data to drive prioritization decisions

    What we're looking for
    - 3-5 years of product management experience in a B2B SaaS or enterprise software environment
    - Strong agile and backlog grooming skills
    - Experience with stakeholder management and roadmap planning
    - Data-driven decision-making with SQL and product analytics
    - Comfortable working with engineering teams on technical specifications

    Preferred qualifications
    - Experience with Jira and Confluence
    - Prior work in integration-heavy platforms

    About us
    We value transparency, iteration, and user empathy. We are a Series B company backed by top-tier VCs.
""").strip()

# A JD that requires FHIR → must produce a HARD gap → Skip.
_FHIR_JD = textwrap.dedent("""
    Senior Product Manager – Health Integrations

    You will own our HL7 FHIR integration layer and work closely with engineering
    to ensure compliance with healthcare data standards.

    Requirements
    - 3+ years of product management experience
    - Deep expertise in FHIR, HL7, and healthcare data exchange standards
    - Familiarity with EHR systems (Epic, Cerner)
    - Agile experience and backlog management

    About us
    Elation Health is a clinical platform serving primary care physicians.
""").strip()

# A very short JD — should produce thin_jd = True.
_THIN_JD = textwrap.dedent("""
    Product Manager

    We are hiring a PM. You should have 3 years of experience.
    Apply with resume.
""").strip()

# A JD for a blocked company.
_BLOCKED_COMPANY = "Apex Systems"

# A gambling-industry JD.
_GAMBLING_JD = textwrap.dedent("""
    Product Manager – Sports Betting Platform

    Our Gambling and sports wagering platform needs an experienced PM to own
    the real-money betting product roadmap.

    Requirements
    - 3+ years PM experience
    - Experience in regulated Gaming or Sports Betting markets
    - Strong agile background
""").strip()

# A JD requiring people management.
_PEOPLE_MGT_JD = textwrap.dedent("""
    Group Product Manager

    In this role you will manage a team of 3 product managers and be responsible
    for headcount planning and performance reviews.

    Requirements
    - 5+ years of product management experience
    - People management experience required
    - Strong roadmap and agile skills
""").strip()

# A JD requiring solo-PM / 0-to-1.
_SOLO_PM_JD = textwrap.dedent("""
    Founding Product Manager

    You will be our first product manager, responsible for establishing the PM
    function and building our product from scratch.

    Requirements
    - 4+ years experience
    - Comfort with ambiguity and building product teams
""").strip()

# A JD requiring revenue/billing ownership.
_REVENUE_OWN_JD = textwrap.dedent("""
    Product Manager – Payments

    You will own the billing platform and drive P&L ownership for our payments product.

    Requirements
    - 4+ years of product management
    - Proven revenue ownership and billing product experience
    - Experience with P&L management and pricing strategy
""").strip()

# A JD requiring ML model building.
_ML_MODEL_JD = textwrap.dedent("""
    AI/ML Product Manager

    You will build ML models and own the AI model pipeline end-to-end.

    Requirements
    - 3+ years PM experience
    - Direct experience training and deploying machine learning models
    - TensorFlow or PyTorch background preferred
""").strip()

# A JD with travel over 15%.
_HIGH_TRAVEL_JD = textwrap.dedent("""
    Product Manager – Enterprise Sales

    Requirements
    - 4+ years of PM experience
    - Willingness to travel up to 40% for customer visits
    - Strong stakeholder management skills
""").strip()

# A JD with URL on first line.
_URL_JD = "URL: https://example.com/jobs/pm-role\n\nSenior Product Manager\n\nRequirements\n- 3+ years PM experience in SaaS\n- Agile backlog management"

# A standard Snowflake JD — Snowflake is a hard-blocked tool.
_SNOWFLAKE_JD = textwrap.dedent("""
    Data Product Manager

    Requirements
    - 3+ years of product management experience
    - Deep familiarity with Snowflake data warehouse and dbt
    - Experience with SQL and analytics tools
    - Strong agile background
""").strip()

# DB gate "clear" mock result.
_DB_CLEAR = {"action": "clear", "reason_code": "no_terminal_rows", "reason": "No prior rows", "matched_rows": []}
# DB gate "reject" mock result.
_DB_REJECT = {"action": "reject", "reason_code": "self_rejected", "reason": "Self-Rejected (permanent)", "matched_rows": []}
# DB gate "reapply_flag" mock result.
_DB_REAPPLY = {"action": "reapply_flag", "reason_code": "reapply_eligible", "reason": "Cooldown expired", "matched_rows": []}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_submission_folder(jd_text: str) -> Path:
    """Write JD text to a temp folder and return the folder path."""
    d = Path(tempfile.mkdtemp())
    (d / "Original_JD.txt").write_text(jd_text, encoding="utf-8")
    return d


def _build(jd_text: str, company: str = "TestCo", db_result: dict | None = None) -> dict:
    """Build stage0 result for inline JD text."""
    folder = _make_submission_folder(jd_text)
    # Rename folder to match company slug for display
    return build_stage0_fit_gate(
        folder,
        db_gate_result=db_result or _DB_CLEAR,
        prefs=_PREFS_MINIMAL,
        vocab=_load_anchor_vocab(),
    )


# ---------------------------------------------------------------------------
# Test: URL parsing
# ---------------------------------------------------------------------------

class TestUrlParsing(unittest.TestCase):
    def test_url_extracted(self):
        url, body = _parse_url_and_jd(_URL_JD)
        self.assertEqual(url, "https://example.com/jobs/pm-role")
        self.assertIn("Senior Product Manager", body)

    def test_no_url(self):
        url, body = _parse_url_and_jd(_CLEAN_PM_JD)
        self.assertEqual(url, "")
        self.assertIn("Senior Product Manager", body)

    def test_url_preserved_in_output(self):
        folder = _make_submission_folder(_URL_JD)
        result = build_stage0_fit_gate(
            folder,
            db_gate_result=_DB_CLEAR,
            prefs=_PREFS_MINIMAL,
        )
        self.assertEqual(result["url"], "https://example.com/jobs/pm-role")


# ---------------------------------------------------------------------------
# Test: Thin JD detection
# ---------------------------------------------------------------------------

class TestThinJd(unittest.TestCase):
    def test_thin_jd_detected(self):
        result = _build(_THIN_JD)
        self.assertTrue(result["thin_jd"], "short JD should be flagged thin")

    def test_full_jd_not_thin(self):
        result = _build(_CLEAN_PM_JD)
        self.assertFalse(result["thin_jd"], "full JD should not be thin")


# ---------------------------------------------------------------------------
# Test: Stage signal detection
# ---------------------------------------------------------------------------

class TestStageSignal(unittest.TestCase):
    def test_series_b_detected(self):
        sig = _detect_stage_signal(_CLEAN_PM_JD)
        self.assertIn("Series", sig)

    def test_unknown_stage(self):
        sig = _detect_stage_signal(_THIN_JD)
        self.assertIn("not stated", sig)


# ---------------------------------------------------------------------------
# Test: Section extraction
# ---------------------------------------------------------------------------

class TestSectionExtraction(unittest.TestCase):
    def test_required_extracted(self):
        sections = _extract_sections(_CLEAN_PM_JD)
        self.assertGreater(len(sections["required"]), 0)

    def test_preferred_extracted(self):
        sections = _extract_sections(_CLEAN_PM_JD)
        self.assertGreater(len(sections["preferred"]), 0)

    def test_responsibilities_extracted(self):
        sections = _extract_sections(_CLEAN_PM_JD)
        self.assertGreater(len(sections["responsibilities"]), 0)


# ---------------------------------------------------------------------------
# Test: Gap classification
# ---------------------------------------------------------------------------

class TestGapClassification(unittest.TestCase):
    def setUp(self):
        self.vocab = _load_anchor_vocab()

    def test_fhir_is_hard_gap(self):
        reqs = ["Deep expertise in FHIR and HL7 healthcare data exchange standards"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(classified[0]["gap"], "FHIR should be flagged as a gap")
        self.assertEqual(classified[0]["gap_class"], "HARD")

    def test_agile_is_not_a_gap(self):
        reqs = ["3+ years of product management experience in an agile environment"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        # Agile / product management should have anchors
        self.assertFalse(classified[0]["gap"], "agile/PM exp should find anchors")

    def test_snowflake_is_hard_gap(self):
        reqs = ["Deep familiarity with Snowflake data warehouse"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(classified[0]["gap"])
        self.assertEqual(classified[0]["gap_class"], "HARD")

    def test_domain_gap_is_soft(self):
        # Healthcare domain knowledge (not a named hard tool) → SOFT
        reqs = ["Prior experience in the healthcare industry or regulated environment"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        if classified[0]["gap"]:
            self.assertEqual(classified[0]["gap_class"], "SOFT")

    def test_preferred_item_has_handling(self):
        prefs = ["CMMS experience preferred"]
        _, classified_pref, _ = classify_gaps([], prefs, vocab=self.vocab)
        self.assertIn("handling", classified_pref[0])

    def test_flagged_gaps_populated(self):
        reqs = ["FHIR expertise required", "3+ years agile PM experience"]
        _, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(any(g.get("gap_class") == "HARD" for g in flagged))


# ---------------------------------------------------------------------------
# Test: Clean PM JD → not Skip
# ---------------------------------------------------------------------------

class TestCleanPmJd(unittest.TestCase):
    def test_not_skip(self):
        result = _build(_CLEAN_PM_JD)
        self.assertIn(result["tier"], {"Tier 1", "Tier 2"}, "clean PM JD must not be Skip")
        self.assertEqual(result["decision"], "PASS")

    def test_has_required_items(self):
        result = _build(_CLEAN_PM_JD)
        self.assertGreater(len(result["required"]), 0)

    def test_has_responsibilities(self):
        result = _build(_CLEAN_PM_JD)
        self.assertGreater(len(result["responsibilities"]), 0)

    def test_company_and_role_present(self):
        result = _build(_CLEAN_PM_JD)
        self.assertIn("company", result)
        self.assertIn("role", result)


# ---------------------------------------------------------------------------
# Test: FHIR JD → Skip (HARD gap)
# ---------------------------------------------------------------------------

class TestFhirJd(unittest.TestCase):
    def test_fhir_produces_skip(self):
        result = _build(_FHIR_JD)
        self.assertEqual(result["tier"], "Skip")
        self.assertEqual(result["decision"], "SKIP")

    def test_fhir_flagged_as_hard(self):
        result = _build(_FHIR_JD)
        hard_gaps = [g for g in result["flagged_gaps"] if g.get("gap_class") == "HARD"]
        self.assertGreater(len(hard_gaps), 0)


# ---------------------------------------------------------------------------
# Test: Snowflake JD → Skip
# ---------------------------------------------------------------------------

class TestSnowflakeJd(unittest.TestCase):
    def test_snowflake_produces_skip(self):
        result = _build(_SNOWFLAKE_JD)
        self.assertEqual(result["tier"], "Skip")


# ---------------------------------------------------------------------------
# Test: Prefs gate — blocked company
# ---------------------------------------------------------------------------

class TestBlockedCompany(unittest.TestCase):
    def test_blocked_company_reject(self):
        gate = run_prefs_gate(_BLOCKED_COMPANY, _CLEAN_PM_JD, _PREFS_MINIMAL)
        self.assertFalse(gate["passed"])
        codes = {r["code"] for r in gate["rejects"]}
        self.assertIn("blocked_company", codes)

    def test_non_blocked_company_passes(self):
        gate = run_prefs_gate("Acme Corp", _CLEAN_PM_JD, _PREFS_MINIMAL)
        blocked_codes = {r["code"] for r in gate["rejects"]}
        self.assertNotIn("blocked_company", blocked_codes)


# ---------------------------------------------------------------------------
# Test: Prefs gate — blocked industry
# ---------------------------------------------------------------------------

class TestBlockedIndustry(unittest.TestCase):
    def test_gambling_jd_blocked(self):
        gate = run_prefs_gate("BetCo", _GAMBLING_JD, _PREFS_MINIMAL)
        self.assertFalse(gate["passed"])
        codes = {r["code"] for r in gate["rejects"]}
        self.assertIn("blocked_industry", codes)


# ---------------------------------------------------------------------------
# Test: Prefs gate — people management exclusion zone
# ---------------------------------------------------------------------------

class TestPeopleManagement(unittest.TestCase):
    def test_people_management_blocked(self):
        rejects = _check_people_management(_PEOPLE_MGT_JD)
        codes = {r["code"] for r in rejects}
        self.assertIn("exclusion_zone_people_management", codes)

    def test_clean_pm_not_flagged(self):
        rejects = _check_people_management(_CLEAN_PM_JD)
        self.assertEqual(rejects, [])

    def test_via_prefs_gate(self):
        gate = run_prefs_gate("AnyCompany", _PEOPLE_MGT_JD, _PREFS_MINIMAL)
        self.assertFalse(gate["passed"])


# ---------------------------------------------------------------------------
# Test: Prefs gate — revenue/billing exclusion zone
# ---------------------------------------------------------------------------

class TestRevenueBilling(unittest.TestCase):
    def test_revenue_own_blocked(self):
        rejects = _check_revenue_billing(_REVENUE_OWN_JD)
        codes = {r["code"] for r in rejects}
        self.assertIn("exclusion_zone_revenue_billing", codes)

    def test_revenue_mention_not_blocked(self):
        # "Grow revenue", "improve revenue metrics" should NOT trigger
        ok_jd = "You will drive revenue growth and monitor revenue metrics for the product."
        rejects = _check_revenue_billing(ok_jd)
        self.assertEqual(rejects, [])


# ---------------------------------------------------------------------------
# Test: Prefs gate — AI/ML model ownership exclusion zone
# ---------------------------------------------------------------------------

class TestAiMlOwnership(unittest.TestCase):
    def test_ml_model_training_blocked(self):
        rejects = _check_ai_ml_ownership(_ML_MODEL_JD)
        codes = {r["code"] for r in rejects}
        self.assertIn("exclusion_zone_ai_ml_ownership", codes)

    def test_ai_tooling_not_blocked(self):
        # ACC-401 tooling language — must NOT false-positive
        tooling_jd = textwrap.dedent("""
            Requirements
            - AI fluency: use AI tools like Claude, Gemini, and ChatGPT daily
            - Comfortable with prompt engineering and AI-assisted workflows
            - Use AI tools to accelerate documentation and requirements drafting
        """)
        rejects = _check_ai_ml_ownership(tooling_jd)
        self.assertEqual(rejects, [], "AI tooling language must NOT trigger exclusion zone")


# ---------------------------------------------------------------------------
# Test: Prefs gate — travel ceiling
# ---------------------------------------------------------------------------

class TestTravelCeiling(unittest.TestCase):
    def test_high_travel_blocked(self):
        rejects = _check_travel(_HIGH_TRAVEL_JD)
        codes = {r["code"] for r in rejects}
        self.assertIn("travel_ceiling", codes)

    def test_low_travel_ok(self):
        low_jd = "Occasional travel up to 10% for team meetings."
        rejects = _check_travel(low_jd)
        self.assertEqual(rejects, [])

    def test_no_travel_mention_ok(self):
        rejects = _check_travel(_CLEAN_PM_JD)
        self.assertEqual(rejects, [])


# ---------------------------------------------------------------------------
# Test: Solo PM trap gate
# ---------------------------------------------------------------------------

class TestSoloPmTrap(unittest.TestCase):
    def test_founding_pm_blocked(self):
        gate = run_prefs_gate("NewStartup", _SOLO_PM_JD, _PREFS_MINIMAL)
        self.assertFalse(gate["passed"])
        codes = {r["code"] for r in gate["rejects"]}
        # Either solo_pm_trap or exclusion_zone_zero_to_one
        self.assertTrue(
            "solo_pm_trap" in codes or "exclusion_zone_zero_to_one" in codes,
            f"Expected solo/zero-to-one code, got: {codes}",
        )


# ---------------------------------------------------------------------------
# Test: DB gate interaction
# ---------------------------------------------------------------------------

class TestDbGateInteraction(unittest.TestCase):
    def test_db_reject_produces_skip(self):
        result = _build(_CLEAN_PM_JD, db_result=_DB_REJECT)
        self.assertEqual(result["tier"], "Skip")
        self.assertEqual(result["decision"], "SKIP")

    def test_db_reapply_flag_at_least_tier2(self):
        result = _build(_CLEAN_PM_JD, db_result=_DB_REAPPLY)
        # Reapply flag should cause at least Tier 2 (maybe Tier 1 if no gaps, but
        # db_reapply_flag should push to Tier 2)
        self.assertIn(result["tier"], {"Tier 2"})
        self.assertTrue(result.get("db_reapply_flag", False))

    def test_db_clear_allows_tier1(self):
        result = _build(_CLEAN_PM_JD, db_result=_DB_CLEAR)
        self.assertIn(result["tier"], {"Tier 1", "Tier 2"})


# ---------------------------------------------------------------------------
# Test: Output shape
# ---------------------------------------------------------------------------

class TestOutputShape(unittest.TestCase):
    def test_required_fields_present(self):
        result = _build(_CLEAN_PM_JD)
        required_keys = {
            "company", "role", "decision", "tier", "reach_out",
            "stage_signal", "thin_jd", "required", "preferred",
            "responsibilities", "flagged_gaps", "exclusion_zone_check", "notes",
        }
        missing = required_keys - set(result.keys())
        self.assertEqual(missing, set(), f"Missing keys: {missing}")

    def test_required_items_have_correct_shape(self):
        result = _build(_CLEAN_PM_JD)
        for item in result["required"]:
            self.assertIn("item", item)
            self.assertIn("anchor", item)
            self.assertIn("gap", item)

    def test_flagged_gaps_have_gap_class(self):
        result = _build(_FHIR_JD)
        for gap in result["flagged_gaps"]:
            self.assertIn("gap_class", gap)
            self.assertIn(gap["gap_class"], {"HARD", "SOFT"})

    def test_json_serializable(self):
        result = _build(_CLEAN_PM_JD)
        # Should not raise
        _ = json.dumps(result)


# ---------------------------------------------------------------------------
# Test: write to disk
# ---------------------------------------------------------------------------

class TestWriteToDisk(unittest.TestCase):
    def test_output_file_written(self):
        folder = _make_submission_folder(_CLEAN_PM_JD)
        result = build_stage0_fit_gate(
            folder,
            db_gate_result=_DB_CLEAR,
            prefs=_PREFS_MINIMAL,
        )
        # Manually write (CLI would do this)
        out_path = folder / "stage0_fit_gate.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        self.assertTrue(out_path.exists())
        loaded = json.loads(out_path.read_text())
        self.assertEqual(loaded["decision"], result["decision"])


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
