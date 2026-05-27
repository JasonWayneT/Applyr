"""
JD profile extraction and claim scoring (CR-014 / FR-091).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List

from utils import PROJECT_ROOT

BRIDGE_PHRASES_PATH = os.path.join(PROJECT_ROOT, "data", "bridge_phrases.json")

THEME_KEYWORDS = (
    ("platform", "platform reliability and scale"),
    ("data", "data integrity and ingestion"),
    ("ingest", "data integrity and ingestion"),
    ("migration", "customer migration and retention"),
    ("security", "security backlog and risk reduction"),
    ("roadmap", "roadmap prioritization and execution"),
    ("saas", "B2B SaaS product delivery"),
    ("stakeholder", "cross-functional stakeholder alignment"),
    ("onboarding", "onboarding and customer experience"),
)


@dataclass
class JdProfile:
    priority_themes: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    source: str = "deterministic"

    def to_dict(self):
        return asdict(self)


def load_bridge_phrases() -> Dict[str, str]:
    if os.path.exists(BRIDGE_PHRASES_PATH):
        with open(BRIDGE_PHRASES_PATH, encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _substring_valid(phrase: str, jd_text: str) -> bool:
    return _normalize_ws(phrase) in _normalize_ws(jd_text)


def build_jd_profile_deterministic(jd_text: str, fit_summary: str = "") -> JdProfile:
    jd_lower = jd_text.lower()
    themes = []
    for kw, phrase in THEME_KEYWORDS:
        if kw in jd_lower and phrase not in themes:
            themes.append(phrase)

    requirements = []
    for line in jd_text.splitlines():
        line = line.strip().lstrip("-•*").strip()
        if 20 <= len(line) <= 120 and line[0].isalnum():
            requirements.append(line[:120])
    requirements = requirements[:6]

    words = set(re.findall(r"[a-z]{5,}", jd_lower))
    keywords = sorted(w for w in words if w not in {"about", "their", "would", "should", "other"})[:12]

    if fit_summary:
        fs = fit_summary.lower()
        for kw, phrase in THEME_KEYWORDS:
            if kw in fs and phrase not in themes:
                themes.append(phrase)

    return JdProfile(
        priority_themes=themes[:4],
        requirements=requirements[:6],
        keywords=keywords,
        source="deterministic",
    )


def build_jd_profile(jd_text: str, fit_summary: str = "") -> JdProfile:
    from llm_stages import call_llm_stage

    prompt = f"""Extract from this job description ONLY phrases that appear verbatim (substring).
Output JSON: {{"priority_themes": [], "requirements": [], "keywords": []}}
Max 4 themes, 6 requirements, 12 keywords.

JD:
{jd_text[:2500]}"""
    raw = call_llm_stage(
        "jd_profile",
        "Output only valid JSON. Do not invent requirements not in the JD.",
        prompt,
        temperature=0.0,
        response_mime_type="application/json",
    )
    if raw:
        try:
            cleaned = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(cleaned)
            themes = [t for t in data.get("priority_themes", []) if _substring_valid(str(t), jd_text)]
            reqs = [r for r in data.get("requirements", []) if _substring_valid(str(r), jd_text)]
            kws = [k for k in data.get("keywords", []) if str(k).lower() in jd_text.lower()]
            if themes or reqs:
                return JdProfile(
                    priority_themes=themes[:4],
                    requirements=reqs[:6],
                    keywords=[str(k) for k in kws[:12]],
                    source="llm_validated",
                )
        except (json.JSONDecodeError, TypeError):
            pass
    return build_jd_profile_deterministic(jd_text, fit_summary)


def score_claim_for_jd(claim_text: str, profile: JdProfile, jd_text: str) -> int:
    text_l = claim_text.lower()
    jd_l = jd_text.lower()
    score = sum(1 for w in profile.keywords if w in text_l and w in jd_l)
    for req in profile.requirements:
        for token in re.findall(r"[a-z]{5,}", req.lower()):
            if token in text_l:
                score += 2
    for theme in profile.priority_themes:
        for token in re.findall(r"[a-z]{5,}", theme.lower()):
            if token in text_l:
                score += 1
    return score


def pick_cover_bullets(
    bullets: Dict[str, str],
    valid_ids: Dict[str, str],
    profile: JdProfile,
    jd_text: str,
    k: int = 2,
) -> List[str]:
    from local_draft_stages import employer_for_claim_id

    ranked = sorted(
        bullets.items(),
        key=lambda item: (
            score_claim_for_jd(valid_ids.get(item[0], item[1]), profile, jd_text),
            item[0],
        ),
        reverse=True,
    )
    picked: List[str] = []
    employers_seen = set()
    for cid, text in ranked:
        emp = employer_for_claim_id(cid)
        if emp in employers_seen and len(picked) >= k:
            continue
        picked.append(text)
        employers_seen.add(emp)
        if len(picked) >= k:
            break
    if len(picked) < k:
        for _, text in ranked:
            if text not in picked:
                picked.append(text)
            if len(picked) >= k:
                break
    return picked[:k]


def bridge_hints_for_jd(jd_text: str) -> str:
    jd_l = jd_text.lower()
    phrases = load_bridge_phrases()
    lines = []
    for key, out in phrases.items():
        if key.replace("_", " ") in jd_l or key in jd_l:
            lines.append(f"- When source relates to {key.replace('_', ' ')}, prefer framing: {out}")
    return "\n".join(lines[:8])
