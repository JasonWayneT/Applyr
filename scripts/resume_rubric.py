"""
Deterministic resume rubric scoring (FR-200).

Scores a compiled Resume.md against the job description using the weighted
rubric from resume_decision_report_2026. No LLM calls — every criterion
is proxied via regex, token matching, and structural checks.

Rubric weights:
  Summary   (40%): role_targeting(25%) + value_proposition(25%)
                   + evidence_outcomes(30%) + keyword_alignment(20%)
  Experience(60%): relevance(25%) + achievement_vs_duties(25%)
                   + quantification(20%) + structure(15%)
                   + skills_integration(15%)

  overall = 0.4 * summary + 0.6 * experience
  threshold_flag = True when overall < 60
"""
from __future__ import annotations

import re
from typing import Dict, List

_STOP_WORDS = {
    "about", "their", "would", "should", "other", "have", "with",
    "that", "this", "will", "from", "your", "they", "been", "were",
    "also", "when", "what", "which", "than", "more", "into", "some",
    "such", "each", "both", "does", "very", "able",
}

_STRONG_VERB_RE = re.compile(
    r"^(Stabilized|Drove|Built|Designed|Delivered|Implemented|Reduced|"
    r"Eliminated|Launched|Led|Partnered|Resolved|Closed|Identified|"
    r"Prioritized|Replaced|Managed|Coordinated|Scoped|Navigated|"
    r"Maintained|Generated|Sustained|Restored|Enabled|Accelerated|"
    r"Increased|Improved|Developed|Established|Executed|Negotiated|"
    r"Streamlined|Automated|Deployed|Migrated|Rebuilt|Architected|"
    r"Created|Secured|Synthesized|Presented|Reverse-engineered|"
    r"Enforced|Expanded|Translated|Owned|Co-created|Facilitated|"
    r"Extended|Spearheaded|Introduced|Restructured|Consolidated|"
    r"Optimized|Scaled|Tracked|Formalized|Championed|Refined)\b",
    re.IGNORECASE,
)


_REQ_TOKEN_CAP = 60  # calibrated for a typical requirements section (~30-80 unique terms)


def _req_tokens(jd_text: str) -> set:
    from jd_tailoring import extract_req_section
    req = extract_req_section(jd_text) if jd_text else jd_text
    return set(re.findall(r"[a-z]{4,}", req.lower())) - _STOP_WORDS


def _eff_req_denom(req_tok: set) -> int:
    """Effective denominator: caps at _REQ_TOKEN_CAP when the full JD was used as fallback.

    When extract_req_section() falls back to the full JD, req_tok can contain
    200-600+ tokens. The multipliers (300x, 400x, 500x) were calibrated for
    ~30-60 focused requirement tokens. Capping prevents artificially low scores
    on JDs with no structured requirements section.
    """
    return min(len(req_tok), _REQ_TOKEN_CAP) if req_tok else 1


_EDU_SECTION_RE = re.compile(r"^##\s*EDUCATION", re.IGNORECASE | re.MULTILINE)


def _bullet_lines(resume_md: str) -> List[str]:
    """Extract experience/skills bullet lines, excluding education section entries."""
    edu_match = _EDU_SECTION_RE.search(resume_md)
    experience_text = resume_md[: edu_match.start()] if edu_match else resume_md
    return [
        ln.lstrip("* ").strip()
        for ln in experience_text.splitlines()
        if ln.strip().startswith("* ")
    ]


def _summary_text(resume_md: str) -> str:
    m = re.search(
        r"##\s*PROFESSIONAL\s+SUMMARY\s*\n([\s\S]*?)(?=\n##\s)",
        resume_md,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Summary sub-scores
# ---------------------------------------------------------------------------

def _s_role_targeting(summary: str, req_tok: set) -> float:
    """How many req-section tokens appear in the summary (0-100)."""
    if not req_tok:
        return 60.0
    s_lower = summary.lower()
    matched = sum(1 for t in req_tok if t in s_lower)
    return min(100.0, matched / _eff_req_denom(req_tok) * 300)


def _s_value_proposition(summary: str) -> float:
    """Summary contains at least one metric (0 or 100)."""
    return 100.0 if re.search(r"\d", summary) else 0.0


def _s_evidence_outcomes(summary: str) -> float:
    """Number of sentences in summary that contain a metric (0-100, capped at 2)."""
    sentences = re.split(r"(?<=[.!?])\s+", summary.strip())
    proof = sum(1 for s in sentences if re.search(r"\d", s))
    return min(100.0, proof * 50.0)


def _s_keyword_alignment(summary: str, req_tok: set) -> float:
    """Overlap between summary tokens and req tokens (0-100)."""
    if not req_tok:
        return 50.0
    s_tok = set(re.findall(r"[a-z]{4,}", summary.lower())) - _STOP_WORDS
    overlap = len(s_tok & req_tok)
    return min(100.0, overlap / _eff_req_denom(req_tok) * 400)


# ---------------------------------------------------------------------------
# Experience sub-scores
# ---------------------------------------------------------------------------

def _e_relevance(bullets: List[str], req_tok: set) -> float:
    """Average per-bullet req-token overlap (0-100)."""
    if not bullets or not req_tok:
        return 50.0
    denom = _eff_req_denom(req_tok)
    scores = []
    for b in bullets:
        b_lower = b.lower()
        matched = sum(1 for t in req_tok if t in b_lower)
        scores.append(min(100.0, matched / denom * 500))
    return sum(scores) / len(scores)


def _e_achievement(bullets: List[str]) -> float:
    """Ratio of outcome-framed bullets (not activity-only process verbs) (0-100)."""
    if not bullets:
        return 0.0
    from conversion_framing import is_outcome_bullet

    return round(sum(1 for b in bullets if is_outcome_bullet(b)) / len(bullets) * 100, 1)


def _e_quantification(bullets: List[str]) -> float:
    """Ratio of bullets with business outcome metrics (0-100)."""
    if not bullets:
        return 0.0
    from conversion_framing import has_outcome_metric

    return round(sum(1 for b in bullets if has_outcome_metric(b)) / len(bullets) * 100, 1)


def _e_structure(resume_md: str, bullets: List[str]) -> float:
    """All three employers present + no overlong bullets (0-100)."""
    try:
        from local_draft_stages import MAX_BULLET_WORDS as _max
    except Exception:
        _max = 28
    lower = resume_md.lower()
    all_employers = all(e in lower for e in ("cision", "sterkly", "zero to sixty"))
    overlong = sum(1 for b in bullets if len(b.split()) > _max)
    employer_score = 70.0 if all_employers else 0.0
    length_score = 30.0 if overlong == 0 else max(0.0, 30.0 - overlong * 10.0)
    return employer_score + length_score


def _e_skills_integration(resume_md: str) -> float:
    """CORE COMPETENCIES section is present (0 or 100)."""
    return 100.0 if re.search(r"##\s*CORE\s+COMPETENCIES", resume_md, re.IGNORECASE) else 0.0


# ---------------------------------------------------------------------------
# Public scorer
# ---------------------------------------------------------------------------

def score_resume(
    resume_md: str,
    jd_text: str,
    bullets_by_company: Dict[str, List[str]] | None = None,
) -> dict:
    """Score a compiled resume against the rubric (FR-200).

    Args:
        resume_md:          Full text of Resume.md.
        jd_text:            Full job description text.
        bullets_by_company: Optional dict of employer -> bullet list for
                            more accurate Cision bullet extraction.

    Returns a dict containing:
        overall (float 0-100), threshold_flag (bool), summary dict,
        experience dict — all sub-scores rounded to one decimal.
    """
    req_tok = _req_tokens(jd_text)
    summary = _summary_text(resume_md)
    bullets = _bullet_lines(resume_md)

    # Summary scores
    s_targeting = _s_role_targeting(summary, req_tok)
    s_value_prop = _s_value_proposition(summary)
    s_evidence = _s_evidence_outcomes(summary)
    s_alignment = _s_keyword_alignment(summary, req_tok)
    summary_score = (
        s_targeting * 0.25
        + s_value_prop * 0.25
        + s_evidence * 0.30
        + s_alignment * 0.20
    )

    # Experience scores
    e_relevance = _e_relevance(bullets, req_tok)
    e_achievement = _e_achievement(bullets)
    e_quantification = _e_quantification(bullets)
    e_structure = _e_structure(resume_md, bullets)
    e_skills = _e_skills_integration(resume_md)
    experience_score = (
        e_relevance * 0.25
        + e_achievement * 0.25
        + e_quantification * 0.20
        + e_structure * 0.15
        + e_skills * 0.15
    )

    overall = round(summary_score * 0.40 + experience_score * 0.60, 1)

    return {
        "overall": overall,
        "threshold_flag": overall < 60,
        "summary": {
            "score": round(summary_score, 1),
            "role_targeting": round(s_targeting, 1),
            "value_proposition": s_value_prop,
            "evidence_outcomes": s_evidence,
            "keyword_alignment": round(s_alignment, 1),
        },
        "experience": {
            "score": round(experience_score, 1),
            "relevance": round(e_relevance, 1),
            "achievement_vs_duties": e_achievement,
            "quantification": e_quantification,
            "structure": e_structure,
            "skills_integration": e_skills,
        },
    }
