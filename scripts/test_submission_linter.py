"""Tests for submission_linter.py — Epic 1, Story 1.8."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from submission_linter import lint_document, LintResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CL_CLEAN = """# JASON TAYLOR
[REDACTED_EMAIL]

Dear Hiring Manager,

HubSpot's shift toward product-led growth created a specific kind of product problem: the platform had to earn adoption from users who hadn't been sold to yet.

At Cision, on a $40M ARR B2B platform, that was the kind of problem I was responsible for solving. I partnered with engineering, DBA, and DevOps to eliminate a 40% data drop-off that was eroding customer trust and contributing to churn.

The data remediation work required coordinating across Legal, InfoSec, and Account Management while managing competing roadmap priorities. I treated the contact data failures as a product trust problem, not a minor bug, and drove the fix end-to-end.

I welcome the opportunity to discuss how this experience maps to the platform challenges in this role.

Best regards,

Jason Taylor
"""

RESUME_CLEAN = """# JASON TAYLOR
[REDACTED_EMAIL]

## PROFESSIONAL SUMMARY

Product Manager with 6 years across B2B SaaS platforms. Owned data integrity, platform stability, and cross-functional delivery on a $40M ARR media monitoring platform supporting 3,500 enterprise accounts.

## PROFESSIONAL EXPERIENCE

### Product Manager | Cision | Sep 2021 - Jan 2026

Full Remote, San Diego, CA

* Eliminated a 40% contact data drop-off by driving a centralized data remediation initiative coordinated with Engineering, DBA, and DevOps.
* Resolved 90% of a 300-item security backlog through risk-weighted prioritization, maintaining core roadmap delivery.
* Enabled 700 voluntary account migrations using phased tooling built with Customer Experience and Account Management.

### Product Manager | Sterkly Services | Feb 2019 - Aug 2021

* Resolved a critical certificate distribution bottleneck for a macOS security product, sustaining an estimated $1M-$3M in product revenue.

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


def test_LR007_blocks_redacted_phone():
    text = CL_CLEAN.replace("[REDACTED_EMAIL]", "[REDACTED_PHONE]")
    r = lint_document(text, "cover_letter")
    assert not r.passed
    assert any(v.rule_id == "LR-007" for v in r.blocks)


def test_LR008_blocks_redacted_email():
    text = CL_CLEAN.replace("[REDACTED_EMAIL]", "[REDACTED_EMAIL]")
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
    r = lint_document(CL_CLEAN, "cover_letter")
    assert not any(v.rule_id == "LW-001" for v in r.warns)


def test_LW002_warns_on_long_resume():
    long_resume = RESUME_CLEAN + ("\n* " + "Managed platform deliverables with cross-functional teams across multiple quarters. " * 30)
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
