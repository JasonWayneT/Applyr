from audit_improve_native import apply_claude_native_improvement

MASTER_RESUME = """# Jason Taylor

Jason Taylor - Product Manager
Cision: owned a $40M ARR platform, reduced data drop-off from 40% to zero,
resolved 90% of a 300-item security backlog, migrated 700 accounts.
"""

BULLETS = """
Owned a $40M ARR B2B SaaS platform serving 25,000 users.
Reduced contact data drop-off from 40% to zero via a rebuilt ETL pipeline.
Resolved 90% of a 300-item security vulnerability backlog.
"""

RESUME_HEADER = (
    "# Jason Taylor\n\n"
    "[REDACTED_EMAIL] | linkedin.com/in/jasontaylor\n\n"
)

RESUME_BODY_TAIL = (
    "\n\n## PROFESSIONAL EXPERIENCE\n\n"
    "### Product Manager | Cision | 2019 - 2023\n\n"
    "San Diego, CA\n\n"
    "* Owned a $40M ARR B2B SaaS platform serving 25,000 users.\n"
    "* Reduced contact data drop-off from 40% to zero via a rebuilt ETL pipeline.\n"
    "* Resolved 90% of a 300-item security vulnerability backlog.\n\n"
    "## EDUCATION\n\n"
    "* Bachelor of Business Administration, National University, San Diego, California, 2019\n"
)

CL_HEADER = (
    "# Jason Taylor\n\n"
    "[REDACTED_EMAIL] | linkedin.com/in/jasontaylor\n\n"
)

CL_TAIL = "\n\nRegards,\n\nJason Taylor\n"


def _build_resume(summary: str) -> str:
    return f"{RESUME_HEADER}## PROFESSIONAL SUMMARY\n\n{summary}{RESUME_BODY_TAIL}"


def _build_cover_letter(body: str) -> str:
    return f"{CL_HEADER}Dear Hiring Manager,\n\n{body}{CL_TAIL}"


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

GOOD_COVER_LETTER_BODY = (
    "Your platform reliability challenge is one I've solved before. At Cision, "
    "I reduced contact data drop-off from 40% to zero on a $40M ARR platform "
    "by rebuilding the ETL pipeline."
)

FABRICATED_COVER_LETTER_BODY = (
    "Your platform reliability challenge is one I've solved before. At Cision, "
    "I grew revenue by 250% and reduced churn to 2%."
)

GOOD_RESUME = _build_resume(GOOD_SUMMARY)
FABRICATED_SUMMARY_RESUME = _build_resume(FABRICATED_SUMMARY)
TWO_SENTENCE_RESUME = _build_resume(TWO_SENTENCE_SUMMARY)

GOOD_COVER_LETTER = _build_cover_letter(GOOD_COVER_LETTER_BODY)
FABRICATED_COVER_LETTER = _build_cover_letter(FABRICATED_COVER_LETTER_BODY)


def test_accepts_good_content_and_converges():
    result = apply_claude_native_improvement(
        updated_resume=GOOD_RESUME,
        updated_cl=GOOD_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is True
    assert result.final_issues == []
    assert result.corrected_resume != ""
    assert result.corrected_cover_letter != ""


def test_rejects_fabricated_summary_metric():
    result = apply_claude_native_improvement(
        updated_resume=FABRICATED_SUMMARY_RESUME,
        updated_cl=GOOD_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is False
    assert any("250" in issue or "metric" in issue.lower() for issue in result.final_issues)


def test_rejects_fabricated_cover_letter_metric():
    result = apply_claude_native_improvement(
        updated_resume=GOOD_RESUME,
        updated_cl=FABRICATED_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is False
    assert any("250" in issue for issue in result.final_issues)


def test_rejects_wrong_sentence_count_summary():
    result = apply_claude_native_improvement(
        updated_resume=TWO_SENTENCE_RESUME,
        updated_cl=GOOD_COVER_LETTER,
        master_resume_text=MASTER_RESUME,
        bullets=BULLETS,
        company_name="TestCo",
    )
    assert result.converged is False
    assert any("sentence" in issue.lower() for issue in result.final_issues)
