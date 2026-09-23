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
    r"lead\s+(?:a\s+)?(?:small\s+)?team\s+of\s+(?:\d+\s*[\u2013\-]\s*\d+\s+)?"
    r"(?:[\w]+\s+){0,4}?(?:analysts?|specialists?|engineers?|developers?|designers?|people|reports?)|"
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
_PEOPLE_MGT_NEGATED_ROLE_RE = re.compile(
    r"\b(?:no|not|without|never)\b.{0,48}\b(?:direct\s+reports?|people[- ]management)"
    r"|\b(?:direct\s+reports?|people[- ]management).{0,48}\b(?:no|not)\b",
    re.I,
)
_OTHER_MANAGERS_REPORTS_RE = re.compile(
    r"\b(?:their|his|her|the\s+manager'?s)\s+direct\s+reports?\b",
    re.I,
)
_COACHING_NOT_MANAGING_RE = re.compile(
    r"\b(?:coach(?:ing)?|mentor(?:ing)?)\b",
    re.I,
)


def _people_line_is_not_role_management(line: str) -> bool:
    """True when a line mentions reports or management that is not this role's.

    Implements FR-338.
    """
    if _PEOPLE_MGT_NEGATIVE_RE.search(line):
        return True
    if _PEOPLE_MGT_NEGATED_ROLE_RE.search(line):
        return True
    if _OTHER_MANAGERS_REPORTS_RE.search(line):
        return True
    if _COACHING_NOT_MANAGING_RE.search(line) and not re.search(
        r"\b(?:you will|this role|the role)\b.{0,60}\b(?:manage|direct reports?)",
        line,
        re.I,
    ):
        return True
    return False


def _check_people_management(jd_text: str) -> list[dict]:
    """Skip only when this role has reports or manages people. Implements FR-338."""
    if not jd_text:
        return []
    filtered = "\n".join(
        line for line in jd_text.splitlines()
        if not _people_line_is_not_role_management(line)
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
    # Original patterns (ownership of revenue model, billing, P&L, pricing)
    r"own\s+(?:the\s+)?(?:revenue\s+model|billing\s+(?:system|product|platform)|p\s*[&and]+\s*l|pricing\s+strategy)|"
    r"(?:revenue|billing|payments?)\s+ownership|"
    r"manage\s+(?:the\s+)?p\s*[&and]+\s*l|"
    r"p\s*[&and]+\s*l\s+(?:ownership|responsibility|accountability)|"
    r"own\s+(?:the\s+)?(?:billing|payments?|monetization)\s+product|"
    r"drive\s+(?:and\s+)?own\s+(?:revenue|billing)|"
    # Added 2026-09-03: broader phrasings found in real JDs that the original
    # regex missed, allowing revenue/billing/pricing roles to pass Stage 0.
    # amphenol_rf/hale: "Manage product line performance. Including revenue and margin"
    r"(?:manage|drive|own|lead)\s+product\s+line\s+(?:performance|revenue|margin|growth|profitability)|"
    r"revenue\s+and\s+margin|"
    r"product[- ]line\s+(?:growth\s+and\s+)?profitability|"
    r"profitability\s+of\s+(?:a\s+|the\s+)?(?:key\s+)?product[- ]line|"
    r"full\s+product[- ]line\s+business|"
    r"product[- ]line(?:'s|’s)?\s+commercial\s+performance|"
    # beyond: "define and evolve how dynamic pricing works"
    r"define\s+and\s+evolve\s+.*dynamic\s+pricing|"
    r"owning\s+.*pricing\s+algorithm|"
    r"translating\s+pricing\s+strategy\s+into|"
    # harnham: "pricing updates", "billing, ordering", "pricing models"
    r"(?:manage|own|support)\s+.*(?:pricing\s+updates?|pricing\s+models?)|"
    r"billing\s*,?\s*(?:and\s+)?(?:ordering|invoicing)|"
    # tenth_revolution_group: "Own product strategy for finance, payroll"
    r"own\s+product\s+strategy\s+.*?(?:finance|payroll|billing)|"
    r"payroll\s+(?:processing|management|invoicing)|"
    r"(?:finance|payroll|billing)\s+(?:workstreams?|solutions?|products?)"
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


# Hands-on KYC / KYB implementation the posting itself marks as mandatory.
# A model evidence score of 0 does not hard-gate this, because the domain rule
# also wants a years number. Kraken 2026-09-22: the must-have line was scored
# 0, then a nice-to-have founder line opened a review card and the fit-floor
# skip never ran. Familiarity, or KYC as one option among others, does not skip.
_KYC_MUST_HAVE_RE = re.compile(
    r"hands[\s-]on experience implementing (?:kyc|kyb)|"
    r"implementing (?:kyc|kyb).{0,120}must have|"
    r"(?:kyc|kyb).{0,80}must have,\s*not a nice to have",
    re.I | re.S,
)


def _check_kyc_must_have(jd_text: str) -> list[dict]:
    """Skip a posting that requires hands-on KYC or KYB implementation."""
    if not jd_text or not _KYC_MUST_HAVE_RE.search(jd_text):
        return []
    return [{
        "code": "exclusion_zone_kyc_implementation",
        "reason": "JD requires hands-on KYC or KYB implementation — Exclusion Zone",
    }]


# ---------------------------------------------------------------------------
# Exclusion zones — AI/ML model ownership (not tooling fluency)
# ---------------------------------------------------------------------------

# Hard-skip only when the JD requires the candidate to train, fine-tune, or
# build models, or requires an ML engineering / data science background.
# "Deploy AI models" in a product description, and "shipped AI features",
# are not exclusion-zone hits (ACC-401 / ACC-120 / ACC-179 soft-gap path).
_AI_MODEL_OWN_RE = re.compile(
    r"\b("
    r"(?:train(?:ing)?|fine.?tun(?:e|ing)|build(?:ing)?)\s+"
    r"(?:and\s+(?:fine.?tun(?:e|ing)|deploying)\s+)?"
    r"(?:ml|ai|machine\s+learning|deep\s+learning|llm|neural\s+network|language)\s+models?|"
    r"train(?:ing)?\s+and\s+fine.?tun(?:e|ing)\s+(?:llms?|large\s+language\s+models?)|"
    r"(?:ml|machine\s+learning)\s+engineering\s+background|"
    r"data\s+science\s+background|"
    r"responsible\s+for\s+(?:training|fine.?tuning|building)\s+(?:ai|ml|machine\s+learning)\s+models?"
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
# Required non-English language fluency
# ---------------------------------------------------------------------------
# Found 2026-09-19 on binance (Data Product Manager, Derivatives): the JD stated
# "Bilingual English/Mandarin required to coordinate with overseas partners."
# Stage 0's LLM evidence classifier downgraded this to gap_class SOFT, reasoning
# that Jason's experience coordinating with distributed teams IN ENGLISH
# (U.S./India/Budapest/Israel) "demonstrates the underlying cross-geographic
# coordination capability" -- that is a different skill and does not address
# actual language fluency at all. Jason confirmed directly: no Mandarin, "a
# little Spanish and English." An LLM judgment call on a factual, binary
# question (does the candidate speak this language) is the wrong tool here --
# same reasoning as why travel/years/title use deterministic gates instead of
# trusting the cascade's soft/hard call. Spanish is a genuine partial case (some
# proficiency, unclear if it meets a given JD's bar) so it flags for review
# instead of a hard reject; every other named language hard-rejects since
# there is zero evidence of any proficiency.
# Matches only an explicit human-language name, never an open word class -- an
# earlier version used `\w+` after "fluent in" and false-positived on "become
# deeply fluent in legal and medical workflows" (indigo JD: domain fluency,
# not language fluency, and not even hiring-requirement framing).
_LANGUAGE_NAMES = (
    "mandarin|chinese|cantonese|spanish|french|german|japanese|korean|"
    "portuguese|italian|russian|arabic|hindi|vietnamese|thai|tagalog|"
    "polish|dutch|swedish|turkish|hebrew|indonesian|malay|farsi|persian|"
    "urdu|bengali|punjabi|tamil|ukrainian|greek|romanian|hungarian|czech|"
    "danish|norwegian|finnish|swahili"
)
_REQUIRED_LANGUAGE_RE = re.compile(
    rf"\b(?:bilingual\s+english/(?P<lang1>{_LANGUAGE_NAMES})|"
    rf"fluent(?:cy)?\s+in\s+(?P<lang2>{_LANGUAGE_NAMES})|"
    rf"(?P<lang3>{_LANGUAGE_NAMES})\s+fluency\s+(?:is\s+)?required|"
    rf"must\s+(?:speak|be\s+fluent\s+in)\s+(?P<lang4>{_LANGUAGE_NAMES})|"
    rf"native\s+(?P<lang5>{_LANGUAGE_NAMES})\s+speaker\s+required)\b",
    re.I,
)
_ENGLISH_RE = re.compile(r"^english$", re.I)
_SPANISH_RE = re.compile(r"^spanish$", re.I)


def _check_required_language(jd_text: str) -> tuple[list[dict], list[dict]]:
    """Return (rejects, flags) for an explicit required non-English language.

    Only fires on "required"/"must"/"fluent" framing, not "preferred" or
    "a plus" -- those are legitimate soft gaps the existing evidence cascade
    can reason about (they are not a binary pass/fail on Jason's own history).
    """
    if not jd_text:
        return [], []
    rejects: list[dict] = []
    flags: list[dict] = []
    seen: set[str] = set()
    for match in _REQUIRED_LANGUAGE_RE.finditer(jd_text):
        lang = next((g for g in match.groups() if g), None)
        if not lang or _ENGLISH_RE.match(lang):
            continue
        key = lang.casefold()
        if key in seen:
            continue
        seen.add(key)
        if _SPANISH_RE.match(lang):
            flags.append({
                "code": "required_language_partial",
                "note": (
                    f"JD requires {lang} fluency; Jason has some Spanish but "
                    "proficiency against this JD's bar is unconfirmed — needs a "
                    "human check, not an automatic pass or skip."
                ),
            })
            continue
        rejects.append({
            "code": "required_language_unmet",
            "reason": (
                f"JD requires {lang} fluency; Jason speaks English (and some "
                "Spanish) with no documented proficiency in this language"
            ),
        })
    return rejects, flags


# ---------------------------------------------------------------------------
# Blocked company
# ---------------------------------------------------------------------------

def _normalize_company_name(name: str) -> str:
    """Collapse a company string for exact blocked-list matching. Implements FR-337."""
    return re.sub(r"\s+", " ", (name or "").strip().casefold())


def _check_blocked_company(company: str, prefs: dict) -> list[dict]:
    """Reject only when the whole normalized company name equals a blocked entry.

    Substring checks made "Remote" match "RemoteHunter" and a blank company
    match every entry because ``"" in "remotehunter"`` is True. Implements FR-337.
    """
    blocked = (prefs or {}).get("blocked_companies") or []
    if not isinstance(blocked, list):
        return []
    company_key = _normalize_company_name(company)
    if not company_key:
        return []
    for entry in blocked:
        entry_key = _normalize_company_name(str(entry or ""))
        if not entry_key:
            continue
        if company_key == entry_key:
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

    # 2. Blocked industry — keyword gate (deterministic, fast, free)
    from industry_gate import batch_industry_blocked
    blocked, term = batch_industry_blocked(company, jd_text, prefs)
    if blocked:
        rejects.append({
            "code": "blocked_industry",
            "reason": f"Industry blocklist match: '{term}'",
        })

    # 2b. Blocked industry — LLM semantic gate (supplementary, CR-110 Gap A)
    # Only runs when the keyword gate did not block. Fail-open on LLM error.
    if not blocked:
        from industry_semantic import classify_industry_safe
        blocked_industries = prefs.get("blocked_industries") or []
        if blocked_industries:
            result = classify_industry_safe(jd_text, blocked_industries, company)
            llm_blocked = result.get("blocked_industry", "")
            llm_confidence = result.get("confidence", "low")
            if llm_blocked and llm_confidence in ("high", "medium"):
                rejects.append({
                    "code": "blocked_industry_semantic",
                    "reason": f"LLM industry classification: '{llm_blocked}' ({llm_confidence})",
                })
            elif llm_blocked and llm_confidence == "low":
                flags.append({
                    "code": "blocked_industry_semantic_low",
                    "note": f"Possible blocked industry (low confidence): '{llm_blocked}'",
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
    rejects.extend(_check_kyc_must_have(jd_text))

    # 8b. Required non-English language fluency (live miss, binance, 2026-09-19)
    lang_rejects, lang_flags = _check_required_language(jd_text)
    rejects.extend(lang_rejects)
    flags.extend(lang_flags)

    # 9. JD content validation (CR-110 Gap B). network_page is a flag, not a skip.
    from jd_content_validation import check_jd_placeholders, check_network_page
    rejects.extend(check_jd_placeholders(jd_text))
    for item in check_network_page(jd_text):
        flags.append({
            "code": item.get("code", "network_page"),
            "note": item.get("reason") or "Hidden employer / talent-network page",
        })

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
