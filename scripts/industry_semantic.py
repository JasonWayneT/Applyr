"""
CR-110 Gap A: LLM-based industry classification for the Stage 0 preference gate.

The keyword industry gate (industry_gate.py) uses regex word-boundary matching
against a blocklist. It misses JDs that describe a blocked industry without using
the exact term (e.g., a gambling company that calls itself a "gaming entertainment
platform"). This module provides a supplementary LLM pass that runs after the
keyword gate, using the same Groq/Gemini plumbing as evidence_scale.py.

Design:
  - The keyword gate runs first (fast, free, deterministic).
  - This LLM pass only runs when the keyword gate does NOT block.
  - On LLM failure, the gate fails open (logs to stderr, does not block).
  - High/medium confidence classifications produce a hard reject.
  - Low confidence produces a soft flag only.

No regex fallback on LLM success — the LLM's judgment is the output. On LLM
failure, the keyword gate's result stands (fail-open for availability).
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

# Max JD chars to send to the LLM (token budget — same rationale as evidence_scale).
_MAX_JD_CHARS = 2000

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "blocked_industry": {
            "type": "string",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
        "reasoning": {
            "type": "string",
        },
    },
    "required": ["blocked_industry", "confidence", "reasoning"],
}

_SYSTEM_PROMPT = """\
You classify whether a job description belongs to a company in any of the user's \
blocked industries. Read the job description and the list of blocked industries \
carefully. Consider the company's product, service, and market — not just the \
job title. A company that makes gambling software is in the gambling industry even \
if the word "gambling" never appears. A company that sells ad-serving technology \
is in ad tech even if it calls itself a "marketing platform."

If the company or role is clearly in one of the blocked industries, return that \
industry name in blocked_industry. If it is not in any blocked industry, return \
an empty string for blocked_industry.

Use high confidence when the JD clearly describes the blocked industry. Use \
medium when the evidence is strong but indirect. Use low when it is a possible \
but uncertain match.

Output JSON only, matching the schema exactly.\
"""


class IndustryClassificationError(Exception):
    """Raised when the LLM industry classification call fails."""


def _build_prompt(
    jd_text: str,
    blocked_industries: list[str],
    company: str = "",
) -> str:
    """Build the user prompt for the LLM call."""
    truncated = jd_text[:_MAX_JD_CHARS]
    if len(jd_text) > _MAX_JD_CHARS:
        truncated += "\n[...truncated...]"

    parts = []
    if company:
        parts.append(f"Company: {company}")
    parts.append(f"Blocked industries: {', '.join(blocked_industries)}")
    parts.append(f"\nJob description:\n{truncated}")
    return "\n\n".join(parts)


def classify_industry(
    jd_text: str,
    blocked_industries: list[str],
    company: str = "",
) -> dict[str, Any]:
    """Classify whether a JD is in a blocked industry using an LLM call.

    Args:
        jd_text: Raw JD text.
        blocked_industries: List of blocked industry names from prefs.
        company: Optional company name for context.

    Returns:
        dict with keys: blocked_industry (str, "" if none), confidence (str),
        reasoning (str).

    Raises:
        IndustryClassificationError on LLM call failure or bad response.
    """
    if not blocked_industries:
        return {"blocked_industry": "", "confidence": "high", "reasoning": "no blocked industries configured"}

    if not jd_text or len(jd_text.strip()) < 50:
        return {"blocked_industry": "", "confidence": "high", "reasoning": "JD text too short to classify"}

    from llm_stages import call_llm_stage
    from pipeline_env import fit_llm_timeout_sec, fit_num_predict

    prompt = _build_prompt(jd_text, blocked_industries, company)

    try:
        raw = call_llm_stage(
            "industry_semantic",
            _SYSTEM_PROMPT,
            prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=_SCHEMA,
            options_override={"num_predict": fit_num_predict()},
            request_timeout=fit_llm_timeout_sec(),
        )
    except Exception as exc:
        raise IndustryClassificationError(f"LLM call failed: {exc}") from exc

    if not raw:
        raise IndustryClassificationError("no LLM response")

    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group(0) if m else raw)
    except json.JSONDecodeError as exc:
        raise IndustryClassificationError(f"bad JSON from LLM: {exc}") from exc

    if not isinstance(data, dict):
        raise IndustryClassificationError(f"non-object LLM response: {data!r}")

    blocked = str(data.get("blocked_industry") or "").strip()
    confidence = str(data.get("confidence") or "low").strip().lower()
    reasoning = str(data.get("reasoning") or "").strip()

    if confidence not in ("high", "medium", "low"):
        confidence = "low"

    # Normalize: if the LLM returned a blocked industry, verify it roughly
    # matches one of the configured blocked industries (case-insensitive).
    if blocked:
        matched = False
        for term in blocked_industries:
            if term.lower() in blocked.lower() or blocked.lower() in term.lower():
                blocked = term  # normalize to the configured spelling
                matched = True
                break
        if not matched:
            # LLM returned an industry not in the blocked list — treat as no match
            blocked = ""

    return {
        "blocked_industry": blocked,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def classify_industry_safe(
    jd_text: str,
    blocked_industries: list[str],
    company: str = "",
) -> dict[str, Any]:
    """Fail-open wrapper for classify_industry.

    Logs errors to stderr and returns a no-block result on failure, so the
    preference gate remains available when the LLM provider is down.
    """
    try:
        return classify_industry(jd_text, blocked_industries, company)
    except IndustryClassificationError as exc:
        print(
            f"    [industry_semantic] Warning: LLM classification failed: {exc}",
            file=sys.stderr,
        )
        return {
            "blocked_industry": "",
            "confidence": "low",
            "reasoning": f"LLM classification failed: {exc}",
            "_gate_failed": True,
        }
