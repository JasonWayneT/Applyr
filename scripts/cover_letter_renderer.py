"""Render CoverLetterPlan to markdown (CR-024 / FR-097; voice CR-043; structure CR-047)."""
from __future__ import annotations

import re
from typing import Tuple

from claim_catalog import ClaimCatalog
from cover_letter_plan import CoverLetterPlan
from cover_phrasing import CHAR_MAX, WORD_MAX, WORD_MIN, apply_voice_polish

COVER_PAGE_CHAR_LIMIT = 2600
from quality_checker import HEADER_BLOCK


def _word_count(body: str) -> int:
    return len(re.findall(r"\b\w+\b", body))


def _trim_words(text: str, target_reduction: int) -> str:
    """Remove filler phrases to approach word budget (never strip metrics)."""
    fillers = (
        " directly",
        " measurable",
        " end to end",
    )
    out = text
    for f in fillers:
        if target_reduction <= 0:
            break
        if f in out:
            out = out.replace(f, "", 1)
            target_reduction -= 1
    return re.sub(r"\s+", " ", out).strip()


def _render_block_letter(
    plan: CoverLetterPlan, catalog: ClaimCatalog, jd_text: str
) -> str:
    from cover_letter_structure import build_cover_blocks, blocks_to_prose

    blocks = build_cover_blocks(plan, catalog, jd_text)
    body_text = blocks_to_prose(blocks)
    wc = _word_count(body_text)
    if wc > WORD_MAX:
        excess = wc - WORD_MAX
        prose_parts = body_text.split("\n\n")
        if len(prose_parts) > 2:
            prose_parts = [
                prose_parts[0],
                *[
                    _trim_words(
                        p, min(3, excess // max(len(prose_parts) - 2, 1))
                    )
                    for p in prose_parts[1:-1]
                ],
                prose_parts[-1],
            ]
            body_text = "\n\n".join(prose_parts)

    if len(body_text) > CHAR_MAX:
        prose_parts = body_text.split("\n\n")
        if len(prose_parts) > 2:
            body_text = "\n\n".join([prose_parts[0], *prose_parts[1:-1], prose_parts[-1]])

    if len(body_text) > COVER_PAGE_CHAR_LIMIT:
        parts = body_text.split("\n\n")
        while len("\n\n".join(parts)) > COVER_PAGE_CHAR_LIMIT and len(parts) > 2:
            drop_idx = min(range(1, len(parts) - 1), key=lambda i: len(parts[i]))
            parts.pop(drop_idx)
        body_text = "\n\n".join(parts)

    from utils import load_identity_profile

    salutation = "Dear Hiring Manager,"
    candidate_name = (load_identity_profile().get("name") or "Candidate").strip()
    signoff = f"Best regards,\n\n{candidate_name}"
    letter = f"{HEADER_BLOCK.strip()}\n\n{salutation}\n\n{body_text}\n\n{signoff}\n"
    return apply_voice_polish(letter)


def render_cover_letter(
    plan: CoverLetterPlan, catalog: ClaimCatalog, jd_text: str = ""
) -> str:
    return _render_block_letter(plan, catalog, jd_text)


def word_count_report(markdown: str) -> Tuple[int, bool]:
    body = (
        markdown.split("Dear Hiring Manager,")[-1]
        if "Dear Hiring Manager" in markdown
        else markdown
    )
    wc = _word_count(body)
    return wc, WORD_MIN <= wc <= WORD_MAX
