"""Tests for submission_linter.py — Epic 1, Story 1.8."""
import shutil
import sys
import os
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(__file__))

from submission_linter import (
    lint_document,
    LintResult,
    check_b2b_saas_positioning,
    check_unsolicited_geography,
    check_attribution_verb_strength,
    check_bypass_authorship,
    check_customer_discovery,
    check_competency_process_notes,
    check_placeholder_company,
    check_cited_span_fidelity,
    check_experience_role_bullets,
    check_letter_names_employer,
    check_data_model_phrase,
    check_required_hedges,
    collect_fidelity_hard_blocks,
    check_cross_employer_audience_bleed,
    check_generic_hook_self_reference,
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


def test_LW009_pair_equal_length_phrases_sort_by_text():
    from submission_linter import find_shared_phrases

    resume = (
        "* Monday alpha beta gamma delta epsilon zeta before the review.\n"
        "* Tuesday kappa lambda mu nu xi omicron after the review.\n"
    )
    letter = (
        "The plan was alpha beta gamma delta epsilon zeta once the numbers landed.\n"
        "The other plan was kappa lambda mu nu xi omicron once the dates landed.\n"
    )
    shared = find_shared_phrases(resume, letter)
    assert shared == sorted(shared, key=lambda item: (-len(item), item))
    assert shared[0].startswith("alpha ")


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


_RENTANA_GEO_LETTER = """# Jason Taylor
San Diego, CA | candidate@example.com

Dear Hiring Manager,

Rentana's use of operating data to support decisions caught my attention.

At Cision I owned the customer-facing platform for media monitoring.

I also organized the roadmap around cost efficiency and platform stability.

I have worked across two fully remote companies with engineering distributed across the U.S., Budapest, and India, and I would welcome the chance to bring that approach to Rentana's platform.

Best regards,

Jason Taylor
"""


def test_LW039_rentana_cover_letter_line_12_fires():
    from pathlib import Path

    folder = Path(__file__).resolve().parent.parent / "data" / "submissions" / "rentana"
    jd = (folder / "Original_JD.txt").read_text(encoding="utf-8")
    lines = _RENTANA_GEO_LETTER.splitlines()
    assert "distributed across the U.S., Budapest, and India" in lines[11]
    warns = check_unsolicited_geography(_RENTANA_GEO_LETTER, jd, "cover_letter")
    assert len(warns) == 1
    assert warns[0].rule_id == "LW-039"
    assert warns[0].severity == "WARN"
    assert warns[0].line == 12


def test_LW039_global_teams_jd_does_not_fire():
    jd = (
        "Title: Product Manager\n\nRemote (USA)\n\n"
        "You will collaborate with global teams on the product roadmap.\n"
    )
    assert check_unsolicited_geography(_RENTANA_GEO_LETTER, jd, "cover_letter") == []


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


def test_LW032_equal_length_names_have_deterministic_tie_break():
    """Two equal-length names ('workday', 'Unified', both 7 chars) must always
    sort the same way -- reproduces a live bug (crio, 2026-09-20) where
    `sorted(names, key=len, reverse=True)` had no tie-break, so a length tie
    let the hash-randomized iteration order of the `names` set (a fresh
    per-process ordering, since `known_company_names()` returns a set) leak
    into finding order, flipping the dispositions.json content hash bound to
    it across separate worker process runs on unchanged documents. The fix
    adds a lowercased-name tie-break, which is a total order for distinct
    names and therefore always produces the same output regardless of the
    input set's iteration order."""
    # Fixture note (2026-09-21): originally used "workday-hours" as filler
    # resume text -- that is itself the exact capacity-phrasing false
    # positive fixed the same day (isolved), so this fixture would have
    # started silently asserting on excluded text. Switched to a genuine
    # company mention so the fixture still exercises a real LW-032 match.
    resume = "Implemented Workday HCM as part of the engineering capacity rollout."
    cover_letter = "Presented the quarterly plan at Unified to stakeholders."
    hits = check_wrong_job_company_bleed(
        resume=resume,
        cover_letter=cover_letter,
        jd_text="Product Manager at Crio",
        own_company="Crio",
        known_names={"workday", "Unified", "Gravitee"},
    )
    matched = [v.message for v in hits if v.rule_id == "LW-032"]
    assert len(matched) == 2
    # "unified" < "workday" alphabetically -- the tie-break must be stable.
    assert "Unified" in matched[0] and "workday" in matched[1]


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


def test_LW032_workday_hours_capacity_phrase_not_flagged():
    """Live false positive (isolved, 2026-09-21): "developer workday-hours"
    is ordinary capacity-planning phrasing, not a mention of the Workday
    company -- same collision blocked_tools.hard_blocked_tool_pattern's own
    workday exclusion already handles, in a separate check that never got
    the same fix."""
    hits = check_wrong_job_company_bleed(
        resume=(
            "Optimized engineering resource allocation by establishing a "
            "PTO-adjusted capacity model based on developer workday-hours "
            "and uncertainty bands."
        ),
        cover_letter="",
        jd_text="Product Manager",
        own_company="Isolved",
        known_names={"workday", "Isolved"},
    )
    assert hits == []


def test_LW032_real_workday_mention_still_flagged():
    hits = check_wrong_job_company_bleed(
        resume="Implemented Workday HCM for the client's HR team.",
        cover_letter="",
        jd_text="Product Manager",
        own_company="Isolved",
        known_names={"workday", "Isolved"},
    )
    assert any(v.rule_id == "LW-032" and "workday" in v.message for v in hits)


def test_LW032_the_standard_line_phrase_not_flagged():
    """Live false positive (omnissa, 2026-09-21): 'skip the standard line'
    is ordinary queue phrasing, not a mention of The Standard."""
    hits = check_wrong_job_company_bleed(
        resume="",
        cover_letter=(
            "I designed a weighted priority-score formula for Jira issues "
            "from severity and incident frequency, with a qualitative "
            "override so premium clients could skip the standard line."
        ),
        jd_text="Product Manager at Omnissa",
        own_company="Omnissa",
        known_names={"The Standard", "Omnissa"},
    )
    assert hits == []


def test_LW032_real_the_standard_mention_still_flagged():
    hits = check_wrong_job_company_bleed(
        resume="I interviewed at The Standard for their platform PM role.",
        cover_letter="",
        jd_text="Product Manager at Omnissa",
        own_company="Omnissa",
        known_names={"The Standard", "Omnissa"},
    )
    assert any(v.rule_id == "LW-032" and "The Standard" in v.message for v in hits)


def test_LW032_own_company_does_not_warn():
    hits = check_wrong_job_company_bleed(
        resume="",
        cover_letter="I want to join Lightcast because the platform work matches.",
        jd_text="Product Manager",
        own_company="Lightcast",
        known_names={"Lightcast", "Gravitee"},
    )
    assert hits == []


def test_LR032_blocks_defensive_ownership_disclaimer():
    result = lint_document(
        CL_CLEAN.replace(
            "I partnered with engineering",
            "Most of the time the fix was mine to make. I partnered with engineering",
        ),
        "cover_letter",
    )
    assert any(v.rule_id == "LR-032" for v in result.blocks)


def test_LW021_does_not_match_cision_inside_decisions_or_generic_operations():
    jd = (
        "Patients and advocates make healthcare decisions through internal operations. "
        "These operations help patients make better decisions. Patients use the service "
        "while advocates support healthcare decisions and operations."
    )
    letter = (
        "Solace helps patients and advocates make decisions inside healthcare operations. "
        "That makes the user funnel part of the same product problem."
    )
    assert check_cross_employer_audience_bleed(
        "", letter, jd, company_name="Solace"
    ) == []


def test_LW021_allows_target_framing_before_past_employer_bridge():
    jd = (
        "PlayStation membership supports gaming subscriptions. PlayStation "
        "membership gives subscribers gaming benefits and PlayStation access."
    )
    letter = (
        "PlayStation membership is the part of this role that stands out to me. "
        "At Cision, I worked on a paid-content initiative with separate ingestion routes."
    )
    assert check_cross_employer_audience_bleed(
        "", letter, jd, company_name="Sony Interactive Entertainment"
    ) == []


def test_LW038_warns_on_generic_self_referential_hook():
    letter = (
        "Dear Hiring Manager,\n\n"
        "Form Health's new care-delivery program shows what makes this role interesting.\n\n"
        "At Cision, I turned churn signals into product priorities."
    )
    findings = check_generic_hook_self_reference(letter)
    assert any(v.rule_id == "LW-038" for v in findings)


def test_LW038_allows_specific_hook():
    letter = (
        "Dear Hiring Manager,\n\n"
        "Form Health's new care-delivery program expands access by reducing the "
        "administrative work around prescribing.\n\n"
        "At Cision, I turned churn signals into product priorities."
    )
    assert check_generic_hook_self_reference(letter) == []


def test_LW038_ignores_self_reference_outside_hook():
    letter = (
        "Dear Hiring Manager,\n\n"
        "Form Health's new care-delivery program expands access by reducing the "
        "administrative work around prescribing.\n\n"
        "That work shows what makes this role interesting to me."
    )
    assert check_generic_hook_self_reference(letter) == []


def test_LR038_blocks_the_stage2_bypass_overclaims():
    """The three Stage 2 repairs from 2026-09-22 claimed Jason made the connection."""
    bad = [
        "After customer reports of outdated records, removed a 40% drop-off in aging ingestion pipelines by connecting intake directly to the upstream system of record, and those reports fell to none.",
        "Cut a 40% pipeline data-loss rate to zero recurring stale-data complaints by bypassing an unreliable legacy extraction path and connecting the platform directly to the upstream authoritative database.",
        "Prioritized a production fix on a failing ingestion path that removed a 40% drop-off and ended stale-data complaints, writing user stories for the frontend screens and the backend database connection.",
    ]
    for bullet in bad:
        hits = check_bypass_authorship(f"- {bullet}\n", "")
        assert any(v.rule_id == "LR-038" and v.severity == "HARD_BLOCK" for v in hits), bullet


def test_LR038_allows_decision_wording_and_the_approved_story():
    good = [
        "Traced silent contact-data loss hop by hop through a multi-stage ETL pipeline, then prioritized an engineer's proposal to read the upstream database directly, cutting a 40 percent drop-off and ending the stale contact complaints.",
        "Prioritized a source-database integration after lost-subscription analysis named inaccurate records as a top reason customers left, cutting a 40% data drop-off and bringing stale-data complaints to zero.",
        "After customer reports of outdated contact records, drove the decision to bypass aging ETL paths into the upstream system of record, which ended the 40% drop-off and brought those reports to zero.",
        "Prioritized and drove a centralized platform data remediation initiative that bypassed failing legacy ETL paths to integrate directly with the upstream source-of-truth database, eliminating a 40% data drop-off rate and reducing stale-data complaints to zero.",
        "After an engineer proposed reading the system of record directly, prioritized that path, which removed a 40% contact-data drop-off and ended stale-data complaints.",
    ]
    for bullet in good:
        assert check_bypass_authorship(f"- {bullet}\n", "") == [], bullet


def test_LR038_blocks_owned_integration_and_allows_a_decision():
    bad = (
        "- Owned the integration between upstream data providers and the platform, "
        "resolving a 40% data failure rate and eliminating the stale-contact complaints.\n"
    )
    good = (
        "- Drove the decision to replace the legacy path, which ended a 40% drop-off "
        "and brought stale-data complaints to zero.\n"
    )
    assert any(v.rule_id == "LR-038" for v in check_bypass_authorship(bad, ""))
    assert check_bypass_authorship(good, "") == []


def test_LR039_blocks_customer_discovery_and_allows_a_denial():
    resume = (
        "## CORE COMPETENCIES\n"
        "Roadmaps | customer discovery | Jira\n\n"
        "* Used closed-lost reviews to see why accounts left.\n"
    )
    denial = "He did not run customer discovery. The organization blocked it."
    letter_claim = "I used customer discovery to learn what buyers wanted."
    letter_jd = "The role asks for customer discovery with buyers."
    assert any(v.rule_id == "LR-039" for v in check_customer_discovery(resume, ""))
    assert check_customer_discovery("", denial) == []
    assert any(v.rule_id == "LR-039" for v in check_customer_discovery("", letter_claim))
    assert check_customer_discovery("", letter_jd) == []


def test_LR038_blocks_ingestion_loss_sentence_and_allows_the_repair():
    bad = (
        "The corrected feed cleared the ingestion loss those reviews had measured at 40%, "
        "and the stale-record complaints stopped."
    )
    good = (
        "The corrected feed cleared the contact-data drop-off those reviews had measured at 40%, "
        "and the stale-record complaints stopped."
    )
    assert any(v.rule_id == "LR-038" for v in check_bypass_authorship("", bad))
    assert check_bypass_authorship("", good) == []


def test_LW028_adjacent_team_built_is_not_jasons_verb():
    letter = (
        "When an adjacent team at Cision built an AI-assisted content-generation "
        "platform, I conducted joint prompt-engineering research with the lead "
        "product manager to study how per-specialization prompt architectures "
        "performed under production conditions."
    )
    assert not any(
        v.rule_id == "LW-028"
        for v in check_attribution_verb_strength("", letter)
    )
    claimed = "I built the content-generation platform and its prompt orchestration."
    assert any(
        v.rule_id == "LW-028"
        for v in check_attribution_verb_strength("", claimed)
    )


def test_LW028_allows_acc303_separate_subject_attribution():
    letter = (
        "I built the company's first professional landing page, after which engineering "
        "built the automated Salesforce onboarding funnel around it, together lifting "
        "conversion by roughly 40 percentage points."
    )
    assert not any(
        v.rule_id == "LW-028"
        for v in check_attribution_verb_strength("", letter)
    )
    alternate = (
        "A landing page I built became the entry point for an engineering-built "
        "Salesforce onboarding flow, together lifting conversion by roughly "
        "40 percentage points."
    )
    assert not any(
        v.rule_id == "LW-028"
        for v in check_attribution_verb_strength("", alternate)
    )
    enabled = (
        "Built the company's first professional landing page that enabled "
        "engineering to deploy an automated Salesforce onboarding funnel, "
        "lifting account-manager-reported conversion by roughly 40 percentage points."
    )
    assert not any(
        v.rule_id == "LW-028"
        for v in check_attribution_verb_strength("", enabled)
    )
    owned_funnel = (
        "I built the Salesforce onboarding funnel and lifted conversion by "
        "roughly 40 percentage points."
    )
    assert any(
        v.rule_id == "LW-028"
        for v in check_attribution_verb_strength("", owned_funnel)
    )


def test_LW032_ignores_contact_header_and_ambiguous_common_names():
    hits = check_wrong_job_company_bleed(
        resume="# Jason\nlinkedin.com/in/jason\n\n## PROFESSIONAL SUMMARY\nProduct Manager.",
        cover_letter=(
            "# Jason\nlinkedin.com/in/jason\n\nDear Hiring Manager,\n\n"
            "I use a weighted point system and name the tradeoffs."
        ),
        jd_text="Product Manager at Solace",
        own_company="Solace",
        known_names={"LinkedIn", "Point", "Name", "Solace"},
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


def test_LW032_unified_adjective_is_not_the_company():
    """Live miss (modern_campus, 2026-09-22): 'unified stakeholder' is English."""
    hits = check_wrong_job_company_bleed(
        resume=(
            "## PROFESSIONAL SUMMARY\n\n"
            "- Maintain unified stakeholder management across planning cycles."
        ),
        cover_letter="",
        jd_text="Product manager for student engagement.",
        own_company="Modern Campus",
        known_names={"Unified", "Modern Campus"},
    )
    assert hits == []
    named = check_wrong_job_company_bleed(
        resume="## PROFESSIONAL SUMMARY\n\nShipped the integration at Unified last year.",
        cover_letter="",
        jd_text="Product manager for student engagement.",
        own_company="Modern Campus",
        known_names={"Unified", "Modern Campus"},
    )
    assert any(v.rule_id == "LW-032" for v in named), named
    adjective = check_wrong_job_company_bleed(
        resume=(
            "## PROFESSIONAL SUMMARY\n\n"
            "Brought engineering, Legal, and Sales into a unified roadmap."
        ),
        cover_letter="",
        jd_text="Product manager for benefits administration.",
        own_company="Highmark Health",
        known_names={"Unified", "Highmark Health"},
    )
    assert adjective == []


def test_LW032_duplicate_company_suffix_is_the_same_employer():
    hits = check_wrong_job_company_bleed(
        resume="## PROFESSIONAL SUMMARY\n\nMedrisk runs the network I would support.",
        cover_letter="",
        jd_text="Product manager role.",
        own_company="Medrisk 2",
        known_names={"Medrisk", "Lightcast"},
    )
    assert hits == []
    other = check_wrong_job_company_bleed(
        resume="## PROFESSIONAL SUMMARY\n\nLightcast is a different company.",
        cover_letter="",
        jd_text="Product manager role.",
        own_company="Medrisk 2",
        known_names={"Medrisk", "Lightcast"},
    )
    assert any(v.rule_id == "LW-032" and "Lightcast" in v.message for v in other)


def test_LW032_missing_db_does_not_raise():
    names = known_company_names(db_path="/nonexistent/jobagent.sqlite", submissions_root="/nonexistent")
    assert names == set()


def test_LW005_devops_partner_is_verified():
    """Live miss (velosio, 2026-09-21): rstrip('s') turned DevOps into
    'devop', which is not in _VERIFIED_PARTNERS, so a verified partner
    warned as unverified."""
    text = (
        "In previous roles, partnering with DevOps, quality assurance, "
        "and customer-facing teams kept each committed increment honest."
    )
    result = lint_document(text, doc_type="cover_letter")
    assert not any(v.rule_id == "LW-005" for v in result.warns), result.warns


def test_LW005_still_warns_unverified_design_partner():
    text = "I partnered with Design to ship the checkout flow."
    result = lint_document(text, doc_type="cover_letter")
    assert any(v.rule_id == "LW-005" for v in result.warns), result.warns


def test_LW005_peer_product_manager_is_same_function():
    """Live miss (iperium, 2026-09-22): a peer PM is not an outside department."""
    text = (
        "I also partnered with a peer product manager on joint "
        "prompt-engineering research, analyzing a production prompt-orchestration system."
    )
    result = lint_document(text, doc_type="cover_letter")
    assert not any(v.rule_id == "LW-005" for v in result.warns), result.warns


def test_LR026_epic_not_flagged_when_agile_word_precedes_it():
    """Live miss (peoplefinders, 2026-09-21): "new roadmap epics." -- the
    qualifying Agile word ("roadmap") comes BEFORE "epics", which
    blocked_tools.py's regex-only lookahead can't catch (stdlib re has no
    variable-width lookbehind). lint_document() must not HARD_BLOCK this."""
    text = (
        "giving teams realistic bandwidth bands for new roadmap epics. "
        "In parallel, I evaluated user interaction patterns."
    )
    result = lint_document(text, doc_type="cover_letter")
    assert not any(v.rule_id == "LR-026" for v in result.blocks), result.blocks


def test_LR026_real_epic_company_still_flagged():
    text = "Worked extensively with Epic EHR systems for clinical data integration."
    result = lint_document(text, doc_type="resume")
    assert any(v.rule_id == "LR-026" for v in result.blocks), result.blocks


def test_LR026_blocks_dynamics_365_business_central():
    """Live miss (velosio, 2026-09-21): first-draft cover letter opened on
    Microsoft Dynamics 365 Business Central. Jason answered NOT_PRESENT.
    SAP/NetSuite were already hard-blocked; Dynamics was not."""
    text = (
        "Expanding proprietary IP solutions across Microsoft Dynamics 365 "
        "Business Central requires a product manager who can anchor development."
    )
    result = lint_document(text, doc_type="cover_letter")
    assert any(v.rule_id == "LR-026" for v in result.blocks), result.blocks


def test_LR026_blocks_workspace_one_uem():
    """Live miss (omnissa, 2026-09-21): Review Center NOT_PRESENT on
    Workspace ONE UEM, then Stage 0 still mapped a SOFT bridge."""
    text = (
        "Hands-on experience with Workspace ONE UEM is how I would "
        "approach frontline device management at Omnissa."
    )
    result = lint_document(text, doc_type="cover_letter")
    assert any(v.rule_id == "LR-026" for v in result.blocks), result.blocks


def test_LR040_blocks_a_process_note_in_competencies():
    resume = (
        "## CORE COMPETENCIES\n"
        "Jira | Direct customer discovery did not happen\n\n"
        "## PROFESSIONAL EXPERIENCE\n"
    )
    assert any(v.rule_id == "LR-040" for v in check_competency_process_notes(resume))
    clean = (
        "## CORE COMPETENCIES\n"
        "Jira | Roadmaps\n\n"
        "## PROFESSIONAL EXPERIENCE\n"
        "* He did not run customer discovery.\n"
    )
    assert check_competency_process_notes(clean) == []


def test_LR041_blocks_placeholder_company():
    assert any(
        v.rule_id == "LR-041"
        for v in check_placeholder_company("Confidential is tackling a growth phase.")
    )
    assert check_placeholder_company("Keep the customer list confidential.") == []


def test_LR042_binds_the_unit_and_rejects_an_unseen_percent():
    spans = [
        "saving $8,500 per quarter ($34,000 annually) with the deployment script.",
        "saving $22,100 annually by co-creating the onboarding tool.",
        "churn held near 7%.",
    ]
    annually = "* Scaled fulfillment, saving $8,500 annually."
    bare = "* Scaled fulfillment, saving $8,500."
    quarterly = "* Scaled fulfillment, cutting $8,500 in quarterly operating spend."
    onboarding = "* Saved $22,100 annually by co-creating the onboarding tool."
    annual_phrase = (
        "* Co-created an onboarding tool, securing $22,100 in annual recurring savings."
    )
    derived = "* Supported annual retention near 93% by prioritizing reliability."
    assert any(v.rule_id == "LR-042" for v in check_cited_span_fidelity(annually, "", spans))
    assert any(v.rule_id == "LR-042" for v in check_cited_span_fidelity(bare, "", spans))
    assert check_cited_span_fidelity(quarterly, "", spans) == []
    assert check_cited_span_fidelity(onboarding, "", spans) == []
    assert check_cited_span_fidelity(annual_phrase, "", spans) == []
    arr = "* Directed product scope across two stacks representing $40M ARR."
    assert check_cited_span_fidelity(arr, "", [
        "Owned a customer-facing platform, a $40M ARR stack serving 25,000 users.",
    ]) == []
    assert any(v.rule_id == "LR-042" for v in check_cited_span_fidelity(derived, "", spans))


def test_LR042_blocks_a_swapped_percent_referent():
    profiles = (
        "per-client data profiles were widely assumed must-have but used by only "
        "~25% of customers; custom tagging took priority."
    )
    migration = "Estimated at least ~95% of customers flipped."
    dropoff = "Eliminated a 40% data drop-off rate between sources."
    backlog = "Resolved 90% of the backlog over a phased period."
    risks = "Resolved 90% of security risks while balancing new work."
    swapped = (
        "Per-client data profiles represented approximately 25% of platform usage."
    )
    bare_usage = (
        "* Analyzing usage data across Pendo and Salesforce to address a "
        "25% core data usage profile."
    )
    customers = "Roughly 25% of customers used per-client data profiles."
    who_used = "Of the 25% who used per-client data profiles, the rest used it lightly."
    accounts = "* An estimated 95% of active accounts completed the migration."
    records = "* The pipeline was dropping 40% of records before the fix."
    security = "The work resolved 90% of security risks in that year."
    unrelated = "Travel for this role is about 25% of the time."
    assert any(v.rule_id == "LR-042" for v in check_cited_span_fidelity("", swapped, [profiles]))
    assert any(v.rule_id == "LR-042" for v in check_cited_span_fidelity(bare_usage, "", [profiles]))
    assert check_cited_span_fidelity("", customers, [profiles]) == []
    assert check_cited_span_fidelity("", who_used, [profiles]) == []
    assert check_cited_span_fidelity(accounts, "", [migration]) == []
    assert check_cited_span_fidelity(records, "", [dropoff]) == []
    assert check_cited_span_fidelity("", security, [backlog, risks]) == []
    assert check_cited_span_fidelity("", unrelated, [profiles]) == []


def test_LR043_blocks_taking_the_funnel_and_allows_the_split():
    spans = [
        "Built the landing page. Once it proved out, engineering built the funnel around it."
    ]
    taken = "I created a dedicated acquisition funnel and automated lead routing."
    split = (
        "I built the landing page, and engineering then built the automated funnel around it."
    )
    assert any(v.rule_id == "LR-043" for v in check_cited_span_fidelity("", taken, spans))
    assert check_cited_span_fidelity("", split, spans) == []
    intake = "* Built an intake and incident prioritization model in Jira."
    assert check_cited_span_fidelity(intake, "", spans) == []


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_LR044_blocks_nisum_2_empty_roles():
    """Fixture matches nisum_2 stage1_pre_repair: three role headings, zero bullets."""
    path = os.path.join(_repo_root(), "tests", "fixtures", "cr127_empty_roles_resume.md")
    text = open(path, encoding="utf-8").read()
    violations = check_experience_role_bullets(text)
    assert len(violations) == 3
    assert all(v.rule_id == "LR-044" for v in violations)
    filled = text.replace(
        "### Product Manager | Cision | September 2021 - January 2026\n",
        "### Product Manager | Cision | September 2021 - January 2026\n* Kept the contact records current.\n",
        1,
    ).replace(
        "### Product Manager / Product Owner | Sterkly | February 2019 - August 2021\n",
        "### Product Manager / Product Owner | Sterkly | February 2019 - August 2021\n* Wrote the certificate workflow.\n",
        1,
    ).replace(
        "### Account Manager / Product Owner | Zero To Sixty | June 2017 - January 2019\n",
        "### Account Manager / Product Owner | Zero To Sixty | June 2017 - January 2019\n* Built the landing page.\n",
        1,
    )
    assert check_experience_role_bullets(filled) == []


def test_LR045_requires_a_past_employer_paragraph():
    bare = (
        "Dear Hiring Manager,\n\n"
        "Investigating the pipeline mechanics revealed a silent data loss pattern.\n\n"
        "Best regards,\n"
    )
    assert any(v.rule_id == "LR-045" for v in check_letter_names_employer(bare))
    named = bare.replace(
        "Investigating the pipeline",
        "At Cision, investigating the pipeline",
    )
    assert check_letter_names_employer(named) == []


def test_LR046_blocks_data_model_and_allows_schema():
    bad = "I authored the requirements to restructure the underlying data model."
    assert any(v.rule_id == "LR-046" for v in check_data_model_phrase("", bad))
    ok = "I specified splitting the values into two columns and reading the schema directly."
    assert check_data_model_phrase(ok, "") == []


def test_LR047_requires_estimated_on_the_range_and_the_drafting_line():
    bare_money = "Earlier at Sterkly, I unlocked between $1M and $3M in blocked revenue."
    kept_money = "Sustained an estimated $1M to $3M in blocked product revenue."
    bare_time = (
        "Used AI to draft epics, reducing drafting time from two weeks to several days."
    )
    kept_time = (
        "Used AI to draft epics, reducing drafting time from about two weeks to a few days, "
        "his own estimate."
    )
    assert any(v.rule_id == "LR-047" for v in check_required_hedges("", bare_money))
    assert check_required_hedges("* " + kept_money, "") == []
    assert any(v.rule_id == "LR-047" for v in check_required_hedges("* " + bare_time, ""))
    assert check_required_hedges("* " + kept_time, "") == []


def test_LR049_blocks_a_cited_sentence_that_contradicts_the_fact():
    """FR-390: the cite is real and the sentence says something the fact does not."""
    inversion = "I prioritized profile portability over custom tagging."
    usage = "That change reached 25 percent of active usage."
    true_line = "Custom tagging took priority over making profiles portable."
    cited = {
        "cover_letter_claims": [
            {"sentence": inversion, "claim_ids": ["ACC-155"]},
            {"sentence": usage, "claim_ids": ["ACC-115"]},
            {"sentence": true_line, "claim_ids": ["ACC-155"]},
        ]
    }
    blocks = collect_fidelity_hard_blocks("", "\n\n".join([inversion, usage, true_line]), cited)
    assert any(v.rule_id == "LR-049" and "ACC-155" in v.message for v in blocks)
    assert any(v.rule_id == "LR-049" and "ACC-115" in v.message for v in blocks)
    assert not any(true_line[:40] in v.message for v in blocks if v.rule_id == "LR-049")
    other_fact = {
        "cover_letter_claims": [
            {"sentence": inversion, "claim_ids": ["ACC-104"]},
        ]
    }
    assert not any(
        v.rule_id == "LR-049"
        for v in collect_fidelity_hard_blocks("", inversion, other_fact)
    )
    assert not any(
        v.rule_id == "LR-049"
        for v in collect_fidelity_hard_blocks("", inversion)
    )
    credited = (
        "I influenced the landing page that enabled engineering to deploy "
        "an automated Salesforce onboarding funnel."
    )
    credited_prov = {
        "cover_letter_claims": [{"sentence": credited, "claim_ids": ["ACC-303"]}]
    }
    assert not any(
        v.rule_id == "LR-049"
        for v in collect_fidelity_hard_blocks("", credited, credited_prov)
    )
    took_funnel = "I automated lead capture and built the onboarding funnel."
    took_prov = {
        "cover_letter_claims": [{"sentence": took_funnel, "claim_ids": ["ACC-303"]}]
    }
    assert any(
        v.rule_id == "LR-049" and "ACC-303" in v.message
        for v in collect_fidelity_hard_blocks("", took_funnel, took_prov)
    )


def test_LR048_blocks_a_clean_cutover_that_drops_the_five_percent():
    bare = "The migration finished without service disruption."
    hedged = (
        "An estimated 95 percent of customers flipped, and about 5 percent never did, "
        "so the cutover was not without disruption for every account."
    )
    plain = "I aligned engineering on the rollout plan."
    bare_blocks = collect_fidelity_hard_blocks("", bare)
    assert any(v.rule_id == "LR-048" for v in bare_blocks)
    assert not any(v.rule_id == "LR-048" for v in collect_fidelity_hard_blocks("", hedged))
    assert not any(v.rule_id == "LR-048" for v in collect_fidelity_hard_blocks("* " + plain, ""))


def test_LR046_and_LR047_on_a_before_fix_copy():
    """Copy from data/review_evidence, never from data/submissions."""
    evidence = os.path.join(
        _repo_root(), "data", "review_evidence", "2026-09-23-before-fix"
    )
    medrisk = os.path.join(evidence, "bak_medrisk_CoverLetter.md")
    highmark = os.path.join(evidence, "bak_highmark_health_CoverLetter.md")
    candor = os.path.join(evidence, "bak_candor_health_Resume.md")
    if not (os.path.isfile(medrisk) and os.path.isfile(highmark) and os.path.isfile(candor)):
        raise unittest.SkipTest("before-fix evidence is not in this checkout")
    with tempfile.TemporaryDirectory() as tmp:
        medrisk_copy = os.path.join(tmp, "CoverLetter.md")
        highmark_copy = os.path.join(tmp, "HighmarkCover.md")
        candor_copy = os.path.join(tmp, "Resume.md")
        shutil.copyfile(medrisk, medrisk_copy)
        shutil.copyfile(highmark, highmark_copy)
        shutil.copyfile(candor, candor_copy)
        medrisk_text = open(medrisk_copy, encoding="utf-8").read()
        highmark_text = open(highmark_copy, encoding="utf-8").read()
        candor_text = open(candor_copy, encoding="utf-8").read()
    assert any(v.rule_id == "LR-046" for v in check_data_model_phrase("", medrisk_text))
    assert any(v.rule_id == "LR-047" for v in check_required_hedges("", highmark_text))
    candor_hits = check_required_hedges(candor_text, "")
    assert any("drafting-time line" in v.message for v in candor_hits)
    kept = "* Sustained an estimated $1M to $3M in blocked product revenue."
    assert check_required_hedges(kept, "") == []


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            suite.addTest(unittest.FunctionTestCase(value, description=name))
    return suite


if __name__ == "__main__":
    unittest.main()
