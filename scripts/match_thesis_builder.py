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
    """Deprecated — value-first opener carries fit; avoid stacking JD mirror sentences."""
    return ""


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
    plan: CoverLetterPlan,
    profile: JdProfile,
    jd_text: str = "",
    bullet_corpus: str = "",
) -> CoverLetterPlan:
    all_themes = profile.priority_themes[:6] or ["B2B SaaS product execution"]
    from experience_theme_guard import (
        build_transferable_bridge,
        filter_experience_backed_themes,
    )

    backed = (
        filter_experience_backed_themes(all_themes, bullet_corpus)
        if bullet_corpus.strip()
        else all_themes[:3]
    )
    resume_themes = backed[:3] or all_themes[:2]
    plan.match_thesis = build_match_thesis(
        plan.company_display, plan.role_title, plan.ranked_needs, resume_themes
    )
    plan.interest_via_match = build_interest_via_match(
        plan.company_display,
        plan.role_title,
        plan.ranked_needs,
        resume_themes,
        jd_text=jd_text,
    )
    plan.theme_keywords = all_themes[:3]
    return plan
