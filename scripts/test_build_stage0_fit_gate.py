#!/usr/bin/env python3
"""
Tests for build_stage0_fit_gate.py and stage0_prefs_gate.py — no real DB, no LLM.

All fixture JDs are inline strings. DB gate is mocked to return "clear" so tests
don't need a real SQLite file for non-DB cases. Tests that exercise DB logic pass
their own in-memory connection via the stage0_db_gate._conn kwarg.

Run with:
    python -m unittest scripts.test_stage0_db_gate scripts.test_build_stage0_fit_gate -q
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 2026-08-17: build_stage0_fit_gate() now tries an LLM call by default for
# section extraction (see that module's docstring). This suite's own
# docstring promises "no real DB, no LLM" -- force the deterministic regex
# path for every test here so the suite stays fast, offline, and
# network-free. Scoring is mocked at evidence_scale.classify_requirement
# (Story 2.7, setUpModule below). The LLM extract path itself is covered
# separately with a mocked call_llm, not real network I/O -- see
# TestSectionExtractionLLM below.
os.environ["STAGE0_SECTION_MODE"] = "deterministic"

from build_stage0_fit_gate import (
    STAGE0_EXTRACT_MODEL,
    Stage0ExtractError,
    _parse_url_and_jd,
    _detect_thin_jd,
    _detect_stage_signal,
    _detect_po_solo_backlog_signal,
    _extract_sections,
    classify_gaps,
    build_stage0_fit_gate,
    screen_responsibilities_for_exclusion,
    _cap_requirement_bucket,
    extract_salary_range,
    _load_anchor_vocab,
    _has_extraction_override,
    batch_report,
    _BACHELORS_SATISFIED_RE,
    _HIGHER_DEGREE_MANDATORY_RE,
    _YEARS_EXPERIENCE_LEADIN_RE,
)
from evidence_scale import EvidenceJudgment
from stage0_prefs_gate import (
    run_prefs_gate,
    _check_people_management,
    _check_revenue_billing,
    _check_ai_ml_ownership,
    _check_travel,
    _check_zero_to_one,
)

# ---------------------------------------------------------------------------
# Offline classify_requirement (CR-093 Story 2.7)
#
# Live accuracy is data/fit_rubric_golden_set.json. This stub only has to
# make THIS file's fixtures produce the evidence-scale contract so
# classify_gaps / Step 5.5 wiring tests run without Ollama: tools never
# HARD-gate, degree/domain/role_exclusion can, undergraduate is satisfied,
# and a default PM line looks like documented evidence.
# ---------------------------------------------------------------------------

_KNOWN_EVIDENCE = (
    "product management",
    "product ownership",
    "product owner",
    "agile",
    "scrum",
    "roadmap",
    "backlog",
    "stakeholder",
    "cross-functional",
    "jira",
    "confluence",
    "salesforce",
    "pendo",
    "amplitude",
    "sql",
    "microsoft teams",
    "communication",
    "prioritization",
    "user stor",
    "sprint",
    "b2b saas",
    "analytics",
    "cohort",
    "funnel",
    "engineering",
    "integration-heavy",
    "written communication",
)

_UNKNOWN_TOOLS = (
    "fhir",
    "hl7",
    "snowflake",
    "guidewire",
    "servicemesh",
    "docker",
    "kubernetes",
    "microsoft office",
    "braze",
    "klaviyo",
    "cmms",
    "looker",
    "mixpanel",
    "optimizely",
    "statsig",
    "shopify",
    "cerner",
    "dbt",
)

_REGULATED_DOMAIN = (
    "payroll tax",
    "healthcare",
    "clinical",
    "banking",
    "insurance",
    "highly regulated",
)

_DOMAIN_HEDGE_RE = re.compile(r"\b(ideally|preferred|a plus)\b", re.I)

_CLASSIFY_PATCHER = None


def _offline_classify_requirement(
    item: str,
    work_exp: str,
    *,
    is_required: bool = True,
    company: str = "",
    internal_terms: list[str] | None = None,
    **_kwargs,
) -> EvidenceJudgment:
    del work_exp, company, internal_terms
    text = (item or "").lower()

    if is_required and _HIGHER_DEGREE_MANDATORY_RE.search(text):
        return EvidenceJudgment(
            item=item,
            gate="HARD",
            gap_source="degree",
            evidence_level=0,
            confidence="high",
            reasoning="mandatory advanced degree, not satisfied",
            is_required=True,
        )

    has_years = bool(_YEARS_EXPERIENCE_LEADIN_RE.match((item or "").strip()))
    has_domain = any(d in text for d in _REGULATED_DOMAIN)
    has_pm_alt = "product management" in text or "product ownership" in text
    if (
        is_required
        and has_years
        and has_domain
        and not has_pm_alt
        and not _DOMAIN_HEDGE_RE.search(text)
    ):
        return EvidenceJudgment(
            item=item,
            gate="HARD",
            gap_source="domain",
            evidence_level=0,
            confidence="high",
            reasoning="named regulated domain with years, no PM alternative",
            is_required=True,
        )

    if _BACHELORS_SATISFIED_RE.search(text) and not _HIGHER_DEGREE_MANDATORY_RE.search(text):
        return EvidenceJudgment(
            item=item,
            gate="NONE",
            gap_source=None,
            evidence_level=4,
            confidence="high",
            reasoning="undergraduate/bachelor's already satisfied",
            is_required=is_required,
        )

    has_known_product = any(
        p in text
        for p in (
            "pendo",
            "amplitude",
            "salesforce",
            "jira",
            "confluence",
            "microsoft teams",
        )
    )
    unknown_tool = next((t for t in _UNKNOWN_TOOLS if t in text), None)
    if unknown_tool and not has_known_product:
        return EvidenceJudgment(
            item=item,
            gate="NONE",
            gap_source="tool",
            evidence_level=1,
            confidence="high",
            reasoning=f"named tool {unknown_tool} has no documented evidence",
            is_required=is_required,
        )

    if has_domain and not has_pm_alt:
        return EvidenceJudgment(
            item=item,
            gate="NONE",
            gap_source="domain",
            evidence_level=1,
            confidence="high",
            reasoning="named domain without documented evidence",
            is_required=is_required,
        )

    if any(k in text for k in _KNOWN_EVIDENCE):
        return EvidenceJudgment(
            item=item,
            gate="NONE",
            gap_source=None,
            evidence_level=4,
            confidence="high",
            reasoning="documented product-management evidence",
            is_required=is_required,
        )

    return EvidenceJudgment(
        item=item,
        gate="NONE",
        gap_source=None,
        evidence_level=4,
        confidence="high",
        reasoning="default documented evidence for generic PM lines",
        is_required=is_required,
    )


def setUpModule():
    global _CLASSIFY_PATCHER
    _CLASSIFY_PATCHER = patch(
        "evidence_scale.classify_requirement",
        side_effect=_offline_classify_requirement,
    )
    _CLASSIFY_PATCHER.start()


def tearDownModule():
    global _CLASSIFY_PATCHER
    if _CLASSIFY_PATCHER is not None:
        _CLASSIFY_PATCHER.stop()
        _CLASSIFY_PATCHER = None


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

# A PO JD reading as solo backlog ownership -- BRD/waterfall, no engineering
# collaboration language.
_PO_SOLO_JD = textwrap.dedent("""
    Product Owner

    You will own the backlog and author the business requirements document
    for each release, following our waterfall delivery process.

    Requirements
    - 3+ years of product ownership experience
    - Strong agile and requirements gathering and documentation skills
    - Experience writing detailed functional specification documents
""").strip()

# A PO JD that is collaborative with engineering -- should NOT flag.
_PO_COLLAB_JD = textwrap.dedent("""
    Product Owner

    You will own the backlog and write the business requirements document
    for each release, but you'll work closely with engineering throughout
    to shape and refine every ticket.

    Requirements
    - 3+ years of product ownership experience
    - Strong agile background
    - Comfortable partnering with engineering on requirements
""").strip()

# A non-PO PM JD with the same BRD/waterfall language -- title gate should
# keep this from flagging (the signal is scoped to PO postings).
_PM_WATERFALL_JD = textwrap.dedent("""
    Senior Product Manager

    You will author the business requirements document for each release,
    following our waterfall delivery process.

    Requirements
    - 5+ years of product management experience
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


class TestSalaryRangeExtraction(unittest.TestCase):
    """2026-08-28, Jason-supplied: best-effort salary capture for jobs.salary_range."""

    def test_dollar_range_with_commas_extracted(self):
        jd = "The base salary range for this role is $120,000 - $150,000 annually."
        self.assertEqual(extract_salary_range(jd), "$120,000 - $150,000 annually")

    def test_k_shorthand_range_extracted(self):
        jd = "Compensation: $120K-$150K depending on experience."
        self.assertEqual(extract_salary_range(jd), "$120K-$150K")

    def test_em_dash_and_en_dash_ranges_extracted(self):
        self.assertEqual(extract_salary_range("Pay: $90,000—$110,000."), "$90,000—$110,000")
        self.assertEqual(extract_salary_range("Pay: $90,000–$110,000."), "$90,000–$110,000")

    def test_no_dollar_sign_returns_none(self):
        # Deliberately not handled -- see the function's own docstring.
        self.assertIsNone(extract_salary_range("Salary: 120000 to 150000 USD."))

    def test_no_salary_mention_returns_none(self):
        self.assertIsNone(extract_salary_range(_CLEAN_PM_JD))

    def test_empty_jd_returns_none(self):
        self.assertIsNone(extract_salary_range(""))
        self.assertIsNone(extract_salary_range(None))


class TestPreferenceRejectShortCircuit(unittest.TestCase):
    """Deterministic exclusions must not depend on any model being available."""

    def test_prefs_reject_skips_before_extraction(self):
        from unittest.mock import patch

        rejected = {
            "passed": False,
            "rejects": [{
                "code": "exclusion_zone_zero_to_one",
                "reason": "Role requires zero-to-one ownership.",
            }],
            "flags": [],
        }
        with patch("build_stage0_fit_gate.run_prefs_gate_safe", return_value=rejected):
            with patch("build_stage0_fit_gate._extract_sections_llm") as extractor:
                result = _build(_CLEAN_PM_JD)
        self.assertEqual(result["decision"], "SKIP")
        self.assertEqual(result["tier"], "Skip")
        self.assertEqual(result["skip_reason_code"], "exclusion_zone_zero_to_one")
        self.assertEqual(result["extraction_source"], "not_run")
        extractor.assert_not_called()

    def test_batch_mode_keeps_final_model_until_next_role_boundary(self):
        with patch.dict(os.environ, {"STAGE0_BATCH_KEEP_ALIVE": "1"}):
            with patch("build_stage0_fit_gate._release_stage0_vram") as release:
                _build(_CLEAN_PM_JD)
        self.assertEqual(
            [call.args[0] for call in release.call_args_list],
            ["before-extract"],
        )

    def test_single_role_mode_still_releases_models(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STAGE0_BATCH_KEEP_ALIVE", None)
            with patch("build_stage0_fit_gate._release_stage0_vram") as release:
                _build(_CLEAN_PM_JD)
        self.assertEqual(
            [call.args[0] for call in release.call_args_list],
            ["before-extract", "after-stage0"],
        )

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
        # Same word count but with extractable qualification-shaped requireds is not thin.
        self.assertFalse(
            _detect_thin_jd(
                words,
                required_items=[
                    "5+ years of product management experience in B2B SaaS",
                    "Bachelor's degree in Computer Science or equivalent experience",
                ],
            )
        )

    def test_culture_sentences_in_required_do_not_clear_thin(self):
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
        self.assertTrue(
            _detect_thin_jd(
                words,
                required_items=[
                    "We work to enable developers to have the most productive results of their career",
                    "In total, we are 700+ ebankers spread across the world",
                ],
            )
        )


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
# Test: requirement-bucket cap (2026-08-28, Jason-supplied -- the
# Schellman-class outlier, 17 real required items vs. 7-12 typical)
# ---------------------------------------------------------------------------

class TestRequirementBucketCap(unittest.TestCase):
    def test_bucket_at_or_under_limit_is_untouched(self):
        items = [f"Requirement number {i} with 5 years of something." for i in range(12)]
        kept, dropped = _cap_requirement_bucket(items)
        self.assertEqual(kept, items)
        self.assertEqual(dropped, 0)

    def test_over_limit_bucket_is_capped_and_reports_dropped_count(self):
        items = [f"Requirement number {i} with 5 years of something specific." for i in range(17)]
        kept, dropped = _cap_requirement_bucket(items)
        self.assertEqual(len(kept), 12)
        self.assertEqual(dropped, 5)

    def test_generic_soft_skill_lines_are_dropped_before_specific_ones(self):
        specific = [f"Own the {i} roadmap with 5+ years of B2B SaaS product experience." for i in range(12)]
        generic = ["Strong communication skills.", "Excellent interpersonal skills."]
        kept, dropped = _cap_requirement_bucket(specific + generic)
        self.assertEqual(dropped, 2)
        self.assertTrue(all(g not in kept for g in generic))

    def test_kept_items_preserve_original_jd_order(self):
        items = [f"Item {i} with a concrete number like {i}." for i in range(15)]
        kept, _ = _cap_requirement_bucket(items)
        # Whatever survives must appear in the same relative order it was extracted in.
        self.assertEqual(kept, [item for item in items if item in kept])

    def test_custom_limit_is_respected(self):
        items = [f"Item {i} with 3 years experience." for i in range(10)]
        kept, dropped = _cap_requirement_bucket(items, limit=5)
        self.assertEqual(len(kept), 5)
        self.assertEqual(dropped, 5)


# ---------------------------------------------------------------------------
# Test: Gap classification
# ---------------------------------------------------------------------------

class TestGapClassification(unittest.TestCase):
    """Wiring tests against the offline classify_requirement stub (Story 2.7).
    Named tools are SOFT evidence gaps, never HARD (spec Sec. 9). Live
    accuracy belongs in data/fit_rubric_golden_set.json."""

    def setUp(self):
        self.vocab = _load_anchor_vocab()

    def test_fhir_is_soft_tool_gap_not_hard(self):
        reqs = ["Deep expertise in FHIR and HL7 healthcare data exchange standards"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(classified[0]["gap"], "FHIR should be flagged as a gap")
        self.assertEqual(classified[0]["gap_class"], "SOFT")
        self.assertTrue(any(g.get("gap_class") == "SOFT" for g in flagged))

    def test_agile_is_not_a_gap(self):
        reqs = ["3+ years of product management experience in an agile environment"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertFalse(classified[0]["gap"], "agile/PM exp should find anchors")

    def test_snowflake_is_soft_tool_gap_not_hard(self):
        reqs = ["Deep familiarity with Snowflake data warehouse"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(classified[0]["gap"])
        self.assertEqual(classified[0]["gap_class"], "SOFT")

    def test_domain_gap_is_soft(self):
        # Healthcare domain knowledge (not a named hard tool) → SOFT
        reqs = ["Prior experience in the healthcare industry or regulated environment"]
        classified, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(classified[0]["gap"])
        self.assertEqual(classified[0]["gap_class"], "SOFT")

    def test_preferred_item_has_handling(self):
        prefs = ["CMMS experience preferred"]
        _, classified_pref, _ = classify_gaps([], prefs, vocab=self.vocab)
        self.assertIn("handling", classified_pref[0])

    def test_flagged_gaps_populated_as_soft_for_tools(self):
        reqs = ["FHIR expertise required", "3+ years agile PM experience"]
        _, _, flagged = classify_gaps(reqs, [], vocab=self.vocab)
        self.assertTrue(any(g.get("gap_class") == "SOFT" for g in flagged))
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in flagged))


# ---------------------------------------------------------------------------
# Test: PO solo-backlog-ownership signal (2026-08-18)
# ---------------------------------------------------------------------------

class TestPoSoloBacklogSignal(unittest.TestCase):
    def test_solo_po_jd_flagged_soft(self):
        signal = _detect_po_solo_backlog_signal("Product Owner", _PO_SOLO_JD, _PREFS_MINIMAL)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["gap_class"], "SOFT")
        self.assertIn("po_solo_backlog_signal", signal["bridge"])

    def test_collaborative_po_jd_not_flagged(self):
        signal = _detect_po_solo_backlog_signal("Product Owner", _PO_COLLAB_JD, _PREFS_MINIMAL)
        self.assertIsNone(signal)

    def test_non_po_title_not_flagged(self):
        # Same BRD/waterfall language, but not a PO-titled posting -- scoped to PO only.
        signal = _detect_po_solo_backlog_signal(
            "Senior Product Manager", _PM_WATERFALL_JD, _PREFS_MINIMAL
        )
        self.assertIsNone(signal)

    def test_falls_back_to_defaults_without_prefs_keys(self):
        # _PREFS_MINIMAL carries no po_solo_backlog_flags/mitigators keys --
        # detection must still work off the module defaults.
        signal = _detect_po_solo_backlog_signal("Product Owner", _PO_SOLO_JD, {})
        self.assertIsNotNone(signal)

    def test_solo_po_jd_routes_to_tier2_not_skip(self):
        result = _build(_PO_SOLO_JD)
        self.assertNotEqual(result["tier"], "Skip")
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(
            any("po_solo_backlog_signal" in g.get("bridge", "") for g in result["flagged_gaps"])
        )

    def test_collaborative_po_jd_not_forced_to_tier2_by_signal(self):
        result = _build(_PO_COLLAB_JD)
        self.assertFalse(
            any("po_solo_backlog_signal" in g.get("bridge", "") for g in result["flagged_gaps"])
        )


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
# Test: FHIR JD — tool gap is SOFT, must not Skip
# ---------------------------------------------------------------------------

class TestFhirJd(unittest.TestCase):
    def test_fhir_does_not_skip(self):
        """Named tools never hard-gate (spec Sec. 9). Score can still land
        Tier 1 or Tier 2 depending on the other required lines."""
        result = _build(_FHIR_JD)
        self.assertNotEqual(result["tier"], "Skip")
        self.assertEqual(result["decision"], "PASS")

    def test_fhir_flagged_as_soft_not_hard(self):
        result = _build(_FHIR_JD)
        fhir_rows = [
            r for r in result["required"] if "fhir" in r["item"].lower()
        ]
        self.assertEqual(len(fhir_rows), 1, result["required"])
        self.assertEqual(fhir_rows[0]["gap_class"], "SOFT")
        hard_gaps = [g for g in result["flagged_gaps"] if g.get("gap_class") == "HARD"]
        self.assertEqual(hard_gaps, [], hard_gaps)


# ---------------------------------------------------------------------------
# Test: Snowflake JD — tool gap is SOFT, must not Skip
# ---------------------------------------------------------------------------

class TestSnowflakeJd(unittest.TestCase):
    def test_snowflake_does_not_skip(self):
        result = _build(_SNOWFLAKE_JD)
        self.assertNotEqual(result["tier"], "Skip")
        snow = [r for r in result["required"] if "snowflake" in r["item"].lower()]
        self.assertEqual(len(snow), 1, result["required"])
        self.assertEqual(snow[0]["gap_class"], "SOFT")
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))


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
# Test: responsibilities-bucket exclusion screen escalates every line
# (2026-08-28, Jason-supplied -- CR-096's "still not caught automatically"
# Harbor Compliance finding, resolved by removing the signal-word pre-filter
# rather than growing its word list).
# ---------------------------------------------------------------------------

class TestResponsibilitiesFullJudgmentEscalation(unittest.TestCase):
    def test_line_with_no_old_signal_words_still_gets_classified(self):
        """A responsibilities line matching none of the old
        _RESPONSIBILITY_EXCLUSION_SIGNAL_RE categories (no "from scratch",
        no P&L, no team-of-N, ...) must still reach classify_requirement --
        that pre-filter no longer gates whether a line gets real judgment.
        """
        line = "Own the outcomes for a brand-new product area end to end."
        with patch("evidence_scale.classify_requirement") as mock_classify:
            mock_classify.return_value = EvidenceJudgment(
                item=line,
                gate="NONE",
                gap_source=None,
                evidence_level=4,
                confidence="high",
                reasoning="documented product-management evidence",
                is_required=True,
            )
            screen_responsibilities_for_exclusion(
                [line], work_exp="some work experience", company="Test Co",
            )
        mock_classify.assert_called_once()
        self.assertEqual(mock_classify.call_args[0][0], line)

    def test_deterministic_0to1_line_never_pays_for_a_classify_call(self):
        """The free zero-cost regex fast path still short-circuits before
        any LLM call for the one unambiguous, high-confidence phrasing."""
        line = "You will own the zero to one build of our new platform."
        with patch("evidence_scale.classify_requirement") as mock_classify:
            hits = screen_responsibilities_for_exclusion(
                [line], work_exp="some work experience", company="Test Co",
            )
        mock_classify.assert_not_called()
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["gap_source"], "role_exclusion")

    def test_hard_gate_from_full_judgment_is_returned_as_a_hit(self):
        line = "Manage a direct team of engineers and own their growth plans."
        with patch("evidence_scale.classify_requirement") as mock_classify:
            mock_classify.return_value = EvidenceJudgment(
                item=line,
                gate="HARD",
                gap_source="role_exclusion",
                evidence_level=0,
                confidence="high",
                reasoning="people-management ownership, not in scope",
                is_required=True,
            )
            hits = screen_responsibilities_for_exclusion(
                [line], work_exp="some work experience", company="Test Co",
            )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["gap_class"], "HARD")


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
        # Score-driven Step 5.5 can still land Tier 1; the reapply signal
        # must remain on the output either way.
        self.assertNotEqual(result["tier"], "Skip")
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

    def test_deep_familiarity_snowflake_is_soft_not_hard(self):
        """Intensified familiarity does not HARD-gate a named tool (spec Sec. 9)."""
        result = _build(_SNOWFLAKE_JD)
        self.assertNotEqual(result["tier"], "Skip")
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))
        snow = [r for r in result["required"] if "snowflake" in r["item"].lower()]
        self.assertEqual(snow[0]["gap_class"], "SOFT")

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


@unittest.skip(
    "CR-093: _split_compound_item was removed -- an LLM judging a full "
    "requirement line directly handles compound-clause reasoning natively, "
    "no regex pre-splitting needed. The hard-blocked-tool test also asserts "
    "gap_class=='HARD' for a tool-only line, which is now definitionally "
    "wrong (spec Sec. 9: tools never gate). Real replacement coverage "
    "belongs in data/fit_rubric_golden_set.json. See CR-093 Epic 2 Story 2.7."
)
class TestCompoundClauseSplitting(unittest.TestCase):
    """CR-092 (2026-08-15): mechanizes generate-submission/SKILL.md's
    "Humana finding" (2026-07-21) -- a compound requirement line joined by
    commas must be split into sub-concepts before anchor-checking, not
    evaluated as one bag-of-words unit. That rule was prose-only for three
    weeks; a generic word matching in ANY sub-clause previously cleared the
    WHOLE line, masking a real gap in a different sub-clause."""

    def test_three_item_list_flags_the_unanchored_clause(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Experience managing product zoning matrices, intake processes, and prioritization frameworks.
            """
        )
        result = _build(jd)
        rows = [r for r in result["required"] if "zoning matrices" in r["item"].lower()]
        self.assertEqual(len(rows), 1, result["required"])
        row = rows[0]
        self.assertTrue(row["gap"], f"expected gap, got anchor={row.get('anchor')!r}")
        self.assertIn("unanchored sub-clause", row["anchor"])

    def test_three_item_list_all_anchored_stays_clean(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Experience with roadmap planning, backlog prioritization, and cross-functional stakeholder alignment.
            """
        )
        result = _build(jd)
        rows = [r for r in result["required"] if "roadmap planning" in r["item"].lower()]
        self.assertEqual(len(rows), 1, result["required"])
        row = rows[0]
        self.assertFalse(row["gap"], f"expected clean, got anchor={row.get('anchor')!r}")

    def test_single_comma_not_treated_as_list(self):
        """One comma is too ambiguous to safely split (appositive, trailing
        clause, etc.) -- _split_compound_item requires 2+ commas."""
        from build_stage0_fit_gate import _split_compound_item
        item = "Experience with SQL, including complex joins"
        self.assertEqual(_split_compound_item(item), [item])

    def test_no_comma_not_treated_as_list(self):
        from build_stage0_fit_gate import _split_compound_item
        item = "Experience with product management and delivery"
        self.assertEqual(_split_compound_item(item), [item])

    def test_hard_blocked_tool_anywhere_in_compound_line_still_hard_skips(self):
        """A hard-blocked tool inside a compound line must still hard-skip
        the whole line regardless of what else is in it -- this check runs
        on the whole line BEFORE the compound split, unchanged from before."""
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Experience with Snowflake, dbt, and data pipeline orchestration.
            """
        )
        result = _build(jd)
        rows = [r for r in result["required"] if "snowflake" in r["item"].lower()]
        self.assertEqual(len(rows), 1, result["required"])
        row = rows[0]
        self.assertEqual(row["gap_class"], "HARD")


class TestPreferredHardGapTriggersSkip(unittest.TestCase):
    """CR-092 follow-up (2026-08-15, Jason-supplied, real miss): a hard-
    blocked named tool sitting in the JD's Preferred section, not Required,
    must still be escalated into flagged_gaps -- confirmed real on Mercury
    Insurance, whose Guidewire requirement was in "Preferred" and reached
    Tier 2 PASS even after being correctly classified HARD, because
    classify_gaps() only ever escalated domain_soft SOFT preferred items
    into flagged_gaps, never HARD ones.

    2026-08-19: a tool-only HARD gap no longer forces an outright Skip
    (only a credential/degree HARD gap does) -- so this now asserts the
    preferred Guidewire line is still classified as a gap, not that it Skips."""

    def test_hard_blocked_tool_in_preferred_section_is_flagged_not_skipped(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 3+ years of product management experience

            Preferred
            - 1+ years of advanced knowledge of Guidewire product models specifically working on Guidewire Policy Center, with knowledge of its function in underwriting/sales workflows, policy rating, rules engine.
            """
        )
        result = _build(jd)
        self.assertEqual(result["decision"], "PASS")
        self.assertNotEqual(result["tier"], "Skip")
        gw = [r for r in result["preferred"] if "guidewire" in r["item"].lower()]
        self.assertEqual(len(gw), 1, result["preferred"])
        self.assertTrue(gw[0]["gap"])
        self.assertEqual(gw[0]["gap_class"], "SOFT")
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

    def test_domain_soft_preferred_gap_still_only_soft_pass(self):
        """Regression guard: an ordinary domain-soft preferred gap (not a
        hard-blocked tool) must NOT start Skipping JDs -- only gap_class ==
        "HARD" escalates; this must stay Tier 2, not Skip."""
        jd = textwrap.dedent(
            """
            Requirements
            - 3+ years of product management experience in B2B SaaS

            Preferred
            - Experience in healthcare or clinical settings preferred.
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["decision"], "SKIP")


class TestUnconfirmedToolAllowList(unittest.TestCase):
    """CR-092 (2026-08-15): a named tool with no anchor of its own must not
    silently clear a line just because some OTHER generic word in the same
    line matched a vocab tag. Confirmed real: Mercury Insurance's "Guidewire
    Policy Center... policy rating, rules engine" cleared as gap=False
    because "workflows"/"sales" (generic tags) matched, even though
    Guidewire itself has zero anchor anywhere in ground truth."""

    def test_unlisted_named_tool_becomes_soft_gap_despite_generic_word_match(self):
        # "ServiceMesh Pro" is not real, not in HARD_BLOCKED_TOOLS, not in
        # skills_catalog.json -- a stand-in for "some tool nobody thought to
        # deny-list in advance." "workflows" is a generic word likely to
        # anchor via ordinary vocab tags.
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Advanced knowledge of ServiceMesh Pro workflows and configuration.
            """
        )
        result = _build(jd)
        rows = [r for r in result["required"] if "servicemesh" in r["item"].lower()]
        self.assertEqual(len(rows), 1, result["required"])
        row = rows[0]
        self.assertTrue(row["gap"], f"expected gap, got anchor={row.get('anchor')!r}")
        self.assertEqual(row["gap_class"], "SOFT")

    def test_verified_tool_from_skills_catalog_not_flagged_as_unconfirmed(self):
        # Salesforce and Pendo are both in data/skills_catalog.json --
        # naming them must never trip the unconfirmed-tool WARN.
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Experience with Salesforce and Pendo required.
            """
        )
        result = _build(jd)
        rows = [r for r in result["required"] if "salesforce" in r["item"].lower()]
        self.assertEqual(len(rows), 1, result["required"])
        row = rows[0]
        self.assertNotIn("unconfirmed tool", (row.get("anchor") or "").lower())

    def test_guidewire_now_hard_blocked_not_silently_clear(self):
        """The real Mercury Insurance line. Named tools never HARD-gate
        (spec Sec. 9) -- Guidewire is a SOFT evidence gap, not silently clear."""
        jd = textwrap.dedent(
            """
            Preferred
            - 1+ years of advanced knowledge of Guidewire product models specifically working on Guidewire Policy Center, with knowledge of its function in underwriting/sales workflows, policy rating, rules engine, and Guidewire product models.
            """
        )
        result = _build(jd)
        rows = [r for r in result["preferred"] if "guidewire" in r["item"].lower()]
        self.assertEqual(len(rows), 1, result["preferred"])
        row = rows[0]
        self.assertTrue(row["gap"])
        self.assertEqual(row["gap_class"], "SOFT")


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
        # The original bug: word-splitting "Microsoft Teams"/"Google Suite" into
        # bare "microsoft"/"suite" tokens made those false TAG anchors. Check
        # specifically for that failure mode (a "tags:" match), not just any
        # appearance of the word -- CR-092's unconfirmed-tool annotation now
        # legitimately names "microsoft office suite" in a different, correct
        # context (flagging it as an unverified tool), which is not the bug
        # this test guards against.
        anchor_str = (row.get("anchor") or "").lower()
        tags_part = anchor_str.split(";")[0] if anchor_str.startswith("tags:") else ""
        self.assertNotIn("microsoft", tags_part)
        self.assertNotIn("suite", tags_part)

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
    def test_amplitude_does_not_hard_gate(self):
        """Named tools never HARD-gate (spec Sec. 9). Jason also has real
        Amplitude/Pendo evidence, so this line is not a gap."""
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS
            - Hands-on experience with Amplitude for product analytics
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip")
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

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
        """Amplitude on an alternatives list still must not HARD-gate."""
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
        self.assertNotEqual(result["tier"], "Skip")
        self.assertFalse(any(g.get("gap_class") == "HARD" for g in result["flagged_gaps"]))

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
# Test: LLM-based section extraction (2026-08-17) -- mocked, no real network
# ---------------------------------------------------------------------------

class TestSectionExtractionLLM(unittest.TestCase):
    """_extract_sections_llm never makes a real network call in these tests --
    call_llm and ensure_local_model_available are patched. The safety contract
    is id-lookup into harvested lines plus fail-closed when Qwen cannot run
    (no regex extractor, no other model)."""

    def setUp(self):
        from build_stage0_fit_gate import _extract_sections_llm
        from stage0_extract import harvest_extract_candidates
        self._extract_sections_llm = _extract_sections_llm
        self.jd = textwrap.dedent(
            """
            Requirements
            5+ years of product management experience in B2B SaaS
            Strong analytical and communication skills

            Preferred Qualifications
            Experience with Salesforce or similar CRM platforms
            """
        )
        cands = harvest_extract_candidates(self.jd)
        self.req_id = next(c["id"] for c in cands if "5+ years" in c["text"])
        self.pref_id = next(
            c["id"] for c in cands if "Salesforce" in c["text"]
        )

    def _llm_patches(self, **call_llm_kw):
        return (
            patch.dict(os.environ, {"STAGE0_SECTION_MODE": "llm"}),
            patch("model_manager.ensure_local_model_available"),
            patch("utils.call_llm", **call_llm_kw),
        )

    def test_llm_mode_off_returns_none_without_calling_llm(self):
        with patch.dict(os.environ, {"STAGE0_SECTION_MODE": "deterministic"}):
            with patch("utils.call_llm") as mock_call:
                result = self._extract_sections_llm(self.jd)
        mock_call.assert_not_called()
        self.assertIsNone(result)

    def test_valid_id_response_accepted(self):
        payload = json.dumps({
            "required": [self.req_id],
            "preferred": [self.pref_id],
            "responsibilities": [],
            "culture": [],
        })
        env, avail, llm = self._llm_patches(return_value=payload)
        with env, avail, llm as mock_call:
            result = self._extract_sections_llm(self.jd)
        self.assertIsNotNone(result)
        self.assertIn("5+ years", result["required"][0])
        self.assertIn("Salesforce", result["preferred"][0])
        self.assertGreaterEqual(len(result["required"]), 1)
        mock_call.assert_called_once()
        self.assertEqual(mock_call.call_args.kwargs.get("model"), STAGE0_EXTRACT_MODEL)
        system_prompt = mock_call.call_args.args[0]
        user_prompt = mock_call.call_args.args[1]
        self.assertIn("[1]", user_prompt)
        self.assertIn("integer ids", system_prompt.lower())
        self.assertIn("Do not copy the line text", user_prompt)

    def test_invented_ids_and_copied_wording_are_dropped(self):
        """Unknown ids and copied JD-style strings must never survive --
        resolved text is always a lookup into the harvested candidate list."""
        payload = json.dumps({
            "required": [
                self.req_id,
                99,
                "10+ years of experience leading a team of engineers",
            ],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
        })
        env, avail, llm = self._llm_patches(return_value=payload)
        with env, avail, llm:
            result = self._extract_sections_llm(self.jd)
        self.assertIsNotNone(result)
        joined = " | ".join(result["required"])
        self.assertIn("5+ years of product management experience in B2B SaaS", joined)
        self.assertNotIn("10+ years of experience leading a team of engineers", joined)

    def test_omitted_requirement_filled_from_header_hint(self):
        payload = json.dumps({
            "required": [self.req_id],
            "preferred": [self.pref_id],
            "responsibilities": [],
            "culture": [],
        })
        env, avail, llm = self._llm_patches(return_value=payload)
        with env, avail, llm:
            result = self._extract_sections_llm(self.jd)
        joined = " | ".join(result["required"])
        self.assertIn("5+ years of product management experience in B2B SaaS", joined)
        self.assertIn("Strong analytical and communication skills", joined)
        self.assertTrue(any("Salesforce" in p for p in result["preferred"]))


    def test_html_entity_jd_resolves_cleaned_harvested_text(self):
        jd = (
            "Role: &lt;p&gt;Technical Program Manager&lt;/p&gt;\n"
            "&lt;p&gt;5+ years of product management experience in B2B SaaS&lt;/p&gt;"
        )
        from stage0_extract import harvest_extract_candidates
        cands = harvest_extract_candidates(jd)
        req_id = next(c["id"] for c in cands if "5+ years" in c["text"])
        payload = json.dumps({
            "required": [req_id],
            "preferred": [],
            "responsibilities": [],
            "culture": [],
        })
        env, avail, llm = self._llm_patches(return_value=payload)
        with env, avail, llm:
            result = self._extract_sections_llm(jd)
        self.assertEqual(len(result["required"]), 1)
        self.assertIn("5+ years of product management experience in B2B SaaS", result["required"][0])
        self.assertNotIn("&lt;", result["required"][0])
        self.assertNotIn("<p>", result["required"][0].lower())

    def test_empty_harvest_raises_without_calling_llm(self):
        env, avail, llm = self._llm_patches(return_value="{}")
        with env, avail, llm as mock_call:
            with self.assertRaises(Stage0ExtractError) as ctx:
                self._extract_sections_llm("Hi")
        mock_call.assert_not_called()
        self.assertIn("no candidate lines", str(ctx.exception))
        self.assertIn("No regex fallback", str(ctx.exception))

    def test_empty_llm_response_raises_not_silent_none(self):
        env, avail, llm = self._llm_patches(return_value="")
        with env, avail, llm:
            with self.assertRaises(Stage0ExtractError) as ctx:
                self._extract_sections_llm(self.jd)
        self.assertIn(STAGE0_EXTRACT_MODEL, str(ctx.exception))
        self.assertIn("No fallback", str(ctx.exception))

    def test_malformed_json_raises_not_silent_none(self):
        env, avail, llm = self._llm_patches(return_value="not json at all")
        with env, avail, llm:
            with self.assertRaises(Stage0ExtractError) as ctx:
                self._extract_sections_llm(self.jd)
        self.assertIn(STAGE0_EXTRACT_MODEL, str(ctx.exception))

    def test_llm_exception_raises_not_silent_none(self):
        env, avail, llm = self._llm_patches(side_effect=RuntimeError("network down"))
        with env, avail, llm:
            with self.assertRaises(Stage0ExtractError) as ctx:
                self._extract_sections_llm(self.jd)
        self.assertIn(STAGE0_EXTRACT_MODEL, str(ctx.exception))
        self.assertIn("No fallback", str(ctx.exception))

    def test_model_unavailable_raises_without_calling_llm(self):
        from model_manager import LocalModelUnavailable
        with patch.dict(os.environ, {"STAGE0_SECTION_MODE": "llm"}):
            with patch(
                "model_manager.ensure_local_model_available",
                side_effect=LocalModelUnavailable(
                    f"{STAGE0_EXTRACT_MODEL} is not installed"
                ),
            ):
                with patch("utils.call_llm") as mock_call:
                    with self.assertRaises(Stage0ExtractError) as ctx:
                        self._extract_sections_llm(self.jd)
        mock_call.assert_not_called()
        self.assertIn(STAGE0_EXTRACT_MODEL, str(ctx.exception))

    def test_full_pipeline_stops_when_extract_model_unavailable(self):
        """build_stage0_fit_gate() must not quietly switch to the regex
        extractor when Qwen cannot run."""
        with patch.dict(os.environ, {"STAGE0_SECTION_MODE": "llm"}):
            with patch("model_manager.ensure_local_model_available"):
                with patch("utils.call_llm", return_value=""):
                    with self.assertRaises(Stage0ExtractError):
                        _build(_CLEAN_PM_JD)


class TestUnbridgeableDomainRequirement(unittest.TestCase):
    """2026-08-19, Jason-supplied, real miss: OneSource Virtual required
    "5+ years... in a payroll tax... industry" and "5+ years... with Payroll
    Tax filing... software" -- both scored a bridgeable SOFT domain gap, and
    the JD landed Tier 1/fit 80, despite Jason having zero real evidence for
    either (one had an empty claim_ids list in the authoring packet)."""

    def test_payroll_tax_required_with_years_is_hard_skip(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of progressive experience in a payroll tax or other highly regulated industry, performing analysis, requirements gathering, design and development duties in support of enterprise application systems.
            - 5+ years of experience with Payroll Tax filing and/or Payroll Tax filing software.
            """
        )
        result = _build(jd)
        self.assertEqual(result["tier"], "Skip")
        self.assertEqual(result["decision"], "SKIP")
        hard = [g for g in result["flagged_gaps"] if g.get("gap_class") == "HARD"]
        self.assertTrue(any(g.get("gap_source") == "domain" for g in hard), hard)

    def test_domain_with_pm_alternative_stays_bridgeable(self):
        """Real corpus false positives found running this against all 402
        archive JDs before shipping: "X years of product management ... in
        [domain A], [domain B], or [domain C]" lists product management --
        Jason's real, literal background -- as one of the acceptable
        alternatives. Must NOT hard-Skip (axos_bank, real case)."""
        jd = textwrap.dedent(
            """
            Requirements
            - 1-3+ years of experience in product management, consulting, banking, or fintech
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip", result.get("skip_reason") or result.get("notes"))
        hard_domain = [
            g for g in result["flagged_gaps"]
            if g.get("gap_class") == "HARD" and g.get("gap_source") == "domain"
        ]
        self.assertEqual(hard_domain, [], hard_domain)

    def test_domain_with_ideally_hedge_stays_bridgeable(self):
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience, ideally in fraud, identity, payments, or SaaS product management
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip", result.get("skip_reason") or result.get("notes"))

    def test_domain_in_preferred_bucket_stays_soft(self):
        """Required-only, same gate as the degree check -- a domain mention
        in Preferred is genuinely optional, must not force a Skip."""
        jd = textwrap.dedent(
            """
            Requirements
            - 5+ years of product management experience in B2B SaaS

            Preferred
            - 5+ years of experience in payroll tax or a highly regulated industry
            """
        )
        result = _build(jd)
        self.assertNotEqual(result["tier"], "Skip", result.get("skip_reason") or result.get("notes"))


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
