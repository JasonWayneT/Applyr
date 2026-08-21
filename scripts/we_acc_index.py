"""
CR-094/CR-095: classify workExperience.md bracket ACC ids and attach hedges.

WE uses [ACC-N] for stories, documentation substories, not-owned/not-implemented
lines, Attribution, DO NOT CLAIM, and ACC-119 tools. Only story-class ids are
indexable in master_claims.json. Substories ride in the parent WE excerpt.

# Implements CR-094, CR-095
"""
from __future__ import annotations

import re
from typing import Any

CLASS_STORY = "story"
CLASS_SUBSTORY = "substory"
CLASS_NONCLAIMABLE = "nonclaimable"
CLASS_ATTRIBUTION = "attribution"
CLASS_DO_NOT_CLAIM = "do_not_claim"
CLASS_TOOLS = "tools"

_BRACKET_ACC_RE = re.compile(r"\[(ACC-\d+)\]")
_ATTRIBUTION_TIER_RE = re.compile(
    r"\b(OWNED|CONTRIBUTED|INFLUENCED)\b", re.IGNORECASE
)
_TOOLS_PROJECT_ID = "ACC-119"

# Documentation breakdowns of a parent story (Problem / What Jason did / …).
_SUBSTORY_PREFIX_RE = re.compile(
    r"^(?:"
    r"What Jason (?:drove|did)"
    r"|Problem:"
    r"|Outcome:"
    r"|Context:"
    r"|Owned:"
    r"|Primary(?: use)?:\s"
    r"|Primary\s*\("
    r"|Secondary:"
    r"|Secondary\s*\("
    r"|Also used for:"
    r"|How:"
    r"|Cross-cutting:"
    r"|Failure mode prevented:"
    r"|Prioritization:"
    r"|Ingestion/enrichment"
    r"|Embedded product ownership"
    r"|Hands-on export extraction"
    r"|Origin of the tooling"
    r"|Post-departure status"
    r"|AI-assisted query writing"
    r"|Scaling Trade-Off"
    r")",
    re.IGNORECASE,
)

_NONCLAIMABLE_RE = re.compile(
    r"(?:"
    r"^Not owned:"
    r"|Not Implemented"
    r"|unconfirmed"
    r"|Not Completed"
    r"|Considered,\s*Not Implemented"
    r"|Role context,\s*not a resume (?:bullet|story)"
    r")",
    re.IGNORECASE,
)


def _line_at(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index)
    start = 0 if start < 0 else start + 1
    end = text.find("\n", index)
    return text[start:] if end < 0 else text[start:end]


def _title_after_acc(line: str) -> str:
    """Plain title after the [ACC-N] marker (markdown stripped)."""
    m = re.search(r"\[ACC-\d+\]\s*(.*)$", line or "")
    rest = m.group(1) if m else (line or "")
    return re.sub(r"\*+", "", rest).strip()


def classify_we_acc_ids(we_text: str) -> dict[str, str]:
    """Map each bracket ACC id in WE to a class constant.

    Args:
        we_text: Full workExperience.md (or a fixture). Must not be logged if it
            contains §1.0 PII; this function only returns ids and class labels.

    Returns:
        ACC id → class constant. Last occurrence wins if an id repeats.
    """
    classes: dict[str, str] = {}
    for match in _BRACKET_ACC_RE.finditer(we_text or ""):
        acc = match.group(1)
        line = _line_at(we_text, match.start())
        line_u = line.upper()
        title = _title_after_acc(line)
        if acc == _TOOLS_PROJECT_ID or "TOOLS USED" in line_u:
            classes[acc] = CLASS_TOOLS
        elif re.search(r"\]\s*\*?\s*Attribution\b", line, re.I) or title.upper().startswith(
            "ATTRIBUTION"
        ):
            classes[acc] = CLASS_ATTRIBUTION
        elif re.search(r"\]\s*\*?\s*DO NOT CLAIM\b", line, re.I) or title.upper().startswith(
            "DO NOT CLAIM"
        ):
            classes[acc] = CLASS_DO_NOT_CLAIM
        elif _NONCLAIMABLE_RE.search(title):
            classes[acc] = CLASS_NONCLAIMABLE
        elif _SUBSTORY_PREFIX_RE.search(title):
            classes[acc] = CLASS_SUBSTORY
        else:
            classes[acc] = CLASS_STORY
    return classes


def indexable_project_ids(we_text: str) -> set[str]:
    """Story-class ACC ids that belong in the claims index.

    Args:
        we_text: WE markdown or fixture.

    Returns:
        Set of ACC-N story ids. Substories, not-owned lines, tools,
        attribution, and DNC ids are excluded.
    """
    return {
        acc
        for acc, kind in classify_we_acc_ids(we_text).items()
        if kind == CLASS_STORY
    }


def _ordered_brackets(we_text: str) -> list[tuple[str, int, str]]:
    """Return (acc_id, start_index, line) in document order."""
    out: list[tuple[str, int, str]] = []
    for match in _BRACKET_ACC_RE.finditer(we_text or ""):
        acc = match.group(1)
        out.append((acc, match.start(), _line_at(we_text, match.start())))
    return out


def story_span_end(we_text: str, project_id: str, start_idx: int) -> int:
    """Index in we_text where this story's excerpt should stop.

    Includes following substory / attribution / DNC lines. Stops before the next
    story, tools, or nonclaimable ACC (not-owned / not-implemented siblings are
    not part of this story's evidence).

    Args:
        we_text: WE markdown or fixture.
        project_id: Story ACC whose span started at start_idx (marker position).
        start_idx: Character offset of this project's [ACC-N] marker.

    Returns:
        Exclusive end offset. len(we_text) if no later boundary exists.
    """
    classes = classify_we_acc_ids(we_text)
    stop_kinds = {CLASS_STORY, CLASS_TOOLS, CLASS_NONCLAIMABLE}
    for match in _BRACKET_ACC_RE.finditer(we_text[start_idx + 1 :]):
        acc = match.group(1)
        if acc == project_id:
            continue
        kind = classes.get(acc)
        if kind in stop_kinds:
            abs_pos = start_idx + 1 + match.start()
            line_start = we_text.rfind("\n", 0, abs_pos)
            return line_start if line_start > start_idx else abs_pos
    return len(we_text or "")


def hedges_for_project(we_text: str, project_id: str) -> dict[str, Any]:
    """Attribution enum + prohibited lines attached to a story ACC.

    Sibling Attribution / DO NOT CLAIM / not-owned lines after the story,
    walking through substories, until the next story (or tools) block.

    Args:
        we_text: WE markdown or fixture.
        project_id: Story ACC (e.g. ACC-101).

    Returns:
        Dict with attribution (str) and prohibited_claims (list[str]).
    """
    empty: dict[str, Any] = {"attribution": "", "prohibited_claims": []}
    if not we_text or not project_id:
        return empty

    classes = classify_we_acc_ids(we_text)
    brackets = _ordered_brackets(we_text)
    start_at: int | None = None
    for i, (acc, _idx, _line) in enumerate(brackets):
        if acc == project_id and classes.get(acc) == CLASS_STORY:
            start_at = i
            break
    if start_at is None:
        return empty

    attribution = ""
    prohibited: list[str] = []
    for acc, _idx, line in brackets[start_at + 1 :]:
        kind = classes.get(acc)
        # Substories keep walking; stop at next story / tools / not-implemented sibling.
        if kind in (CLASS_STORY, CLASS_TOOLS, CLASS_NONCLAIMABLE):
            break
        if kind == CLASS_ATTRIBUTION:
            found = _ATTRIBUTION_TIER_RE.search(line)
            if found:
                attribution = found.group(1).upper()
        elif kind == CLASS_DO_NOT_CLAIM:
            clipped = re.split(r"DO NOT CLAIM:\s*", line, maxsplit=1, flags=re.I)
            body = clipped[1].strip() if len(clipped) > 1 else line.strip()
            body = re.sub(r"\*+", "", body).strip()
            if body:
                prohibited.append(body)

    return {"attribution": attribution, "prohibited_claims": prohibited}


def non_story_acc_ids(we_text: str) -> set[str]:
    """ACC ids that must not be treated as accomplishments (audit / provenance).

    Args:
        we_text: WE markdown or fixture.

    Returns:
        Attribution, DO NOT CLAIM, tools, and not-owned/not-implemented ACC ids.
        Substory ids stay citable (they are real facts under a parent story).
    """
    skip = {
        CLASS_ATTRIBUTION,
        CLASS_DO_NOT_CLAIM,
        CLASS_TOOLS,
        CLASS_NONCLAIMABLE,
    }
    return {
        acc
        for acc, kind in classify_we_acc_ids(we_text).items()
        if kind in skip
    }
