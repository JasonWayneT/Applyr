from audit_improve_native import apply_claude_native_improvement

MASTER_RESUME = """
Jason Taylor - Product Manager
Cision: owned a $40M ARR platform, reduced data drop-off from 40% to zero,
resolved 90% of a 300-item security backlog, migrated 700 accounts.
"""

BULLETS = """
Owned a $40M ARR B2B SaaS platform serving 25,000 users.
Reduced contact data drop-off from 40% to zero via a rebuilt ETL pipeline.
Resolved 90% of a 300-item security vulnerability backlog.
"""

GOOD_SUMMARY = (
    "Senior Product Manager with 6 years of B2B SaaS platform experience. "
    "Partners closely with Engineering and DevOps to stabilize legacy systems "
    "under resource constraints. Reduced contact data drop-off from 40% to zero "
    "on a $40M ARR platform."
)

FABRICATED_SUMMARY = (
    "Senior Product Manager with 6 years of B2B SaaS platform experience. "
    "Grew platform revenue by 250% through aggressive expansion. "
    "Reduced contact data drop-off from 40% to zero on a $40M ARR platform."
)

TWO_SENTENCE_SUMMARY = (
    "Senior Product Manager with 6 years of B2B SaaS platform experience. "
    "Reduced contact data drop-off from 40% to zero on a $40M ARR platform."
)

GOOD_COVER_LETTER = (
    "Dear Hiring Manager,\n\nYour platform reliability challenge is one I've "
    "solved before. At Cision, I reduced contact data drop-off from 40% to "
    "zero on a $40M ARR platform by rebuilding the ETL pipeline.\n\nRegards,\nJason Taylor\n"
)

FABRICATED_COVER_LETTER = (
    "Dear Hiring Manager,\n\nYour platform reliability challenge is one I've "
    "solved before. At Cision, I grew revenue by 250% and reduced churn to 2%.\n\n"
    "Regards,\nJason Taylor\n"
)


def test_accepts_good_content_and_converges():
    result = apply_claude_native_improvement(
        context={"company_stage": "Growth", "product_motion": "Enterprise B2B SaaS"},
        new_summary=GOOD_SUMMARY,
        new_cover_letter=GOOD_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is True
    assert result.final_issues == []


def test_rejects_fabricated_summary_metric():
    result = apply_claude_native_improvement(
        context={"company_stage": "Growth", "product_motion": "Enterprise B2B SaaS"},
        new_summary=FABRICATED_SUMMARY,
        new_cover_letter=GOOD_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is False
    assert any("250" in issue or "metric" in issue.lower() for issue in result.final_issues)


def test_rejects_fabricated_cover_letter_metric():
    result = apply_claude_native_improvement(
        context={"company_stage": "Growth", "product_motion": "Enterprise B2B SaaS"},
        new_summary=GOOD_SUMMARY,
        new_cover_letter=FABRICATED_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is False
    assert any("250" in issue or "2" in issue for issue in result.final_issues)


def test_rejects_wrong_sentence_count_summary():
    result = apply_claude_native_improvement(
        context={"company_stage": "Growth", "product_motion": "Enterprise B2B SaaS"},
        new_summary=TWO_SENTENCE_SUMMARY,
        new_cover_letter=GOOD_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is False
    assert any("sentence" in issue.lower() for issue in result.final_issues)
