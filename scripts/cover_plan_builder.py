"""Rules-only cover letter plan builder (CR-024)."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional  # noqa: F401 used by research_hook

from claim_catalog import ClaimCatalog, load_catalog
from cover_claim_picker import pick_cover_proofs
from cover_letter_structure import detect_archetype
from cover_jd_needs import extract_jd_goal, extract_ranked_needs, extract_role_title
from cover_letter_plan import CoverLetterPlan
from jd_tailoring import build_jd_profile_deterministic, extract_jd_pain_points
from match_thesis_builder import apply_match_blocks

RESEARCH_ALLOWLIST = ("product", "mission", "recent_initiative", "referral")


def _load_research_packet(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def research_hook_from_packet(packet: Dict[str, Any], jd_text: str) -> Optional[str]:
    from jd_tailoring import _substring_valid

    for key in RESEARCH_ALLOWLIST:
        val = packet.get(key)
        if not val or not isinstance(val, str):
            continue
        val = val.strip()
        if 20 <= len(val) <= 200 and _substring_valid(val, jd_text):
            return val
    return None


def build_cover_plan(
    jd_text: str,
    company_display: str,
    catalog: Optional[ClaimCatalog] = None,
    research_packet_path: Optional[str] = None,
    bullet_corpus: str = "",
) -> CoverLetterPlan:
    catalog = catalog or load_catalog()
    profile = build_jd_profile_deterministic(jd_text)
    ranked_needs = extract_ranked_needs(jd_text, profile)
    pain_points = extract_jd_pain_points(jd_text)
    proofs = pick_cover_proofs(catalog, ranked_needs, profile, jd_text, k=4)
    archetype_id = detect_archetype(jd_text, ranked_needs)
    if archetype_id == "marketplace_fintech":
        opening_variant = "need_first"
    elif archetype_id == "product_domain":
        opening_variant = "domain_first"
    else:
        opening_variant = "application_first"

    plan = CoverLetterPlan(
        company_display=company_display,
        role_title=extract_role_title(jd_text),
        ranked_needs=ranked_needs,
        proofs=proofs,
        opening_variant=opening_variant,
        archetype_id=archetype_id,
        jd_goal=extract_jd_goal(jd_text, ranked_needs),
        pain_points=pain_points,
    )

    packet = _load_research_packet(research_packet_path or "")
    hook = research_hook_from_packet(packet, jd_text)
    if hook:
        plan.research_hook = hook

    return apply_match_blocks(plan, profile, jd_text=jd_text, bullet_corpus=bullet_corpus)
