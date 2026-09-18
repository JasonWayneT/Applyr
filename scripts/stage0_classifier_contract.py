#!/usr/bin/env python3
"""Applyr Stage 0 classifier contract (CR-114 / FR-328).

This module is Applyr behavior: what a leftover extraction line or evidence
item is, which fields must come back, and how HARD is allowed to be used.
Providers (Groq, Gemini, Cursor, Claude, Codex, Agy, local) are tools. They
do not own this packet. Transports must send this text and validate this JSON.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

EXTRACTION_BUCKETS = ("required", "preferred", "responsibilities", "culture", "junk")
EVIDENCE_GATES = ("HARD", "NONE")
EVIDENCE_SOURCES = (
    "",
    "domain",
    "tool",
    "skill",
    "seniority",
    "people",
    "zero_to_one",
    "degree",
    "role_exclusion",
    "certification",
)
SCHEMA_VERSION = "stage0-classifier-v3"

EXTRACTION_SYSTEM = (
    "You are labeling job-description lines for Applyr Stage 0. "
    "Output JSON only. Do not explain. Do not invent item_ids. "
    "Do not use tools. Do not read files. Classify only from this prompt."
)

EXTRACTION_USER_PREFIX = (
    "Classify each Stage 0 job-description line into exactly one bucket: "
    "required, preferred, responsibilities, culture, or junk. "
    'Return JSON {"results":[{"item_id":"...","bucket":"..."}]} '
    "with one result per listed item_id. Do not invent item_ids. "
    "Responsibilities are duties with an action (owns, drives, builds, ships). "
    "Checkable qualifications with no duty verb are required, or preferred if "
    "the JD hedges them, never responsibilities: shipped X, track record, "
    "working knowledge, hands-on with named tools, recognized expertise, years, "
    "or 'core requirement'. "
    "Personality, habits, enthusiasm, or 'you are a person who' lines are "
    "culture, never required. Nobody can document 'loves storytelling'. "
    "Culture is also company mission, values, or how the team works: hook material. "
    "Junk is scraper chrome, orphan headings, EEO/legal/salary boilerplate, "
    "or tracking tags. Never use junk when unsure."
)

_CHECKABLE_QUAL_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:has|have)\s+(?:shipped|built|been|led|owned|delivered)\b|"
    r"\btrack\s+record\b|"
    r"\bworking\s+knowledge\b|"
    r"\bhands-?on\b|"
    r"\brecognized\s+as\s+an?\s+expert\b|"
    r"\bcore\s+requirement\b|"
    r"\b\d+\+?\s*years?\b|"
    r"\b(?:bachelor|master|mba|ph\.?d)\b|"
    r"\bexperience\s+(?:with|in|managing|building|shipping|partnering)\b|"
    r"\bproficiency\s+(?:with|in)\b|"
    r"\bproven\s+(?:experience|ability)\b"
    r")"
)
_DISPOSITION_CULTURE_RE = re.compile(
    r"(?i)(?:"
    r"\byou\s+are\s+(?:a|an|someone|the\s+kind|excited)\b|"
    r"\bexcited\s+to\s+work\b|"
    r"\bloves?\b|"
    r"\bcannot\s+leave\s+it\s+alone\b|"
    r"\btries\s+every\s+new\b|"
    r"\bnatural\s+builder\b|"
    r"\bcurious\s+one\b|"
    r"\bcuriosity\s+and\s+building\s+instinct\b|"
    r"\buser\s+empathy\b|"
    r"\bvibe\s+codes?\b|"
    r"\bambiguity\s+and\s+shifting\s+priorities\b"
    r")"
)


def is_checkable_qualification_line(text: str) -> bool:
    """True when the line is a credential someone could document. Implements FR-328."""
    return bool(_CHECKABLE_QUAL_RE.search(text or ""))


def is_disposition_culture_line(text: str) -> bool:
    """True for personality, habit, or 'you are a person who' copy. Implements FR-328.

    These are culture, never scored required. Checkable qualifications win:
    track record and working knowledge stay required even without a duty verb.
    """
    if is_checkable_qualification_line(text):
        return False
    return bool(_DISPOSITION_CULTURE_RE.search(text or ""))

EVIDENCE_SYSTEM = """You classify job requirements against supplied candidate evidence.
Return {"results":[...]} with one result per item_id.

RESPONSE FORMAT — every result object MUST include ALL of these fields:
  "item_id": the item's id string
  "gate": "HARD" or "NONE" (use "NONE" for any non-disqualifying line)
  "evidence_level": integer 0-4
  "confidence": "high" or "medium" or "low"
  "reasoning": a non-empty string citing the requirement's vocabulary and the evidence
  "gap_source": "degree" or "domain" or "role_exclusion" or "certification" (only when gate="HARD"; empty string otherwise)

Example: {"item_id":"req-001","gate":"NONE","evidence_level":3,"confidence":"high","reasoning":"The requirement asks for roadmap ownership and the candidate led the C3 platform roadmap for 4 years.","gap_source":""}

EVIDENCE SCALE (0-4) -- rate how much of the requirement the candidate's documented \
experience actually satisfies:
0 = No documented evidence. Nothing in the candidate profile addresses this.
1 = Adjacent evidence. Candidate did work sharing the underlying capability, not the requested work itself.
2 = Partial direct evidence. Candidate did meaningful parts of it, but scope/tooling/context/ownership differs.
3 = Direct evidence. Candidate clearly did substantially equivalent work, comparable scope.
4 = Strong direct evidence. Substantially equivalent work with comparable-or-greater ownership, scope, or outcome.

OR-ALTERNATIVE LINES -- when a line offers multiple alternatives joined by "or", \
rate evidence_level against whichever single alternative the candidate matches BEST, \
not the worst. The line is satisfied if ANY listed alternative is well-documented.

FORBIDDEN AS EVIDENCE (score 0 if this is the only basis): a title alone, an employer \
name alone, company size, a merely-adjacent industry, an implied department interaction, \
a tool the candidate "probably" touched, seniority implying a capability, or trainability. \
Potential is not evidence of demonstrated experience.

HARD GATES -- gate="HARD" ends scoring for this line outright (disqualifying). \
A line from the PREFERRED bucket NEVER gates. Gating is possible ONLY for a REQUIRED-bucket \
line, and only in these four categories:
- degree: a required advanced degree (Master's/MBA/PhD/JD/MD) with NO Bachelor's alternative.
- domain: a required regulated/specialized domain paired with its OWN years-of-experience threshold.
- role_exclusion: a role category incompatible with the candidate's background (people management, \
AI/ML ownership, revenue/billing ownership, title above Senior IC, or building from nothing).
- certification: a required professional certification/license (PMP, CPA, PE, RN license, etc.).
Tools never gate. Bare years-of-experience never gates. If gate="HARD", gap_source MUST be \
exactly one of "degree", "domain", "role_exclusion", or "certification".

CONFIDENCE -- "high" when both line and evidence are unambiguous; "medium" when real \
interpretation was needed; "low" when the JD line is vague or evidence is thin.

Reasoning must cite the requirement's own vocabulary and the specific evidence that \
supports your rating. Do not invent facts or use evidence outside the supplied excerpts.

Do not use tools. Do not read files. Classify only from this prompt."""

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["item_id", "bucket"],
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "bucket": {"type": "string", "enum": list(EXTRACTION_BUCKETS)},
                },
            },
        }
    },
}

EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["results"],
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "item_id",
                    "gate",
                    "gap_source",
                    "evidence_level",
                    "confidence",
                    "reasoning",
                ],
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "gate": {"type": "string", "enum": list(EVIDENCE_GATES)},
                    "gap_source": {"type": "string"},
                    "evidence_level": {"type": "integer", "minimum": 0, "maximum": 4},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "reasoning": {"type": "string", "minLength": 1},
                    "needs_user_confirmation": {"type": "boolean"},
                    "canonical_skill": {"type": "string"},
                    "skill_kind": {"type": "string"},
                },
            },
        }
    },
}


def schema_for(task: str) -> dict[str, Any]:
    """Return the Applyr JSON schema for one Stage 0 classifier task."""
    if task == "extraction":
        return json_clone(EXTRACTION_SCHEMA)
    if task == "evidence":
        return json_clone(EVIDENCE_SCHEMA)
    raise ValueError(f"unsupported Stage 0 classifier task: {task}")


def json_clone(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a detached copy of a JSON-compatible dict."""
    import json

    return json.loads(json.dumps(payload))


def extraction_user_prompt(lines: Sequence[tuple[str, str]]) -> str:
    """Build the Applyr extraction user packet from (item_id, text) pairs."""
    body = "\n".join(f"[{item_id}] {text}" for item_id, text in lines)
    return f"{EXTRACTION_USER_PREFIX}\n\n{body}"


def evidence_user_prompt(
    items: Sequence[Mapping[str, str]],
    *,
    few_shot: str = "",
) -> str:
    """Build the Applyr evidence user packet from structured items.

    Each item should include item_id, requirement, and optionally bucket and
    evidence. few_shot is Applyr-retrieved examples, not provider-specific.
    """
    lines = ["Classify every item exactly once. Return JSON only.", ""]
    if few_shot.strip():
        lines.append(few_shot.strip())
        lines.append("")
    for item in items:
        item_id = str(item.get("item_id") or "").strip()
        bucket = str(item.get("bucket") or "").strip()
        requirement = str(item.get("requirement") or item.get("text") or "").strip()
        evidence = str(item.get("evidence") or item.get("evidence_excerpt") or "").strip()
        if bucket:
            lines.append(f"[{item_id}] bucket={bucket}")
        else:
            lines.append(f"[{item_id}]")
        if requirement:
            lines.append(f"requirement={requirement}")
        if evidence:
            lines.append(f"evidence={evidence}")
        lines.append("")
    return "\n".join(lines)


def combined_classifier_prompt(task: str, user_prompt: str) -> str:
    """Join Applyr system rules and user packet for CLIs with a single prompt."""
    system = EXTRACTION_SYSTEM if task == "extraction" else EVIDENCE_SYSTEM
    return f"{system}\n\n{user_prompt}"


def parse_extraction_mapping(
    payload: Any,
    expected_ids: Iterable[str],
) -> dict[str, str]:
    """Read Applyr extraction JSON, including the legacy index-map shape."""
    wanted = [str(item_id) for item_id in expected_ids]
    wanted_set = set(wanted)
    mapping: dict[str, str] = {}
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        for row in payload["results"]:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("item_id") or "").strip()
            bucket = str(row.get("bucket") or "").strip()
            if item_id in wanted_set and bucket in EXTRACTION_BUCKETS:
                mapping[item_id] = bucket
        return mapping
    if isinstance(payload, dict):
        for key, value in payload.items():
            item_id = str(key).strip()
            bucket = str(value or "").strip()
            if item_id in wanted_set and bucket in EXTRACTION_BUCKETS:
                mapping[item_id] = bucket
            elif item_id.isdigit() and f"e{item_id}" in wanted_set and bucket in EXTRACTION_BUCKETS:
                mapping[f"e{item_id}"] = bucket
    return mapping
