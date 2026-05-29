"""Micro-narrative slot rendering from claims (CR-024)."""
from __future__ import annotations

import re
from typing import Tuple

from claim_catalog import ClaimCatalog
from claim_composer import format_cover_proof_sentence
from cover_letter_plan import CoverProofSlot


def _first_metric_clause(text: str) -> str:
    m = re.search(
        r"([^,.]*(?:\d+%|~\d+|\$[\d,]+|saved \$[\d,]+)[^,.]*[,.]?)",
        text,
        re.I,
    )
    return m.group(1).strip().rstrip(",") if m else ""


def _short_need(need: str, max_len: int = 90) -> str:
    from cover_jd_needs import need_to_goal_phrase

    return need_to_goal_phrase(need)[:max_len].rstrip(",")


def render_proof_paragraph(
    slot: CoverProofSlot,
    catalog: ClaimCatalog,
    company: str,
) -> str:
    rec = catalog.claims.get(slot.claim_id)
    if not rec:
        return ""
    body = format_cover_proof_sentence(rec.body)
    from cover_jd_needs import need_to_goal_phrase

    need_phrase = need_to_goal_phrase(slot.jd_need)
    metric = _first_metric_clause(rec.body)

    if metric and metric.lower() not in body.lower():
        action = body
    else:
        action = body

    bridge = (
        f"That experience is directly relevant to {company}'s focus on {need_phrase}, "
        f"and to the platform outcomes this role owns."
    )

    if slot.lens in ("migration", "platform", "lifecycle", "customer_success"):
        context = (
            "On a large B2B platform with legacy constraints, I focused on scalable migration "
            "and platform delivery without customer friction."
        )
    elif slot.lens in ("data", "technical"):
        context = "When data integrity threatened product quality and retention, I drove a cross-functional fix end to end."
    elif slot.lens in ("business", "gtm", "finance"):
        context = "Where revenue and retention were at risk, I prioritized fixes that protected the business outcome."
    elif slot.lens in ("roadmap", "execution", "leadership"):
        context = "Under tight capacity and competing mandates, I enforced prioritization that kept delivery on track."
    else:
        context = "In a complex cross-functional environment, I owned the problem through to measurable results."

    return f"{context} {action} {bridge}"


def render_application_first_opening(
    company: str,
    role_title: str,
    ranked_need: str,
    themes: list,
    jd_text: str,
) -> str:
    """Application-first opener: state intent, then JD match (never 'Company is hiring…')."""
    from cover_jd_needs import need_to_goal_phrase
    from cover_prose import format_themes_for_prose, posting_focus_phrase

    theme_str = format_themes_for_prose(themes, max_items=2)
    focus = posting_focus_phrase(jd_text) if jd_text else "platform scale, structured data, and execution"
    need_hint = need_to_goal_phrase(ranked_need) if ranked_need else ""

    if need_hint and 20 < len(need_hint) < 90:
        apply_line = (
            f"I am applying for the {role_title} role at {company}, "
            f"with direct experience in {need_hint}."
        )
    else:
        apply_line = f"I am applying for the {role_title} role at {company}."

    match_line = (
        f"Your posting emphasizes {focus}; "
        f"that aligns with my track record in {theme_str}."
    )
    return f"{apply_line} {match_line}"


# Backward-compatible alias (CR-024 plan field name)
render_problem_first_opening = render_application_first_opening
