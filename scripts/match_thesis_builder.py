"""Match thesis and interest-via-match lines (CR-024)."""
from __future__ import annotations

from typing import List

from cover_letter_plan import CoverLetterPlan
from cover_prose import format_themes_for_prose, posting_focus_phrase
from jd_tailoring import JdProfile


def build_match_thesis(
    company: str,
    role_title: str,
    ranked_needs: List[str],
    themes: List[str],
) -> str:
    return (
        f"I have operated in similar B2B platform environments where roadmap discipline, "
        f"structured data, and cross-functional delivery determined whether initiatives scaled."
    )


def build_interest_via_match(
    company: str,
    role_title: str,
    ranked_needs: List[str],
    themes: List[str],
    jd_text: str = "",
) -> str:
    """Stored on plan for traceability; opening renderer folds this into application_first block."""
    theme_str = format_themes_for_prose(themes, max_items=2)
    focus = posting_focus_phrase(jd_text) if jd_text else "platform scale, structured data, and execution"
    return (
        f"Applying for {role_title} at {company}; posting focus on {focus}; "
        f"track record in {theme_str}."
    )


def apply_match_blocks(
    plan: CoverLetterPlan, profile: JdProfile, jd_text: str = ""
) -> CoverLetterPlan:
    themes = profile.priority_themes[:3] or ["B2B SaaS product execution"]
    plan.match_thesis = build_match_thesis(
        plan.company_display, plan.role_title, plan.ranked_needs, themes
    )
    plan.interest_via_match = build_interest_via_match(
        plan.company_display, plan.role_title, plan.ranked_needs, themes, jd_text=jd_text
    )
    plan.theme_keywords = themes[:3]
    return plan
