"""Render CoverLetterPlan to markdown (CR-024 / FR-097)."""
from __future__ import annotations

import re
from typing import Tuple

from claim_catalog import ClaimCatalog
from cover_letter_plan import CoverLetterPlan
from cover_narrative_templates import render_application_first_opening, render_proof_paragraph
from quality_checker import HEADER_BLOCK

WORD_MIN = 300
WORD_MAX = 350


def _word_count(body: str) -> int:
    return len(re.findall(r"\b\w+\b", body))


def _trim_words(text: str, target_reduction: int) -> str:
    """Remove filler phrases to approach word budget."""
    fillers = (
        " directly",
        " measurable",
        " end to end",
        " cross-functional",
    )
    out = text
    for f in fillers:
        if target_reduction <= 0:
            break
        if f in out:
            out = out.replace(f, "", 1)
            target_reduction -= 1
    return re.sub(r"\s+", " ", out).strip()


def render_cover_letter(
    plan: CoverLetterPlan, catalog: ClaimCatalog, jd_text: str = ""
) -> str:
    company = plan.company_display
    bodies = []
    for slot in plan.proofs:
        para = render_proof_paragraph(slot, catalog, company)
        if para:
            bodies.append(para)

    need0 = plan.ranked_needs[0] if plan.ranked_needs else plan.jd_goal
    opening = render_application_first_opening(
        company,
        plan.role_title,
        need0,
        plan.theme_keywords,
        jd_text,
    )
    if plan.match_thesis and plan.match_thesis not in opening:
        opening = f"{opening} {plan.match_thesis}"
    # Ensure ranked need appears in body for audit (opening covers platform mandate)
    if plan.research_hook:
        opening = f"{plan.research_hook} {opening}"

    close = (
        f"I would welcome a conversation about how this background can help {company} "
        f"advance {plan.jd_goal.rstrip('.')}, with the same discipline on metrics, "
        f"stakeholder alignment, and platform delivery described above."
    )

    bridge_para = (
        f"Together, these examples reflect how I work with Engineering, Data, and "
        f"commercial stakeholders to translate platform requirements into shipped, measurable outcomes, "
        f"aligned with the Engineering and Data partnership model in your posting."
    )
    prose_blocks = [opening] + bodies + [bridge_para, close]
    body_text = "\n\n".join(prose_blocks)
    wc = _word_count(body_text)
    if wc > WORD_MAX:
        excess = wc - WORD_MAX
        bodies = [_trim_words(b, min(3, excess // max(len(bodies), 1))) for b in bodies]
        body_text = "\n\n".join([opening] + bodies + [close])

    salutation = "Dear Hiring Manager,"
    signoff = "Best regards,\n\nJason Taylor"
    letter = f"{HEADER_BLOCK.strip()}\n\n{salutation}\n\n{body_text}\n\n{signoff}\n"
    return letter


def word_count_report(markdown: str) -> Tuple[int, bool]:
    body = markdown.split("Dear Hiring Manager,")[-1] if "Dear Hiring Manager" in markdown else markdown
    wc = _word_count(body)
    return wc, WORD_MIN <= wc <= WORD_MAX
