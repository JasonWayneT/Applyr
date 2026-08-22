"""Tests for submission_linter.py — Epic 1, Story 1.8."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from submission_linter import (
    lint_document,
    LintResult,
    check_b2b_saas_positioning,
    check_cross_employer_audience_bleed,
    check_jd_specificity_floor,
    check_wrong_job_company_bleed,
    known_company_names,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CL_CLEAN = """# JASON TAYLOR
candidate@example.com

Dear Hiring Manager,

HubSpot's shift toward product-led growth created a specific kind of product problem. The platform had to earn adoption from users who hadn't been sold to yet, which changed how discovery and prioritization had to work across product, engineering, and go-to-market teams in the same planning cycle.

At Cision, on a $40M ARR B2B platform, that was the kind of problem I was responsible for solving. I partnered with engineering, DBA, and DevOps to eliminate a 40% data drop-off that was eroding customer trust and contributing to churn across thousands of active accounts.

The data remediation work required coordinating across Legal, InfoSec, and Account Management while managing competing roadmap priorities. I treated the contact data failures as a product trust problem, not a minor bug, and drove the fix end-to-end through quarterly planning and clear success criteria tied to complaint volume. Separately, I used Pendo usage patterns and Salesforce subscription data to sequence migration work for high-risk accounts, so engineering capacity went to the features customers actually used instead of assumed must-haves.

I would welcome a conversation about how this experience maps to the platform challenges in this role. Thank you for your time and consideration.

Best regards,

Jason Taylor
"""

RESUME_CLEAN = """# JASON TAYLOR
candidate@example.com

## PROFESSIONAL SUMMARY

Product Manager with 7 years across B2B SaaS platforms. Owned data integrity, platform stability, and cross-functional delivery on a $40M ARR media monitoring platform supporting 3,500 enterprise accounts.

## PROFESSIONAL EXPERIENCE

### Product Manager | Cision | Sep 2021 - Jan 2026

Full Remote, San Diego, CA

* Eliminated a 40% contact data drop-off by driving a centralized data remediation initiative coordinated with Engineering, DBA, and DevOps.
* Resolved 90% of a 300-item security backlog through risk-weighted prioritization, maintaining core roadmap delivery.
* Enabled 700 voluntary account migrations using phased tooling built with Customer Experience and Account Management.

### Product Manager | Sterkly Services | Feb 2019 - Aug 2021

* Resolved a critical certificate distribution bottleneck for a macOS security product, sustaining an estimated $1M-$3M in product revenue.

### Account Manager / Product Owner | Zero To Sixty | June 2017 - January 2019

* Replaced a manual laptop-fulfillment process with a custom automated deployment script.

## EDUCATION

* **Bachelor of Business Administration**, National University, San Diego, CA, 2019
"""


# ---------------------------------------------------------------------------
# HARD_BLOCK tests — one per rule
# ---------------------------------------------------------------------------

def test_LR001_blocks_excited_to_apply():
    text = CL_CLEAN.replace("HubSpot's", "I am excited to apply to HubSpot's")
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-001" for v in r.blocks)


def test_LR001_passes_clean():
    r = lint_document(CL_CLEAN, "cover_letter")
    assert not any(v.rule_id == "LR-001" for v in r.blocks)


def test_LR002_blocks_excited_about():
    text = CL_CLEAN + "\nI am excited about this opportunity."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-002" for v in r.blocks)


def test_LR003_blocks_confident_that():
    text = CL_CLEAN + "\nI am confident that I can contribute."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-003" for v in r.blocks)


def test_LR004_blocks_proven_track_record_in_cl():
    text = CL_CLEAN + "\nI have a proven track record in platform delivery."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-004" for v in r.blocks)


def test_LR004_blocks_proven_track_record_in_resume():
    text = RESUME_CLEAN + "\n* Proven track record of delivery."
    r = lint_document(text, "resume")
    assert not r.passed
    assert any(v.rule_id == "LR-004" for v in r.blocks)


def test_LR005_blocks_writing_to_express():
    text = CL_CLEAN.replace("HubSpot's", "I am writing to express my interest in")
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-005" for v in r.blocks)


def test_LR006_blocks_em_dash():
    text = CL_CLEAN + "\nThis role — and the platform challenges — are exactly right for me."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-006" for v in r.blocks)


def test_LR006_blocks_double_dash():
    text = CL_CLEAN + "\nThis role -- and the platform challenges -- are a fit."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-006" for v in r.blocks)


_SAMPLE_EMAIL = "candidate@example.com"
_PHONE_PLACEHOLDER = "[" + "REDACTED_" + "PHONE]"
_EMAIL_PLACEHOLDER = "[" + "REDACTED_" + "EMAIL]"


def test_LR007_blocks_redacted_phone():
    text = CL_CLEAN.replace(_SAMPLE_EMAIL, _PHONE_PLACEHOLDER)
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-007" for v in r.blocks)


def test_LR008_blocks_redacted_email():
    text = CL_CLEAN.replace(_SAMPLE_EMAIL, _EMAIL_PLACEHOLDER)
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-008" for v in r.blocks)


def test_LR009_blocks_leverage():
    text = CL_CLEAN + "\nI will leverage my experience to drive results."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-009" for v in r.blocks)


def test_LR009_blocks_passionate():
    text = CL_CLEAN + "\nI am passionate about product management."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-009" for v in r.blocks)


def test_LR009_blocks_synergy():
    text = CL_CLEAN + "\nThe synergy between teams was strong."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-009" for v in r.blocks)


def test_LR010_blocks_bullets_in_cover_letter():
    text = CL_CLEAN + "\n* I did something important.\n* And another thing."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-010" for v in r.blocks)


def test_LR010_does_not_block_bullets_in_resume():
    r = lint_document(RESUME_CLEAN, "resume")
    assert not any(v.rule_id == "LR-010" for v in r.blocks)


def test_LR011_blocks_airo():
    text = CL_CLEAN + "\nI worked on Airo, a macOS product."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-011" for v in r.blocks)


def test_LR011_blocks_internal_codename_in_resume():
    text = RESUME_CLEAN + "\n* Led the Core B2B SaaS Platform roadmap."
    r = lint_document(text, "resume")
    assert not r.passed
    assert any(v.rule_id == "LR-011" for v in r.blocks)


def test_LR012_blocks_disabled_claim():
    text = CL_CLEAN + "\nI oversaw the $800K Canadian platform deprecation."
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-012" for v in r.blocks)


# ---------------------------------------------------------------------------
# WARN tests
# ---------------------------------------------------------------------------

def test_LW001_warns_on_short_cover_letter():
    short_cl = """# JASON TAYLOR\n\nDear Hiring Manager,\n\nHi. I would like to apply.\n\nBest regards,\n\nJason Taylor\n"""
    r = lint_document(short_cl, "cover_letter")
    assert any(v.rule_id == "LW-001" for v in r.warns)
    assert r.passed  # WARN doesn't block


def test_LW001_no_warn_on_correct_length():
    # Pad fixture body into the 220–450 WARN band without changing HARD_BLOCK coverage.
    pad = (
        " That work also meant writing clear requirements, defending tradeoffs in "
        "quarterly planning, and keeping executive stakeholders aligned on what "
        "shipped next versus what waited."
    )
    text = CL_CLEAN.replace(
        "Thank you for your time and consideration.",
        pad + " Thank you for your time and consideration.",
    )
    r = lint_document(text, "cover_letter")
    assert not any(v.rule_id == "LW-001" for v in r.warns)


def test_LW002_warns_on_long_resume():
    long_resume = RESUME_CLEAN + (
        "\n* "
        + "Managed platform deliverables with cross-functional teams across multiple quarters of roadmap work under constrained capacity. "
        * 80
    )
    r = lint_document(long_resume, "resume")
    assert any(v.rule_id == "LW-002" for v in r.warns)


def test_LW003_warns_on_furthermore():
    text = CL_CLEAN + "\nFurthermore, I have excellent platform skills."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-003" for v in r.warns)


def test_LW004_warns_on_aligns_perfectly():
    text = CL_CLEAN + "\nThis role aligns perfectly with my background."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-004" for v in r.warns)


# ---------------------------------------------------------------------------
# Doc-type specificity
# ---------------------------------------------------------------------------

def test_LR001_only_fires_for_cover_letters():
    text = RESUME_CLEAN + "\nI am excited to apply to this opportunity."
    r = lint_document(text, "resume")
    assert not any(v.rule_id == "LR-001" for v in r.blocks)


def test_clean_cover_letter_passes():
    r = lint_document(CL_CLEAN, "cover_letter")
    assert r.passed


def test_clean_resume_passes():
    r = lint_document(RESUME_CLEAN, "resume")
    assert r.passed


# ---------------------------------------------------------------------------
# LW-009-PAIR — shared phrasing across resume + cover letter
# ---------------------------------------------------------------------------

def test_LW009_pair_flags_shared_mechanism_phrase():
    from submission_linter import check_cross_document_repetition

    resume = RESUME_CLEAN + (
        "\n* Built a PTO-adjusted capacity model using T-shirt sizing to guide "
        "quarterly resource allocation across stability, compliance, and roadmap priorities\n"
    )
    letter = CL_CLEAN + (
        "\nI also built a PTO-adjusted capacity model using T-shirt sizing to guide "
        "how engineering resources were allocated each quarter.\n"
    )
    warns = check_cross_document_repetition(resume, letter)
    assert any(v.rule_id == "LW-009-PAIR" for v in warns)


def test_LW009_pair_allows_shared_metric_core_only():
    from submission_linter import check_cross_document_repetition, find_shared_phrases

    resume = "* Eliminated a 40% contact-data drop-off by partnering with engineering on a new path.\n"
    letter = (
        "When Salesforce closed-lost analysis showed data accuracy as a top named reason "
        "customers were leaving, I drove a replacement path that eliminated a 40% contact-data "
        "drop-off after an open ideation session with engineers.\n"
    )
    # The short metric core may appear in both; mechanism clauses must differ.
    shared = find_shared_phrases(resume, letter)
    assert not any("partnering with engineering" in s for s in shared)
    warns = check_cross_document_repetition(resume, letter)
    assert not any(v.rule_id == "LW-009-PAIR" for v in warns)


def test_LW009_pair_clean_when_vocabulary_diverges():
    from submission_linter import check_cross_document_repetition

    resume = (
        "* Every quarter, pulled priorities and blockers from Sales, Legal, DevOps, and DBA, "
        "resolved them into one roadmap, and presented it to the full product and engineering "
        "organization before work began.\n"
    )
    letter = (
        "Sales wanted data fixes prioritized. Legal and DevOps arrived with their own asks. "
        "My job each quarter was to force those into a single sequence the whole team could "
        "commit to before anyone started building.\n"
    )
    warns = check_cross_document_repetition(resume, letter)
    assert not any(v.rule_id == "LW-009-PAIR" for v in warns)


# ---------------------------------------------------------------------------
# no-ai-slop integration (LW-015 - LW-020), added 2026-07-23
# ---------------------------------------------------------------------------

def test_LW015_warns_on_throat_clearing_opener():
    text = CL_CLEAN + "\nHere's the thing, I have shipped fixes like this before."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-015" for v in r.warns)


def test_LW016_warns_on_faux_insight_setup():
    text = CL_CLEAN + "\nWhat if I told you this role is exactly the kind of problem I solve."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-016" for v in r.warns)


def test_LW017_warns_on_importance_puffery():
    text = CL_CLEAN + "\nThis launch marks a pivotal moment for the company."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-017" for v in r.warns)


def test_LW018_warns_on_weasel_attribution():
    text = CL_CLEAN + "\nExperts agree that this approach works well."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-018" for v in r.warns)


def test_LW019_warns_on_fake_strong_hub_verb():
    text = CL_CLEAN + "\nThe tool serves as a centralized hub for sponsor management."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-019" for v in r.warns)


def test_LW020_warns_on_binary_contrast_shape():
    text = CL_CLEAN + "\nIt's not the model. It's the eval that matters here."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-020" for v in r.warns)


def test_LW007_warns_on_ultimately_sentence_starter():
    text = CL_CLEAN + "\nUltimately, I want to help this team ship faster."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-007" for v in r.warns)


def test_LW007_no_warn_on_ultimately_mid_sentence():
    text = CL_CLEAN + "\nI was ultimately responsible for the migration outcome."
    r = lint_document(text, "cover_letter")
    assert not any(v.rule_id == "LW-007" for v in r.warns)


def test_LW033_warns_on_lives_or_dies():
    text = CL_CLEAN + "\nA federal program lives or dies on whether the workstreams stay aligned."
    r = lint_document(text, "cover_letter")
    assert any(v.rule_id == "LW-033" for v in r.warns)


def test_no_ai_slop_rules_clean_on_baseline_fixtures():
    r = lint_document(CL_CLEAN, "cover_letter")
    new_rule_ids = {"LW-015", "LW-016", "LW-017", "LW-018", "LW-019", "LW-020"}
    assert not any(v.rule_id in new_rule_ids for v in r.warns)


# ---------------------------------------------------------------------------
# LintResult structure
# ---------------------------------------------------------------------------

def test_lint_result_passed_false_on_hard_block():
    text = CL_CLEAN + "\nI am excited to apply."
    r = lint_document(text, "cover_letter")
    assert isinstance(r, LintResult)
    assert r.passed is False


def test_lint_result_doc_type_set():
    r = lint_document(CL_CLEAN, "cover_letter")
    assert r.document_type == "cover_letter"


def test_LR013_blocks_last_four_years():
    text = CL_CLEAN.replace(
        "that was the kind of problem I was responsible for solving",
        "mirrors how I have worked for the last four years",
    )
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-013" for v in r.blocks)


def test_LR028_blocks_sdsu_education():
    text = RESUME_CLEAN.replace(
        "National University, San Diego, CA, 2019",
        "San Diego State University",
    )
    r = lint_document(text, "resume")
    assert not r.passed
    assert any(v.rule_id == "LR-028" for v in r.blocks)


def test_LR028_requires_national_university():
    text = RESUME_CLEAN.replace("National University", "Example University")
    r = lint_document(text, "resume")
    assert not r.passed
    assert any(v.rule_id == "LR-028" for v in r.blocks)


def test_LR029_blocks_senior_cision_header():
    text = RESUME_CLEAN.replace(
        "### Product Manager | Cision | Sep 2021 - Jan 2026",
        "### Senior Product Manager | Cision | 2021 - 2024",
    )
    r = lint_document(text, "resume")
    assert not r.passed
    assert any(v.rule_id == "LR-029" for v in r.blocks)


def test_LR029_blocks_operations_manager_z2s():
    text = RESUME_CLEAN.replace(
        "### Account Manager / Product Owner | Zero To Sixty | June 2017 - January 2019",
        "### Operations Manager | Zero To Sixty | 2017 - 2020",
    )
    r = lint_document(text, "resume")
    assert not r.passed
    assert any(v.rule_id == "LR-029" for v in r.blocks)


def test_LR030_blocks_duplicate_welcome_closers():
    text = CL_CLEAN.replace(
        "I would welcome a conversation about how this experience maps to the platform challenges in this role. Thank you for your time and consideration.",
        "I would welcome the chance to bring this experience to your team.\n\n"
        "I would welcome a conversation about this role. Thank you for your time and consideration.",
    )
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-030" for v in r.blocks)


def test_LR030_allows_single_welcome_closer():
    r = lint_document(CL_CLEAN, "cover_letter")
    assert not any(v.rule_id == "LR-030" for v in r.blocks)


def test_LR031_blocks_b2b_saas_summary_when_jd_lacks_saas():
    # RESUME_CLEAN summary already contains "B2B SaaS platforms".
    jd = "We are hiring a Product Manager for our marketplace. Build roadmaps with engineering."
    blocks = check_b2b_saas_positioning(RESUME_CLEAN, jd)
    assert len(blocks) == 1
    assert blocks[0].rule_id == "LR-031"
    assert blocks[0].severity == "HARD_BLOCK"


def test_LR031_allows_b2b_saas_when_jd_says_saas():
    jd = "Looking for a PM with B2B SaaS experience shipping enterprise products."
    assert check_b2b_saas_positioning(RESUME_CLEAN, jd) == []


def test_LR031_ignores_b2b_saas_outside_summary():
    resume = RESUME_CLEAN.replace(
        "Product Manager with 7 years across B2B SaaS platforms.",
        "Product Manager with 7 years across digital platforms.",
    )
    resume += "\n* Owned product across two customer-facing B2B SaaS platform stacks."
    jd = "Product Manager for a healthcare marketplace. No SaaS keyword here."
    assert check_b2b_saas_positioning(resume, jd) == []


# ---------------------------------------------------------------------------
# LW-021 / LW-026 -- added 2026-08-18. No prior test coverage existed for
# either rule despite both being live in lint_folder(); a same-day change
# that expanded LW-021's stopword list and raised its min_count (to fix ~50
# real false positives found in a 6-company batch) had nothing regression-
# testing it against the actual bug the rule exists to catch.
# ---------------------------------------------------------------------------

NEWSELA_STYLE_JD = """
We are looking for a Product Manager to build tools for teachers and students.
Teachers use our platform daily to assign reading materials, and teachers rely
on classroom analytics to track student progress. You will work closely with
teachers to understand classroom needs.
"""


def test_LW021_still_catches_real_cross_employer_bleed():
    """Regression: the actual Newsela bug this rule exists for (found
    2026-07-30) -- a Cision bullet wrongly using the target JD's own
    audience vocabulary ("teachers") must still be caught after the
    2026-08-18 stopword/min_count tightening."""
    resume = RESUME_CLEAN.replace(
        "* Enabled 700 voluntary account migrations using phased tooling built with Customer Experience and Account Management.",
        "* Enabled 700 voluntary account migrations using phased tooling built with Customer Experience and Account Management.\n"
        "* Delivered fixes teachers and other users would feel directly in the product, cutting reported issues by half.",
    )
    violations = check_cross_employer_audience_bleed(
        resume, "", NEWSELA_STYLE_JD, company_name="Newsela"
    )
    assert any(v.rule_id == "LW-021" for v in violations)
    assert any("teachers" in v.message for v in violations)


def test_LW021_no_longer_flags_generic_pm_vocabulary():
    """Regression: a Cision bullet using ordinary generic PM/business
    vocabulary that happens to also appear in the target JD must NOT be
    flagged. This is the actual false-positive pattern found in a real
    6-company batch (2026-08-18), not a hypothetical."""
    jd = (
        "We need a Product Manager with strong technical skills, agile "
        "experience, and the ability to drive execution through capacity "
        "planning and system-level thinking across the organization."
    )
    resume = RESUME_CLEAN.replace(
        "* Enabled 700 voluntary account migrations using phased tooling built with Customer Experience and Account Management.",
        "* Enabled 700 voluntary account migrations using phased tooling built with Customer Experience and Account Management.\n"
        "* Drove execution through better capacity planning and system-level thinking across the team.",
    )
    violations = check_cross_employer_audience_bleed(resume, "", jd, company_name="Acme")
    assert violations == []


def test_LW026_specificity_floor_still_finds_real_hits():
    """LW-026 shares _jd_distinctive_words() with LW-021 but intentionally
    keeps the lower default min_count=2 -- confirm the 2026-08-18 stopword
    expansion (tuned for LW-021) didn't also gut LW-026's ability to find
    legitimate specificity signal in a normal JD."""
    jd = (
        "Nirvana is modernizing commercial insurance underwriting with "
        "telematics data and risk models. Underwriting and telematics are "
        "core to how this role works with brokers."
    )
    cover_letter = CL_CLEAN.replace(
        "HubSpot's shift toward product-led growth",
        "Nirvana's telematics-driven underwriting approach",
    )
    violations = check_jd_specificity_floor(cover_letter, jd, company_name="Nirvana")
    assert violations == []


def test_LW032_flags_other_known_company():
    hits = check_wrong_job_company_bleed(
        resume="Worked at Cision on the platform.",
        cover_letter="This is the same problem I solved for Lightcast last month.",
        jd_text="Product Manager at Gravitee",
        own_company="Gravitee",
        known_names={"Lightcast", "Gravitee", "Cision"},
    )
    assert any(v.rule_id == "LW-032" and "Lightcast" in v.message for v in hits)
    assert not any("Gravitee" in v.message for v in hits)
    assert not any("Cision" in v.message for v in hits)


def test_LW032_own_company_does_not_warn():
    hits = check_wrong_job_company_bleed(
        resume="",
        cover_letter="I want to join Lightcast because the platform work matches.",
        jd_text="Product Manager",
        own_company="Lightcast",
        known_names={"Lightcast", "Gravitee"},
    )
    assert hits == []


def test_LW032_jd_mention_does_not_warn():
    hits = check_wrong_job_company_bleed(
        resume="",
        cover_letter="Partnering the way Lightcast is named in this posting.",
        jd_text="We compete with Lightcast in this market.",
        own_company="Gravitee",
        known_names={"Lightcast", "Gravitee"},
    )
    assert hits == []


def test_LW032_missing_db_does_not_raise():
    names = known_company_names(db_path="/nonexistent/jobagent.sqlite", submissions_root="/nonexistent")
    assert names == set()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
