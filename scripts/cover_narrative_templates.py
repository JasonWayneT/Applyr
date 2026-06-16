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

    from cover_jd_needs import need_to_goal_phrase

    if rec.cover_story:
        story = rec.cover_story.strip()
        if not story.endswith("."):
            story += "."
        from cover_phrasing import apply_voice_polish

        return apply_voice_polish(story)

    body = format_cover_proof_sentence(rec.body)

    if slot.lens in ("migration", "platform", "lifecycle", "customer_success", "integration", "rebuild"):
        context = (
            "On a large B2B platform with legacy constraints, I focused on scalable migration "
            "and platform delivery without customer friction."
        )
    elif slot.lens in ("data", "technical", "security", "compliance"):
        context = "When data integrity threatened product quality and retention, I drove a cross-functional fix end to end."
    elif slot.lens in ("business", "gtm", "finance", "cost"):
        context = "Where revenue and retention were at risk, I prioritized fixes that protected the business outcome."
    elif slot.lens in ("roadmap", "execution", "leadership", "executive", "synthesis", "agile", "process", "pm", "delivery"):
        context = "Under tight capacity and competing mandates, I enforced prioritization that kept delivery on track."
    elif slot.lens in ("requirements",):
        context = "Working directly with cross-functional stakeholders, I translated business needs into engineering-ready specs."
    else:
        context = "In a complex cross-functional environment, I owned the problem through to measurable results."

    from cover_phrasing import apply_voice_polish

    return apply_voice_polish(f"{context} {body}")


def render_value_first_opening(
    company: str,
    role_title: str,
    primary_story: str,
    jd_text: str,
) -> str:
    """Value-first opener: application line + strongest story claim (CR-044 / FR-237)."""
    from cover_phrasing import (
        apply_voice_polish,
        dedupe_opening_paragraph,
        value_lead_from_story,
    )

    from cover_phrasing import render_trust_hook

    apply_line = f"I am applying for the {role_title} role at {company}."
    value_line = render_trust_hook(primary_story) or value_lead_from_story(primary_story)
    parts = [p for p in (apply_line, value_line) if p]
    return apply_voice_polish(dedupe_opening_paragraph(" ".join(parts)))


def render_application_first_opening(
    company: str,
    role_title: str,
    ranked_need: str,
    themes: list,
    jd_text: str,
    primary_story: str = "",
) -> str:
    """Backward-compatible entry; prefers value-first when a cover_story is available."""
    if primary_story:
        return render_value_first_opening(company, role_title, primary_story, jd_text)
    apply_line = f"I am applying for the {role_title} role at {company}."
    from cover_phrasing import apply_voice_polish

    return apply_voice_polish(apply_line)


# Backward-compatible alias (CR-024 plan field name)
render_problem_first_opening = render_application_first_opening
