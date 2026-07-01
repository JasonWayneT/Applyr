"""
Deterministic fit-scoring policy helpers (CR-035 / FR-188).

Used after zero-token gates pass — keeps location, anchors, and optional-domain
logic out of unreliable local LLM Stage A re-runs.
"""
from __future__ import annotations

import re
from typing import Tuple

from anchor_gate import count_anchor_hits

# Borderline band: promote to pass when >=2 anchors match (FR-188).
ANCHOR_FLOOR_LOW = 65

_OPTIONAL_DOMAIN_RE = re.compile(
    r"(?:"
    r"nice\s+plus|nice to have|\bideally\b|\bnot required\b|"
    r"may not have experience|\boptional\b|any experience in .{0,40} is a nice|"
    r"background is a plus"
    r")",
    re.I,
)

SOLO_PM_SCORING_NOTE = (
    "Solo-PM trap policy: Reject ONLY when the candidate would be the sole/founding/first "
    "PM with no product peers. Squad PM ownership, structured product orgs, and informal "
    "mentorship of L1/L2 PMs are ALLOWED — do not penalize for guiding junior PMs."
)

STARTUP_PENALTY_NOTE = (
    "Do not apply the startup/solo-trap -50 penalty when the JD mentions "
    "engineering, product design, and/or data teams, or when the role reports "
    "to a functional technology leader (e.g. CTO, VP Engineering)."
)

SENIOR_PM_NOTE = (
    "Senior Product Manager titles are allowed when stated required years are "
    "within experience_range.max."
)

B2C_OPEN_NOTE = (
    "BUSINESS_MODEL: B2C ALLOWED — Candidate is open to consumer/B2C product roles. "
    "Do not reject because the role is B2C, consumer-facing, or mobile app focused. "
    "Bridge from platform PM strengths: roadmap, cross-functional delivery, data integrity, "
    "and scalable product systems — even when end users are consumers rather than enterprises."
)

TRANSFERABLE_SKILLS_NOTE = (
    "TRANSFERABLE SKILLS POLICY: Do NOT reject solely because the JD's industry vertical "
    "(healthcare, fintech, insurance, etc.) or customer base (B2C vs B2B) differs from "
    "the candidate's background. Score PM craft overlap: platform/roadmap ownership, "
    "cross-functional delivery, agile execution, stakeholder alignment, data/system "
    "complexity, compliance-aware product work, and metrics-driven iteration. "
    "Domain or customer-base gaps may appear in RiskFlags for transparency — "
    "never as the sole reject reason."
)


def score_on_transferable_skills(prefs: dict | None) -> bool:
    """Implements FR-192 — default true."""
    if not prefs:
        return True
    nested = prefs.get("preferences") or {}
    if "score_on_transferable_skills" in nested:
        return bool(nested.get("score_on_transferable_skills"))
    if "score_on_transferable_skills" in prefs:
        return bool(prefs.get("score_on_transferable_skills"))
    return True


def transferable_skills_context_block(jd_text: str, prefs: dict | None) -> str:
    if not score_on_transferable_skills(prefs):
        return ""
    from domain_gate import transferable_skills_prompt_block

    specific = transferable_skills_prompt_block(jd_text, prefs)
    return specific if specific else TRANSFERABLE_SKILLS_NOTE


def is_open_to_b2c(prefs: dict | None) -> bool:
    """Implements FR-191 — explicit opt-in via preferences.open_to_b2c or top-level key."""
    if not prefs:
        return False
    nested = (prefs.get("preferences") or {})
    if "open_to_b2c" in nested:
        return bool(nested.get("open_to_b2c"))
    if "open_to_b2c" in prefs:
        return bool(prefs.get("open_to_b2c"))
    return False


def b2c_open_prompt_block(prefs: dict | None) -> str:
    if is_open_to_b2c(prefs):
        return B2C_OPEN_NOTE
    return ""


def years_lock_prompt_block(jd_text: str, prefs: dict) -> str:
    """Implements FR-109 / CR-036 — prevent LLM from re-penalizing years already cleared."""
    from seniority_gate import parse_max_years_required

    exp = (prefs or {}).get("experience_range") or {}
    max_years = exp.get("max")
    if max_years is None:
        return ""
    cap = int(max_years)
    required = parse_max_years_required(jd_text)
    if required is not None and required <= cap:
        return (
            f"PRE-VERIFIED YEARS POLICY: JD requires up to {required} years (cap {cap}). "
            f"WITHIN RANGE — do not penalize for years or Senior title when required <= {cap}."
        )
    if required is None:
        return (
            f"PRE-VERIFIED YEARS POLICY: experience_range.max = {cap}. "
            f"Do not reject Senior PM when stated years are within {cap} or unstated."
        )
    return ""


def detect_optional_domain_note(jd_text: str) -> str:
    """Implements FR-188 — optional vertical/domain language in JD."""
    if not jd_text or not _OPTIONAL_DOMAIN_RE.search(jd_text):
        return ""
    return (
        "DOMAIN_REQUIREMENT: OPTIONAL — The JD explicitly marks domain or vertical "
        "experience as preferred, ideal, or not required. Do not penalize missing "
        "healthcare, insurance, or other industry expertise."
    )


def gates_passed_rubric(job_fit_rules: str) -> str:
    """Strip Stage A fast gate from rubric — deterministic gates already ran."""
    return re.sub(
        r"## 2\) Stage A:.*?(?=\n---\n\n## 3\) Stage B)",
        "## 2) Stage A: The Fast Gate\n"
        "- **SKIPPED** — Deterministic pre-filters already applied "
        "(title, years, industry, keywords, location). Proceed to Stage B scoring only.\n",
        job_fit_rules,
        count=1,
        flags=re.DOTALL,
    )


def build_fit_scoring_context(
    jd_text: str,
    prefs: dict,
    loc_verdict: str,
    loc_detail: str,
    location_lock_block: str,
) -> str:
    """Assemble injected policy blocks for scoring-only fit prompts."""
    from solo_pm_gate import team_structure_prompt_note

    parts: list[str] = []
    if location_lock_block:
        parts.append(location_lock_block.strip())
    years_block = years_lock_prompt_block(jd_text, prefs)
    if years_block:
        parts.append(years_block)
    org_note = team_structure_prompt_note(jd_text, prefs)
    if org_note:
        parts.append(org_note)
    optional = detect_optional_domain_note(jd_text)
    if optional:
        parts.append(optional)
    transfer = transferable_skills_context_block(jd_text, prefs)
    if transfer:
        parts.append(transfer)
    b2c_note = b2c_open_prompt_block(prefs)
    if b2c_note:
        parts.append(b2c_note)
    anchors = (prefs or {}).get("required_anchors") or []
    if isinstance(anchors, list) and anchors:
        hits, matched = count_anchor_hits(jd_text, anchors)
        if hits:
            status = "SATISFIED" if hits >= 2 else f"needs {max(0, 2 - hits)} more"
            parts.append(
                f"ANCHOR_HITS: {hits} matched ({', '.join(matched)}). "
                f"Two-Anchor rule: {status}."
            )
    parts.extend([SENIOR_PM_NOTE, SOLO_PM_SCORING_NOTE, STARTUP_PENALTY_NOTE])
    return "\n\n".join(parts)


def apply_anchor_floor(result: dict | None, jd_text: str, prefs: dict, min_fit_score: int) -> dict | None:
    """
    Record anchor hits as risk/evidence — no longer force-overwrites score (CR-053 Story 2.6).
    """
    if not result:
        return result
    anchors = (prefs or {}).get("required_anchors") or []
    if not isinstance(anchors, list):
        return result
    hits, matched = count_anchor_hits(jd_text, anchors)
    if hits < 2:
        return result

    out = dict(result)
    flags = list(out.get("RiskFlags") or [])
    anchor_note = ", ".join(matched[:4])
    flags.append(f"anchor_hits_{hits}:{anchor_note}")
    out["RiskFlags"] = flags
    return out


def _fit_cites_years_reject(result: dict) -> bool:
    blob = " ".join([
        str(result.get("Summary") or ""),
        " ".join(result.get("TopFitReasons") or []),
        " ".join(result.get("RiskFlags") or []),
    ]).lower()
    phrases = (
        "exceeds max", "exceed max", "years over", "experience exceeds",
        "above max", "over max", "too many years", "years mismatch",
        "experience mismatch", "seniority mismatch", "required years",
    )
    return any(p in blob for p in phrases)


def strip_false_years_penalty(
    result: dict | None, jd_text: str, prefs: dict,
) -> dict | None:
    """Remove spurious years/seniority penalties when deterministic years gate passed."""
    if not result:
        return result
    from seniority_gate import check_years_gate

    ok, _ = check_years_gate(jd_text, prefs or {})
    if not ok or not _fit_cites_years_reject(result):
        return result

    out = dict(result)
    years_terms = (
        "exceed", "years over", "experience exceeds", "above max", "over max",
        "seniority mismatch", "years mismatch", "experience mismatch",
    )

    def _years_flag(text: str) -> bool:
        t = (text or "").lower()
        return any(term in t for term in years_terms)

    out["RiskFlags"] = [r for r in (out.get("RiskFlags") or []) if not _years_flag(r)]
    out["TopFitReasons"] = [r for r in (out.get("TopFitReasons") or []) if not _years_flag(r)]
    summary = str(out.get("Summary") or "")
    if _years_flag(summary):
        out["Summary"] = "Role fit evaluated; years requirement within candidate cap."
    return out


def strip_location_risk_flags(result: dict | None, loc_verdict: str) -> dict | None:
    """Remove spurious location risk flags when location is pre-verified."""
    if not result or loc_verdict not in ("REMOTE_OK", "SD_LOCAL_OK"):
        return result
    location_terms = (
        "location", "remote", "on-site", "onsite", "hybrid", "san diego", "geograph",
    )

    def _loc_flag(text: str) -> bool:
        t = (text or "").lower()
        return any(term in t for term in location_terms)

    out = dict(result)
    out["RiskFlags"] = [r for r in (out.get("RiskFlags") or []) if not _loc_flag(r)]
    reasons = [r for r in (out.get("TopFitReasons") or []) if not _loc_flag(r)]
    out["TopFitReasons"] = reasons
    return out
