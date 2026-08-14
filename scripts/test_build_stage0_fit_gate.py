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
    _has_extraction_override,
    batch_report,
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

    def test_sparse_headerless_prose_over_80_words_is_thin(self):
        """Cluster C item 10: clear_capital-class ~99-word headerless prose."""
        # ~99 words, no Requirements/What we're looking for headers → 0 requireds.
        words = (
            "Clear Capital is hiring a Product Manager to own roadmap work across "
            "data products and client workflows in real estate valuation. "
            "You will partner with engineering and stakeholders, ship incremental "
            "improvements, and use data to prioritize. The role needs someone who "
            "can write crisp specs, run discovery with customers, and keep delivery "
            "honest when scope shifts. Experience with SaaS platforms, analytics, "
            "and cross-functional alignment matters. Apply with a resume that shows "
            "ownership of ambiguous problems and measurable outcomes over several "
            "years of product work in enterprise software environments today."
        )
        self.assertGreaterEqual(len(words.split()), 80)
        self.assertLess(len(words.split()), 150)
        self.assertTrue(
            _detect_thin_jd(words, required_items=[]),
            "headerless sparse prose under 150 words with 0 requireds must be thin",
        )
        # Same word count but with extractable requireds is not thin.
        self.assertFalse(_detect_thin_jd(words, required_items=["a", "b"]))


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

    def test_curly_apostrophe_headers_extract(self):
        """Greenhouse-style curly apostrophes must not empty the buckets."""
        jd = textwrap.dedent(
            """
            Product Manager

            What you\u2019ll do:
            - Own the product roadmap and backlog for digital servicing
            - Partner with engineering and design on delivery

            What we\u2019re looking for:
            - 3+ years of product management experience
            - Strong analytical and communication skills
            """
        )
        sections = _extract_sections(jd)
        self.assertGreater(len(sections["responsibilities"]), 0)
        self.assertGreater(len(sections["required"]), 0)

    def test_pinterest_tail_boilerplate_not_in_required(self):
        """Relocation / Inclusion / salary after quals must not become soft-gap bait."""
        jd = textwrap.dedent(
            """
            Product Manager II, Search Experience

            What you\u2019ll do:
            - Develop and execute a cohesive Search strategy and roadmap

            What we\u2019re looking for:
            Strong product sense: Strong product sense and ability to collaborate and get buy-in.
            Experience building AI/ML products: Demonstrated success working on AI/ML based products.
            Bring structure to ambiguity: Proven ability to lead in ambiguous environments.
            Bachelor\u2019s degree in a relevant field such as computer science or equivalent experience.

            Relocation Statement:

            This position is not eligible for relocation assistance. Visit our PinFlex page to learn more about our working model.

            In-Office Requirement Statement:

            This role will need to be in the office for in-person collaboration 1-2 times/quarter.

            #LI-NM4

            #LI-REMOTE

            Information regarding the culture at Pinterest and benefits available for this position can be found here.

            US based applicants only
            $114,297\u2014$235,319 USD

            Our Commitment to Inclusion:

            Pinterest is an equal opportunity employer and makes employment decisions on the basis of merit.
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertGreaterEqual(len(sections["required"]), 3)
        self.assertTrue(any("product sense" in r.lower() for r in sections["required"]))
        self.assertTrue(any("ai/ml" in r.lower() for r in sections["required"]))
        for junk in (
            "relocation",
            "pinflex",
            "inclusion",
            "equal opportunity",
            "us based applicants",
            "114,297",
            "#li-",
            "in-office",
        ):
            self.assertNotIn(junk, required_blob, f"junk leaked into required: {junk}")

    def test_labeled_requirement_with_colon_body_kept(self):
        """'Label: body…' hire criteria must not be treated as section-ending headers."""
        jd = textwrap.dedent(
            """
            What we're looking for:
            Strong product sense: Ability to collaborate and set longer term vision.
            Technical strength: Partner closely with Engineering on Machine Learning.
            """
        )
        sections = _extract_sections(jd)
        self.assertEqual(len(sections["required"]), 2)

    def test_success_metrics_section_not_in_required(self):
        """Post-hire KPI sections ('Success Metrics' / 'will be measured on:') are
        not candidate requirements -- found 2026-08-07 on envision_technology_solutions,
        where these bled into required and produced fake soft-gap noise."""
        jd = textwrap.dedent(
            """
            Requirements

            5-8+ years of experience in Product Ownership or Product Management.
            At least 3 years of experience working within Agile/Scrum teams.

            Success Metrics

            The successful Product Owner will be measured on:

            Delivery predictability and sprint success
            Stakeholder satisfaction
            Reduction in production defects due to requirement clarity
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertTrue(any("5-8+ years" in r for r in sections["required"]))
        for junk in ("stakeholder satisfaction", "delivery predictability", "production defects"):
            self.assertNotIn(junk, required_blob, f"post-hire KPI leaked into required: {junk}")

    def test_colon_leadin_not_captured_as_standalone_item(self):
        """A short lead-in line ending in a bare colon ('Experience working on one
        or more of:') is an intro to the list below it, not a requirement on its
        own -- found 2026-08-07 on envision_technology_solutions. The real items
        below the lead-in must still be captured."""
        jd = textwrap.dedent(
            """
            Requirements

            Experience working on one or more of:

            eCommerce Platforms
            Digital Commerce Marketplace

            Hands-on experience with:

            Agile Product Management Tools
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertNotIn("experience working on one or more of", required_blob)
        self.assertNotIn("hands-on experience with", required_blob)
        self.assertTrue(any("ecommerce platforms" in r.lower() for r in sections["required"]))
        self.assertTrue(any("agile product management" in r.lower() for r in sections["required"]))

    def test_benefits_eeo_other_duties_headers_end_required(self):
        """'We Offer All Full-time Team Members' / 'AAP/EEO Statement' / 'Other
        Duties' are boilerplate section headers, not requirement headers -- found
        2026-08-07 on ncontracts, where an entire benefits/EEO/legal list bled
        into required (11 paid holidays, 401k, AAP/EEO statement text)."""
        jd = textwrap.dedent(
            """
            Requirements

            3+ years of relevant B2B SaaS product management experience.

            We Offer All Full-time Team Members

            11 paid holidays per year
            401k with company match

            AAP/EEO Statement

            We are an equal opportunity employer and value diversity.

            Other Duties

            This job description is not an exhaustive list of duties.
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertTrue(any("b2b saas" in r.lower() for r in sections["required"]))
        for junk in ("paid holidays", "401k", "equal opportunity", "exhaustive list of duties"):
            self.assertNotIn(junk, required_blob, f"benefits/EEO/legal boilerplate leaked into required: {junk}")

    def test_recruiter_third_person_leadin_recognized(self):
        """'A few things they're looking for:' (recruiter's third-person phrasing)
        must open the required bucket -- found 2026-08-07 on w_talent_client, where
        this phrasing wasn't recognized at all and the entire required bucket
        extracted empty, silently missing a real hard requirement."""
        jd = textwrap.dedent(
            """
            A few things they're looking for:

            Capital Markets experience is essential.
            5+ years of product management experience.
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertTrue(any("capital markets" in r.lower() for r in sections["required"]))

    def test_inline_is_preferred_routes_to_preferred_bucket(self):
        """A line that self-labels 'is preferred' should land in the preferred
        bucket even though the surrounding section header is 'Qualifications' --
        found 2026-08-07 on envision_technology_solutions, where the CSPO
        certification line stayed lumped into required as a hard requirement."""
        jd = textwrap.dedent(
            """
            Qualifications

            Bachelor's degree in Business, Computer Science, or a related field.
            Certified Scrum Product Owner (CSPO) or equivalent certification is preferred.
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertNotIn("cspo", required_blob)
        self.assertTrue(any("cspo" in p.lower() for p in sections["preferred"]))

    def test_cr086_amn_job_responsibilities_header_switches_bucket(self):
        """CR-086: 'Job Responsibilities' mid-JD must switch to responsibilities,
        not land as a required *item* (AMN Healthcare bleed)."""
        jd = textwrap.dedent(
            """
            Requirements

            4+ years of product management experience in SaaS.
            Hands-on experience using AI/ML in daily product workflows.

            Job Responsibilities

            Evaluate market trends and competitors to improve the product.
            Develop product briefs and define achievable acceptance criteria.

            Work Environment / Physical Requirements

            Work is performed in an office/home office environment.
            Team Members must have the ability to operate standard office equipment and keyboards.
            AMN Healthcare will provide reasonable accommodations to qualified individuals with disabilities to perform essential functions.
            Final pay rate is dependent on experience, training, education, and location.

            Our Core Values

            At AMN we recognize that in-person connections have value.
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        resp_blob = " | ".join(sections["responsibilities"]).lower()
        all_scored = " | ".join(
            sections["required"] + sections["preferred"] + sections["responsibilities"]
        ).lower()

        self.assertNotIn("job responsibilities", required_blob)
        self.assertNotIn("work environment", required_blob)
        self.assertNotIn("our core values", required_blob)
        self.assertTrue(any("4+" in r or "years" in r.lower() for r in sections["required"]))
        self.assertTrue(any("market trends" in r.lower() for r in sections["responsibilities"]))
        self.assertTrue(any("product briefs" in r.lower() for r in sections["responsibilities"]))
        for junk in (
            "office/home office",
            "office equipment",
            "reasonable accommodations",
            "final pay rate",
        ):
            self.assertNotIn(junk, all_scored, f"physical/comp/ADA boilerplate leaked: {junk}")
        # Core values body should not stay in required
        self.assertNotIn("in-person connections", required_blob)

    def test_cr086_orphan_header_item_dropped(self):
        """Belt-and-suspenders: a bare Title-Case label with no verb is not a criterion."""
        from build_stage0_fit_gate import _is_boilerplate_item, _is_orphan_header_item

        self.assertTrue(_is_orphan_header_item("Job Responsibilities"))
        self.assertTrue(_is_orphan_header_item("Our Core Values"))
        self.assertTrue(_is_boilerplate_item("Job Responsibilities"))
        # Real criteria must survive
        self.assertFalse(
            _is_orphan_header_item(
                "3-5 years of product management experience in a B2B SaaS environment"
            )
        )
        self.assertFalse(
            _is_boilerplate_item(
                "3-5 years of product management experience in a B2B SaaS environment"
            )
        )

    def test_domain_qualified_preferred_is_soft_gap(self):
        """Banking+compliance preferred stays SOFT even if 'compliance' tags match."""
        vocab = _load_anchor_vocab()
        # Ensure compliance-ish anchors exist so this isn't a no-anchor soft gap
        vocab = set(vocab) | {"compliance", "regulatory", "privacy"}
        prefs = [
            "Familiarity with regulatory and compliance considerations in banking product development."
        ]
        _, classified_pref, flagged = classify_gaps([], prefs, vocab=vocab)
        self.assertTrue(classified_pref[0]["gap"])
        self.assertEqual(classified_pref[0]["gap_class"], "SOFT")
        self.assertTrue(classified_pref[0].get("domain_soft"))
        self.assertTrue(any("banking" in g["item"].lower() for g in flagged))


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


class TestExtractionOverrideProtection(unittest.TestCase):
    """Found 2026-08-08 (session-005 R14): a bare re-run had zero awareness of a
    hand-corrected extraction_override:true flag and would silently clobber it."""

    def _protected_folder(self) -> Path:
        folder = _make_submission_folder(_CLEAN_PM_JD)
        out_path = folder / "stage0_fit_gate.json"
        out_path.write_text(
            json.dumps({"tier": "Tier 2", "decision": "PASS", "extraction_override": True,
                        "override_reason": "hand-reconstructed, extractor mis-parsed"}, indent=2),
            encoding="utf-8",
        )
        return folder

    def test_has_extraction_override_detects_flag(self):
        folder = self._protected_folder()
        self.assertTrue(_has_extraction_override(folder / "stage0_fit_gate.json"))

    def test_has_extraction_override_false_when_absent(self):
        folder = _make_submission_folder(_CLEAN_PM_JD)
        self.assertFalse(_has_extraction_override(folder / "stage0_fit_gate.json"))

    def test_has_extraction_override_false_when_no_file(self):
        folder = _make_submission_folder(_CLEAN_PM_JD)
        missing = folder / "does_not_exist.json"
        self.assertFalse(_has_extraction_override(missing))

    def test_batch_report_does_not_overwrite_protected_folder_by_default(self):
        folder = self._protected_folder()
        out_path = folder / "stage0_fit_gate.json"
        before = out_path.read_text(encoding="utf-8")
        batch_report([folder], write=True, force=False)
        after = out_path.read_text(encoding="utf-8")
        self.assertEqual(before, after, "protected gate must not be overwritten without --force")

    def test_batch_report_overwrites_protected_folder_with_force(self):
        folder = self._protected_folder()
        out_path = folder / "stage0_fit_gate.json"
        before = out_path.read_text(encoding="utf-8")
        batch_report([folder], write=True, force=True)
        after = out_path.read_text(encoding="utf-8")
        self.assertNotEqual(before, after, "--force must overwrite even a protected gate")
        loaded = json.loads(after)
        self.assertNotIn("extraction_override", loaded, "a fresh run's own output has no override flag")

    def test_batch_report_writes_unprotected_folder_normally(self):
        folder = _make_submission_folder(_CLEAN_PM_JD)
        out_path = folder / "stage0_fit_gate.json"
        self.assertFalse(out_path.exists())
        batch_report([folder], write=True, force=False)
        self.assertTrue(out_path.exists())


# ---------------------------------------------------------------------------
# Test: 2026-08-10 batch remediation (54-submission Stage 0 audit)
# ---------------------------------------------------------------------------

class TestBareRequiredHeader(unittest.TestCase):
    """Deloitte-class: bare 'Required:' must open the required bucket.
    Regex was requirements? only (requirement/requirements), never 'Required'."""

    def test_bare_required_colon_extracts_items(self):
        jd = textwrap.dedent(
            """
            Product Manager

            The Key Responsibilities:
            - Own the product roadmap for the research center
            - Partner with engineering on delivery

            Required:
            - 5+ years of product management experience in B2B SaaS
            - Strong stakeholder management and roadmap planning skills
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["responsibilities"]), 2)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertTrue(any("5+ years" in r for r in sections["required"]))


class TestWorkYoullDoAndRolesHeaders(unittest.TestCase):
    def test_work_youll_do_is_responsibilities(self):
        jd = textwrap.dedent(
            """
            Work you'll do
            - Define product strategy for the platform
            - Lead cross-functional delivery with engineering

            Requirements
            - 4+ years of product management experience
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["responsibilities"]), 2)
        self.assertTrue(any("product strategy" in r.lower() for r in sections["responsibilities"]))

    def test_roles_and_responsibilities_header(self):
        jd = textwrap.dedent(
            """
            Roles and Responsibilities:
            - Coordinate product submissions with licensees
            - Track deadlines across the global team

            Experience and Qualifications
            - Bachelor's degree in Business or related field
            - 3+ years of product coordination experience
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["responsibilities"]), 2)
        self.assertGreaterEqual(len(sections["required"]), 2)


class TestKnowledgeSkillsAbilitiesHeader(unittest.TestCase):
    def test_ksa_header_opens_required(self):
        jd = textwrap.dedent(
            """
            Knowledge, Skills, and Abilities
            - Strong written communication and stakeholder management
            - Ability to manage multiple deadlines under ambiguity

            Benefits
            - Medical, dental, and vision coverage
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["required"]), 2)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertNotIn("medical, dental", required_blob)


class TestLeadingBonusRoutesPreferred(unittest.TestCase):
    """Seed Health: 'Bonus: ... Braze ...' stayed in required, hit hard-blocked
    Braze, and forced Skip. Leading Bonus: must route to preferred so a bonus
    tool mention cannot Skip the whole JD."""

    def test_leading_bonus_line_goes_to_preferred(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Strong roadmap and prioritization skills
            Bonus: experience in DTC e-commerce; familiarity with Shopify or lifecycle/CRM systems (e.g., Klaviyo, Braze, Iterable)
            """
        )
        sections = _extract_sections(jd)
        required_blob = " | ".join(sections["required"]).lower()
        self.assertNotIn("braze", required_blob)
        self.assertTrue(any("braze" in p.lower() for p in sections["preferred"]))

    def test_bonus_braze_does_not_skip_jd(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Strong roadmap and prioritization skills
            Bonus: exposure to lifecycle/CRM systems (e.g., Klaviyo, Braze, Iterable)
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip")
        self.assertNotEqual(result["decision"], "SKIP")
        hard = [g for g in result["flagged_gaps"] if g.get("gap_class") == "HARD"]
        self.assertEqual(hard, [], f"preferred Bonus tool must not produce HARD flagged gaps: {hard}")


class TestBoilerplateNoiseNotSoftGaps(unittest.TestCase):
    """Measured 2026-08-10 on live submissions: E-Verify, pay notes, orphan
    section labels, and benefits headers were becoming SOFT gaps."""

    def test_everify_and_pay_notes_dropped(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            Amplify is an E-Verify participant.
            Note: Starting pay will be based on a number of factors and commensurate with qualifications & experience.
            We also have a location based compensation structure; there may be a different range for candidates in this and other locations
            """
        )
        sections = _extract_sections(jd)
        blob = " | ".join(sections["required"]).lower()
        for junk in ("e-verify", "starting pay", "location based compensation"):
            self.assertNotIn(junk, blob, f"boilerplate leaked into required: {junk}")

    def test_orphan_labels_and_benefits_headers_dropped(self):
        from build_stage0_fit_gate import _is_boilerplate_item

        for label in (
            "Your Qualifications",
            "What You Can Expect From Us",
            "How Will You Make An Impact",
            "More about Nash",
            "Ways of Working",
            "Anticipated Position Close Date",
            "Disability, Life Insurance and Ancillary Benefits",
        ):
            self.assertTrue(
                _is_boilerplate_item(label),
                f"expected orphan/benefits label to be boilerplate: {label!r}",
            )

    def test_hybrid_policy_blurb_dropped(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 4+ years of product management experience
            Please note that per our policy on hybrid/virtual work, candidates not within a reasonable commuting distance from the posting location(s) will not be considered for employment, unless accommodation is granted as required by law.
            """
        )
        sections = _extract_sections(jd)
        blob = " | ".join(sections["required"]).lower()
        self.assertNotIn("hybrid/virtual work", blob)


class TestReadyNetStyleInformalHeaders(unittest.TestCase):
    """Ready Net: informal 'About Your Role' / 'A Bit About You' headers left
    all buckets empty → false extraction_empty Tier 2."""

    def test_about_your_role_and_bit_about_you(self):
        jd = textwrap.dedent(
            """
            Technical Product Manager

            About Your Role At Ready

            Define and communicate a clear product vision that aligns with business goals.
            Develop and maintain a comprehensive product roadmap with key milestones.

            A Bit About You

            Bachelor's or Master's degree in a relevant technical field or equivalent experience.
            Proven experience as a Technical Product Manager at the mid to senior level.
            Strong technical background with software development processes.

            About Ready

            Humble but ambitious, knowledgeable but curious, persistent but not obnoxious
            Comfortable working remotely

            About What You Get

            Competitive salary plus meaningful equity upside
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["responsibilities"]), 2)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertTrue(any("technical product manager" in r.lower() for r in sections["required"]))
        required_blob = " | ".join(sections["required"]).lower()
        for junk in ("humble but ambitious", "comfortable working remotely"):
            self.assertNotIn(junk, required_blob, f"culture personality leaked into required: {junk}")


class TestRealtimeAllCapsHeaders(unittest.TestCase):
    """RealTime eClinical: WHO ARE WE? / WHAT ARE WE LOOKING FOR? / WHAT WILL
    YOU BE DOING? left buckets empty."""

    def test_all_caps_looking_for_and_doing(self):
        jd = textwrap.dedent(
            """
            Product Owner

            WHO ARE WE?
            RealTime is a SaaS company for clinical research.

            WHAT ARE WE LOOKING FOR?
            5+ years of product ownership experience in B2B SaaS
            Strong agile backlog and user story writing skills

            WHAT WILL YOU BE DOING?
            Translate product initiatives into clear user stories and acceptance criteria
            Partner with engineering on sprint delivery
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertGreaterEqual(len(sections["responsibilities"]), 2)
        self.assertTrue(any("product ownership" in r.lower() for r in sections["required"]))


class TestThinStubSkips(unittest.TestCase):
    """Netradyne-class career-page stub: thin + empty buckets must Skip, not
    Tier 2 PASS with extraction_empty."""

    def test_thin_empty_stub_is_skip(self):
        jd = textwrap.dedent(
            """
            Careers at ExampleCo

            Thank you for your interest in ExampleCo.
            Want to protect drivers and reduce costs?
            Book Demo
            Book Demo
            """
        )
        result = _build(jd)
        self.assertTrue(result["thin_jd"])
        self.assertEqual(result["tier"], "Skip")
        self.assertEqual(result["decision"], "SKIP")
        self.assertIn("thin", (result.get("skip_reason") or "").lower())


class TestMixedBucketRecovery(unittest.TestCase):
    """When required is empty but responsibilities holds a mixed duty+qual list
    (SDL / Shazam / Camunda-class), recover quals into required/preferred."""

    def test_sdl_style_mixed_position_splits_quals(self):
        jd = textwrap.dedent(
            """
            Product Manager

            The Position

            Own the product roadmap and prioritize based on customer needs
            Run sprint planning, standups, retros, and backlog grooming
            Write clear specs, user stories, and acceptance criteria
            Work closely with engineering leads to keep velocity high
            5+ years in product management, with real experience running agile teams
            A track record of shipping software and owning outcomes, not just outputs
            Strong opinions about AI and how it's changing product work
            Bonus: experience in GovTech, SaaS, or selling to non-technical buyers
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["responsibilities"]), 3)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertTrue(any("5+ years" in r for r in sections["required"]))
        self.assertTrue(any("track record" in r.lower() for r in sections["required"]))
        self.assertTrue(any("govtech" in p.lower() for p in sections["preferred"]))
        resp_blob = " | ".join(sections["responsibilities"]).lower()
        self.assertNotIn("5+ years", resp_blob)
        self.assertTrue(any("own the product roadmap" in r.lower() for r in sections["responsibilities"]))

    def test_does_not_split_when_required_already_populated(self):
        """Well-structured JDs must not have responsibilities reclassified."""
        jd = textwrap.dedent(
            """
            What you'll do
            - Own the product roadmap for the platform
            - Partner with engineering on delivery
            - 5+ years of experience mentoring junior PMs as a stretch duty phrasing

            What we're looking for
            - 3-5 years of product management experience in B2B SaaS
            - Strong agile and backlog grooming skills
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["required"]), 2)
        # The stretch "5+ years" line under responsibilities must stay there —
        # recovery only fires when required is empty.
        self.assertTrue(
            any("mentoring" in r.lower() for r in sections["responsibilities"]),
            "must not move duty-section lines when required already has items",
        )


class TestMidJdQualsHeaders(unittest.TestCase):
    def test_what_do_you_need_opens_required(self):
        jd = textwrap.dedent(
            """
            WHAT WILL YOU BE DOING?
            Translate product initiatives into clear user stories

            WHAT DO YOU NEED?
            5+ years of product ownership experience in B2B SaaS
            Strong agile backlog and user story writing skills
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertTrue(any("product ownership" in r.lower() for r in sections["required"]))

    def test_ideal_candidate_profile_opens_required(self):
        jd = textwrap.dedent(
            """
            What you'll do
            Own the accounting platform integrations across customers

            Ideal Candidate Profile
            5 years of product management experience, ideally in B2B SaaS
            Exceptional soft skills and stakeholder navigation
            """
        )
        sections = _extract_sections(jd)
        self.assertGreaterEqual(len(sections["required"]), 2)
        self.assertTrue(any("5 years of product management" in r.lower() for r in sections["required"]))


class TestNoiseHeadersAndFluff(unittest.TestCase):
    def test_realtime_what_sets_you_apart_not_a_gap(self):
        jd = textwrap.dedent(
            """
            WHAT DO YOU NEED?
            5+ years of product ownership experience in B2B SaaS
            Strong agile backlog skills

            WHAT SETS YOU APART?
            Experience working in regulated product environments

            WHAT IS IN IT FOR YOU?
            Competitive salary and benefits
            """
        )
        sections = _extract_sections(jd)
        blob = " | ".join(sections["required"] + sections["preferred"] + sections["responsibilities"]).lower()
        self.assertNotIn("what sets you apart", blob)
        self.assertNotIn("what is in it for you", blob)
        self.assertTrue(any("regulated" in r.lower() for r in sections["required"] + sections["preferred"]))

    def test_acushnet_benefits_cta_not_in_resp(self):
        jd = textwrap.dedent(
            """
            The Position
            Own the product roadmap for golf equipment lines
            5+ years of product management experience

            Our Commitment to You
            Additionally, you'll enjoy perks like pet insurance, legal planning, education assistance
            Ready to Make an Impact?
            """
        )
        sections = _extract_sections(jd)
        resp_blob = " | ".join(sections["responsibilities"]).lower()
        for junk in ("commitment to you", "pet insurance", "ready to make an impact"):
            self.assertNotIn(junk, resp_blob, f"benefits/CTA leaked into resp: {junk}")

    def test_dependable_fluff_dropped(self):
        from build_stage0_fit_gate import _is_boilerplate_item

        self.assertTrue(
            _is_boilerplate_item(
                "Dependable, accountable, and able to work effectively in dynamic, fast-paced settings."
            )
        )


class TestUndergraduateSatisfied(unittest.TestCase):
    def test_undergraduate_degree_not_soft_gap(self):
        from build_stage0_fit_gate import classify_gaps, _load_anchor_vocab

        _, _, gaps = classify_gaps(
            ["Undergraduate degree", "3+ years of product management experience in B2B SaaS"],
            [],
            vocab=_load_anchor_vocab(),
        )
        items = [g["item"].lower() for g in gaps]
        self.assertFalse(any("undergraduate" in i for i in items))


class TestFamiliarityHardToolIsSoft(unittest.TestCase):
    def test_familiarity_with_docker_is_soft_not_skip(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Familiarity with technologies such as Kubernetes, Docker, and cloud services (AWS, GCP, Azure)
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip")
        hard = [g for g in result["flagged_gaps"] if g.get("gap_class") == "HARD"]
        soft = [g for g in result["flagged_gaps"] if g.get("gap_class") == "SOFT"]
        self.assertEqual(hard, [], f"familiarity hedge must not HARD-skip: {hard}")
        self.assertTrue(any("docker" in g["item"].lower() for g in soft))

    def test_deep_familiarity_snowflake_still_hard(self):
        """Intensified familiarity stays HARD — existing Snowflake Skip contract."""
        result = _build(_SNOWFLAKE_JD)
        self.assertEqual(result["tier"], "Skip")
        self.assertTrue(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

    def test_strong_plus_after_familiarity_does_not_harden(self):
        """Trailing 'strong plus' must not cancel a plain Familiarity-with hedge.

        Seed Health (2026-08-11): compound analytics line ended with
        'Familiarity with … (e.g., Amplitude) is a strong plus' and was HARD-Skipped
        because 'strong' matched the intensifier anywhere in the line.
        """
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - You're analytically fluent with cohort analysis and funnel metrics. Familiarity with SQL and product analytics tools (e.g., Amplitude) is a strong plus
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip", result.get("skip_reason") or result.get("notes"))
        hard = [g for g in result["flagged_gaps"] if g.get("gap_class") == "HARD"]
        self.assertEqual(hard, [], hard)
        soft = [g for g in result["flagged_gaps"] if g.get("gap_class") == "SOFT"]
        self.assertTrue(any("amplitude" in g["item"].lower() for g in soft))


class TestSkillsCatalogDoesNotFalseAnchorOffice(unittest.TestCase):
    """Invariant: skill-catalog product phrases must not word-split into false anchors.

    skills_catalog has 'Microsoft Teams' and 'Google Suite'. Whitespace-splitting those
    into 'microsoft' / 'suite' previously marked 'Microsoft Office Suite' as grounded
    even though Office is not in Jason's verified tools — Stage 1 then fail-closed with
    an unmapped required item (Central Bank, 2026-08-11).
    """

    def test_microsoft_office_suite_is_soft_gap_not_false_anchor(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Strong command of Microsoft Office Suite.
            """
        )
        result = _build(jd)
        office_rows = [
            r for r in result["required"]
            if "microsoft office" in r["item"].lower()
        ]
        self.assertEqual(len(office_rows), 1, result["required"])
        row = office_rows[0]
        self.assertTrue(row["gap"], f"expected gap, got anchor={row.get('anchor')!r}")
        self.assertEqual(row["gap_class"], "SOFT")
        self.assertNotIn("microsoft", (row.get("anchor") or "").lower())
        self.assertNotIn("suite", (row.get("anchor") or "").lower())

    def test_microsoft_teams_full_phrase_still_anchors(self):
        """Full catalog phrase 'Microsoft Teams' must still count as an anchor."""
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Experience collaborating in Microsoft Teams with engineering partners
            """
        )
        result = _build(jd)
        teams_rows = [
            r for r in result["required"]
            if "microsoft teams" in r["item"].lower()
        ]
        self.assertEqual(len(teams_rows), 1, result["required"])
        self.assertFalse(teams_rows[0]["gap"], teams_rows[0])


class TestBoilerplateAndGenericAnchorGuards(unittest.TestCase):
    """2026-08-11 corpus: LeafLink teams-false-anchor + Common Room Zoom boilerplate."""

    def test_navigate_ambiguity_not_false_anchored_by_teams(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Ability to navigate ambiguity and drive clarity across teams
            """
        )
        result = _build(jd)
        # Filtered as soft-skill fluff boilerplate, or at worst SOFT with no teams anchor.
        amb = [
            r for r in result["required"]
            if "ambiguity" in r["item"].lower()
        ]
        if amb:
            self.assertTrue(amb[0]["gap"], amb[0])
            self.assertNotIn("teams", (amb[0].get("anchor") or "").lower())
        # Preferred outcome: stripped entirely as boilerplate.
        self.assertTrue(
            len(amb) == 0
            or amb[0]["gap"],
            f"ambiguity line should be filtered or soft-gapped: {result['required']}",
        )

    def test_zoom_apply_window_and_tdc_filtered(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - In addition to the base salary and/or OTE listed Zoom has a Total Direct Compensation philosophy that takes into account multiple factors.
            - At Zoom, we offer a window of at least 5 days for you to apply because we believe in giving you every opportunity to apply.
            """
        )
        result = _build(jd)
        leaked = [
            r["item"] for r in result["required"]
            if "total direct compensation" in r["item"].lower()
            or "window of at least" in r["item"].lower()
            or "ote listed" in r["item"].lower()
        ]
        self.assertEqual(leaked, [], f"compensation/apply-window boilerplate leaked: {leaked}")


class TestSharedBlockedTools(unittest.TestCase):
    def test_amplitude_is_hard_blocked_at_stage0(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Hands-on experience with Amplitude for product analytics
            """
        )
        result = _build(jd)
        self.assertEqual(result["tier"], "Skip")
        self.assertTrue(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

    def test_or_similar_alternative_satisfied_by_anchored_tool(self):
        """"(Pendo, Amplitude, Mixpanel, or similar)" is an alternatives list --
        Jason's verified Pendo experience (skills_catalog.json) satisfies it even
        though Amplitude/Mixpanel are individually hard-blocked. Real miss found
        2026-08-13 on Decisiv/pop_up_talent."""
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Experience defining and tracking outcome-based success metrics, using product analytics tools (Pendo, Amplitude, Mixpanel, or similar) to measure adoption and guide iteration
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip")
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

    def test_amplitude_still_hard_blocked_without_anchored_alternative(self):
        """Same alternatives phrasing, but no anchored tool present -- must
        still HARD-skip (guards against over-broadening the fix above)."""
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Hands-on experience with product analytics and experimentation
              tools such as Amplitude, Mixpanel, Looker, Mode, Optimizely, or
              Statsig
            """
        )
        result = _build(jd)
        self.assertEqual(result["tier"], "Skip")
        self.assertTrue(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

    def test_linter_and_stage0_share_blocked_source(self):
        import re

        from blocked_tools import HARD_BLOCKED_TOOLS, hard_blocked_tools_lint_alternation
        from build_stage0_fit_gate import _HARD_BLOCKED_TOOLS as stage0_tools

        self.assertIs(stage0_tools, HARD_BLOCKED_TOOLS)
        alt = hard_blocked_tools_lint_alternation()
        pat = re.compile(rf"\b({alt})\b")
        for sample in ("Amplitude", "Procore", "Smartsheet", "Power BI", "Monday.com"):
            self.assertIsNotNone(pat.search(sample), sample)


class TestEmptyRequiredNotTier1(unittest.TestCase):
    def test_preferred_only_is_tier2(self):
        jd = textwrap.dedent(
            """
            Preferred qualifications
            - Experience with Jira and Confluence
            - Prior work in integration-heavy platforms
            - Strong written communication skills
            """
        )
        result = _build(jd)
        self.assertEqual(len(result["required"]), 0)
        self.assertGreater(len(result["preferred"]), 0)
        self.assertEqual(result["tier"], "Tier 2")
        self.assertEqual(result["decision"], "PASS")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
