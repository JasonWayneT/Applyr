#!/usr/bin/env python3
"""Shadow Stage 0 evidence matcher (CR-114 Story 4 / FR-329).

Reviewed aliases may propose a match. Anything unreviewed, generic, or
ambiguous abstains. This module cannot emit HARD or Skip and is not wired
into the production cascade.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Decision = Literal["match", "abstain"]
TERMINAL_FORBIDDEN = {"HARD", "SKIP", "skip", "hard"}


@dataclass(frozen=True)
class ReviewedCase:
    case_id: str
    aliases: tuple[str, ...]
    reviewed_by: str
    reviewed_at: str
    kind: str = "tool"


TOOL_SINGLE_WORDS = {"jira", "sql", "pendo", "amplitude"}


@dataclass(frozen=True)
class MatchResult:
    decision: Decision
    case_id: str | None
    matched_alias: str | None
    reason: str


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _phrase_in(phrase: str, text: str) -> bool:
    if not phrase:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, flags=re.I))


def load_reviewed_cases(path: Path | None) -> list[ReviewedCase]:
    """Load human-reviewed aliases only. Missing or malformed files abstain later."""
    if path is None or not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    cases: list[ReviewedCase] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        reviewer = str(row.get("reviewed_by") or "").strip()
        reviewed_at = str(row.get("reviewed_at") or "").strip()
        if not reviewer or not reviewed_at:
            continue
        if reviewer.lower() in {"model", "llm", "harness", "fallback_api", "feedbackloop"}:
            continue
        case_id = str(row.get("id") or row.get("case_id") or "").strip()
        aliases = tuple(
            _norm(alias)
            for alias in (row.get("aliases") or [])
            if isinstance(alias, str) and _norm(alias)
        )
        if not case_id or not aliases:
            continue
        kind = str(row.get("kind") or "tool").strip().lower()
        if kind != "tool":
            continue
        cases.append(ReviewedCase(case_id, aliases, reviewer, reviewed_at, kind))
    return cases


def match_requirement(
    requirement: str,
    evidence_excerpt: str,
    cases: list[ReviewedCase],
) -> MatchResult:
    """Return match or abstain. Implements FR-329 / AC-427. Never HARD or Skip."""
    req = _norm(requirement)
    evidence = _norm(evidence_excerpt)
    if not req or not evidence or not cases:
        return MatchResult("abstain", None, None, "insufficient reviewed evidence")
    hits: list[tuple[str, str]] = []
    for case in cases:
        for alias in case.aliases:
            if " " not in alias and alias not in TOOL_SINGLE_WORDS:
                continue
            if case.kind != "tool":
                continue
            if _phrase_in(alias, req) and _phrase_in(alias, evidence):
                hits.append((case.case_id, alias))
    unique_cases = {case_id for case_id, _alias in hits}
    if len(unique_cases) != 1:
        return MatchResult("abstain", None, None, "ambiguous or unmatched reviewed alias")
    case_id, alias = hits[0]
    return MatchResult("match", case_id, alias, "reviewed alias present in requirement and evidence")


def as_shadow_row(result: MatchResult) -> dict[str, Any]:
    """JSON-safe shadow record. Terminal gate fields are intentionally absent."""
    row = {
        "decision": result.decision,
        "case_id": result.case_id,
        "matched_alias": result.matched_alias,
        "reason": result.reason,
    }
    for forbidden in TERMINAL_FORBIDDEN:
        if forbidden in row.values() or forbidden == result.decision:
            raise RuntimeError("evidence matcher must not emit HARD or Skip")
    return row
