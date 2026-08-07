#!/usr/bin/env python3
"""
Stage 0 preference and exclusion-zone zero-token gate.

# Implements FR-252

Given a company name, JD text, and loaded candidate_preferences.json, runs all
deterministic (no-LLM) rejection checks and returns a structured verdict.

Return shape::

    {
        "passed": bool,          # True when no hard rejects
        "rejects": [             # list of hard-reject reasons (→ Skip)
            {"code": "...", "reason": "..."},
        ],
        "flags": [               # soft informational flags (no blocking)
            {"code": "...", "note": "..."},
        ],
    }

Reuses (imports on first call, never at module scope to keep tests fast):
  - industry_gate.batch_industry_blocked
  - seniority_gate.passes_title_gate, check_years_gate
  - solo_pm_gate.check_solo_pm_gate
"""
from __future__ import annotations

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Travel ceiling
# ---------------------------------------------------------------------------

# Matches "travel up to 50%", "travel 30%", "travel requirement: 25%", etc.
_TRAVEL_PCT_RE = re.compile(
    r"travel\b.{0,40}?(\d{1,3})\s*%",
    re.I,
)
# Matches "up to 25% travel"
_TRAVEL_PCT_RE2 = re.compile(
    r"(\d{1,3})\s*%\s+travel",
    re.I,
)
_TRAVEL_HEAVY_WORDS = re.compile(
    r"\b(frequent|extensive|heavy|significant|considerable|regular)\s+travel\b",
    re.I,
)

_DEFAULT_TRAVEL_CEILING_PCT = 15


def _check_travel(jd_text: str, ceiling_pct: int = _DEFAULT_TRAVEL_CEILING_PCT) -> list[dict]:
    """Return reject dicts if travel exceeds ceiling, empty list if OK."""
    text = (jd_text or "")
    rejects: list[dict] = []
    for pat in (_TRAVEL_PCT_RE, _TRAVEL_PCT_RE2):
        for m in pat.finditer(text):
            try:
                pct = int(m.group(1))
            except (IndexError, ValueError):
                continue
            if pct > ceiling_pct:
                rejects.append({
                    "code": "travel_ceiling",
                    "reason": f"JD requires {pct}% travel, exceeds ceiling of {ceiling_pct}%",
                })
    # If no numeric match but heavy-travel language found, soft flag only (can't quantify).
    return rejects


def _travel_soft_flag(jd_text: str) -> list[dict]:
    """Return a soft flag if unquantified heavy-travel language is detected."""
    if not jd_text:
        return []
    if _TRAVEL_HEAVY_WORDS.search(jd_text):
        return [{"code": "travel_language_unquantified", "note": "Heavy travel language without explicit %"}]
    return []


# ---------------------------------------------------------------------------
# Exclusion zones — people management
# ---------------------------------------------------------------------------

_PEOPLE_MGT_REQUIRED_RE = re.compile(
    r"\b("
    r"manage\s+a\s+team\s+of|"
    r"manage\s+(?:\d+|a\s+team\s+of)\s+(?:engineers?|developers?|designers?|pms?|people|reports?)|"
    r"direct\s+reports?|"
    r"people\s+management\s+(?:experience|required|responsibilities)|"
    r"you\s+will\s+manage\s+(?:a\s+team|engineers?|people|staff)|"
    r"hiring\s+(?:and\s+)?(firing|performance\s+reviews?)|"
    r"grow\s+and\s+manage\s+a\s+team|"
    r"build\s+(?:and\s+lead\s+)?a\s+team\s+of|"
    r"headcount\s+(?:planning|management|decisions?)|"
    r"performance\s+reviews?\s+(?:and|for)\s+(?:engineers?|developers?|designers?|pms?|staff)"
    r")",
    re.I,
)

# Negative context — these cancel the people-management signal
_PEOPLE_MGT_NEGATIVE_RE = re.compile(
    r"\b(manage\s+stakeholders?|manage\s+(?:up|vendors?|projects?|products?|priorities|expectations|timelines?|relationships?|roadmaps?))\b",
    re.I,
)


def _check_people_management(jd_text: str) -> list[dict]:
    if not jd_text:
        return []
    # Remove negative-context lines first
    filtered = "\n".join(
        line for line in jd_text.splitlines()
        if not _PEOPLE_MGT_NEGATIVE_RE.search(line)
    )
    if _PEOPLE_MGT_REQUIRED_RE.search(filtered):
        return [{
            "code": "exclusion_zone_people_management",
            "reason": "JD requires direct people management / managing a team — Exclusion Zone",
        }]
    return []


# ---------------------------------------------------------------------------
# Exclusion zones — 0-to-1 / founding PM (pattern only; solo_pm_gate covers more)
# ---------------------------------------------------------------------------

_ZERO_TO_ONE_RE = re.compile(
    r"\b("
    r"0\s*[-–]\s*1\s+(?:product|pm|role)|"
    r"zero[- ]to[- ]one\s+(?:product|experience|pm)|"
    r"greenfield\s+(?:product|build|initiative)|"
    r"build\s+(?:from\s+)?scratch\s+(?:the\s+)?(?:product|platform|pm\s+function)"
    r")\b",
    re.I,
)


def _check_zero_to_one(jd_text: str) -> list[dict]:
    if not jd_text:
        return []
    if _ZERO_TO_ONE_RE.search(jd_text):
        return [{
            "code": "exclusion_zone_zero_to_one",
            "reason": "JD signals 0-to-1 / greenfield build — Exclusion Zone",
        }]
    return []


# ---------------------------------------------------------------------------
# Exclusion zones — revenue / billing ownership
# ---------------------------------------------------------------------------

_REVENUE_OWN_RE = re.compile(
    r"\b("
    r"own\s+(?:the\s+)?(?:revenue\s+model|billing\s+(?:system|product|platform)|p\s*[&and]+\s*l|pricing\s+strategy)|"
    r"(?:revenue|billing|payments?)\s+ownership|"
    r"manage\s+(?:the\s+)?p\s*[&and]+\s*l|"
    r"p\s*[&and]+\s*l\s+(?:ownership|responsibility|accountability)|"
    r"own\s+(?:the\s+)?(?:billing|payments?|monetization)\s+product|"
    r"drive\s+(?:and\s+)?own\s+(?:revenue|billing)"
    r")\b",
    re.I,
)


def _check_revenue_billing(jd_text: str) -> list[dict]:
    if not jd_text:
        return []
    if _REVENUE_OWN_RE.search(jd_text):
        return [{
            "code": "exclusion_zone_revenue_billing",
            "reason": "JD requires revenue/billing/P&L ownership — Exclusion Zone",
        }]
    return []


# ---------------------------------------------------------------------------
# Exclusion zones — AI/ML model ownership (not tooling fluency)
# ---------------------------------------------------------------------------

# These patterns catch "build/train/own ML models" without false-positiving
# on ACC-401 language ("use AI tools", "prompt engineering", "Claude/Gemini").
_AI_MODEL_OWN_RE = re.compile(
    r"\b("
    r"(?:build|train|develop|design|own|architect|deploy)\s+(?:and\s+)?(?:ml|ai|machine\s+learning|deep\s+learning|llm|neural\s+network)\s+models?|"
    r"(?:ml|ai|machine\s+learning)\s+model\s+(?:development|ownership|engineering)|"
    r"own\s+(?:the\s+)?(?:ai|ml|machine\s+learning)\s+(?:model|platform|pipeline)|"
    r"train\s+(?:and\s+)?(?:fine.?tune\s+)?(?:large\s+)?language\s+models?|"
    r"responsible\s+for\s+(?:training|building|designing)\s+(?:ai|ml|machine\s+learning)\s+models?"
    r")\b",
    re.I,
)

# Negative guard — "use AI tools", "AI fluency", "leverage AI" are OK
_AI_TOOLING_ONLY_RE = re.compile(
    r"\b(use\s+ai\s+tools?|ai\s+fluency|ai\s+literacy|prompt\s+engineering|leverage\s+ai|"
    r"comfortable\s+with\s+ai|ai.assisted|ai\s+prototyping|"
    r"claude|gemini|chatgpt|openai\s+api)\b",
    re.I,
)


def _check_ai_ml_ownership(jd_text: str) -> list[dict]:
    if not jd_text:
        return []
    if not _AI_MODEL_OWN_RE.search(jd_text):
        return []
    # If the match is in a line that's purely about tooling, skip
    for line in jd_text.splitlines():
        if _AI_MODEL_OWN_RE.search(line) and not _AI_TOOLING_ONLY_RE.search(line):
            return [{
                "code": "exclusion_zone_ai_ml_ownership",
                "reason": "JD requires AI/ML model ownership or training — Exclusion Zone",
            }]
    return []


# ---------------------------------------------------------------------------
# Blocked company
# ---------------------------------------------------------------------------

def _check_blocked_company(company: str, prefs: dict) -> list[dict]:
    blocked = (prefs or {}).get("blocked_companies") or []
    if not isinstance(blocked, list):
        return []
    company_lower = (company or "").lower().strip()
    for entry in blocked:
        if not entry:
            continue
        if entry.lower().strip() in company_lower or company_lower in entry.lower().strip():
            return [{
                "code": "blocked_company",
                "reason": f"Company '{company}' matches blocked_companies entry '{entry}'",
            }]
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_prefs_gate(
    company: str,
    jd_text: str,
    prefs: dict | None = None,
) -> dict:
    """
    Run all preference and exclusion-zone zero-token checks.

    Parameters
    ----------
    company:
        Company name string (used for blocked_company check).
    jd_text:
        Raw JD text.
    prefs:
        Loaded candidate_preferences.json dict.  When None, loads from disk.

    Returns
    -------
    dict with keys:
        passed   — True when no hard rejects
        rejects  — list of {code, reason} hard-block dicts
        flags    — list of {code, note} soft-flag dicts
    """
    if prefs is None:
        from utils import load_candidate_preferences
        prefs = load_candidate_preferences()

    rejects: list[dict] = []
    flags: list[dict] = []

    # 1. Blocked company
    rejects.extend(_check_blocked_company(company, prefs))

    # 2. Blocked industry (reuse existing gate)
    from industry_gate import batch_industry_blocked
    blocked, term = batch_industry_blocked(company, jd_text, prefs)
    if blocked:
        rejects.append({
            "code": "blocked_industry",
            "reason": f"Industry blocklist match: '{term}'",
        })

    # 3. Title blocklist
    from seniority_gate import passes_title_gate
    passes, title_reason = passes_title_gate(jd_text, prefs)
    if not passes:
        rejects.append({
            "code": "blocked_title",
            "reason": title_reason,
        })

    # 4. Years ceiling
    from seniority_gate import check_years_gate
    passes, years_reason = check_years_gate(jd_text, prefs)
    if not passes:
        rejects.append({
            "code": "years_ceiling",
            "reason": years_reason,
        })

    # 5. Solo PM trap (0-to-1 / founding PM)
    from solo_pm_gate import check_solo_pm_gate
    passes, solo_reason = check_solo_pm_gate(jd_text, prefs)
    if not passes:
        rejects.append({
            "code": "solo_pm_trap",
            "reason": solo_reason,
        })

    # 6. Zero-to-one pattern (supplemental to solo_pm_gate)
    rejects.extend(_check_zero_to_one(jd_text))

    # 7. Travel ceiling
    rejects.extend(_check_travel(jd_text))
    flags.extend(_travel_soft_flag(jd_text))

    # 8. Exclusion zones
    rejects.extend(_check_people_management(jd_text))
    rejects.extend(_check_revenue_billing(jd_text))
    rejects.extend(_check_ai_ml_ownership(jd_text))

    # Deduplicate rejects by code (keep first)
    seen_codes: set[str] = set()
    deduped: list[dict] = []
    for r in rejects:
        if r["code"] not in seen_codes:
            seen_codes.add(r["code"])
            deduped.append(r)

    return {
        "passed": len(deduped) == 0,
        "rejects": deduped,
        "flags": flags,
    }
