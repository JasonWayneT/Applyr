"""
Claim Composition Engine — deterministic bullets from catalog.

Implements the hybrid vector-deterministic architecture.
Pulls text directly from master_claims.json.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

from claim_catalog import ClaimCatalog, load_catalog, sanitize_claim_text
from jd_tailoring import JdProfile, load_bridge_phrases, score_claim_for_jd
from local_draft_stages import (
    select_claims_deterministic,
    validate_bullet_for_local,
)
from verify_claims import extract_numeric_tokens

PRIMARY_METRIC_TOKENS = {"40", "40000000", "40000"}
MAX_BRIDGE_BULLETS = 1

def _draft_mode() -> str:
    return os.environ.get("DRAFT_MODE", "compose").lower()

def pick_bridge_prefix(jd_text: str) -> str:
    """At most one bridge clause per job (first matching JD keyword)."""
    phrases = load_bridge_phrases()
    jd_l = jd_text.lower()
    keys = sorted(phrases.keys(), key=lambda k: -len(k))
    for key in keys:
        if key.replace("_", " ") in jd_l or key in jd_l:
            phrase = phrases[key].strip()
            if len(phrase.split()) > 8:
                phrase = " ".join(phrase.split()[:6])
            return phrase[0].upper() + phrase[1:] + ": "
    return ""

def strip_bridge_prefix(bullet: str) -> str:
    """Remove leading bridge phrase for cover letter proof lines."""
    text = bullet.strip()
    phrases = load_bridge_phrases()
    for phrase in sorted(phrases.values(), key=len, reverse=True):
        p = phrase.strip()
        if not p:
            continue
        for prefix in (
            p[0].upper() + p[1:] + ": ",
            p[0].upper() + p[1:] + " — ",
            p + ": ",
            p + " — ",
        ):
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix) :].strip()
                break
    return text


def format_cover_proof_sentence(bullet: str) -> str:
    """Cover proof line: strip bridge prefix, capitalize, ensure terminal period."""
    text = strip_bridge_prefix(bullet).strip()
    if not text:
        return ""
    if text[0].islower():
        text = text[0].upper() + text[1:]
    return text if text.endswith(".") else f"{text}."


def compose_bullet(
    claim_id: str,
    catalog: ClaimCatalog,
    jd_text: str,
    profile: Optional[JdProfile] = None,
    use_bridge: bool = False,
) -> str:
    rec = catalog.claims.get(claim_id)
    if not rec:
        return ""
    
    # In the new architecture, the text is already perfectly styled.
    core = sanitize_claim_text(rec.body, catalog)
    
    prefix = pick_bridge_prefix(jd_text) if use_bridge else ""
    if prefix:
        # We lowercase the first letter of core if we prepend a prefix
        first_letter = core[0].lower() if core else ""
        rest_of_string = core[1:] if len(core) > 1 else ""
        bullet = (prefix + first_letter + rest_of_string).strip()
    else:
        bullet = core.strip()

    source_line = catalog.raw_truth_lines.get(claim_id, rec.body)
    valid, err = validate_bullet_for_local(source_line, bullet)
    
    if not valid:
        import sys
        print(f"    [Warning] Local validation failed for {claim_id}: {err}. Falling back to raw text.", file=sys.stderr)
        return core.strip()
        
    return bullet

def _metric_signature(text: str) -> frozenset:
    return frozenset(extract_numeric_tokens(text.replace(",", "")) & PRIMARY_METRIC_TOKENS)

def generate_bullets_compose(
    selected_ids: List[str],
    catalog: ClaimCatalog,
    jd_text: str,
    profile: Optional[JdProfile] = None,
) -> Tuple[Dict[str, str], int]:
    bullets: Dict[str, str] = {}
    fallback_count = 0
    used_primary_metric = False

    truth = catalog.truth_map()
    prof = profile or JdProfile()
    
    ranked = sorted(
        selected_ids,
        key=lambda cid: score_claim_for_jd(
            truth.get(cid, catalog.claims[cid].body if cid in catalog.claims else ""),
            prof,
            jd_text,
        ),
        reverse=True,
    )
    bridge_ids = {ranked[0]} if ranked else set()

    for claim_id in selected_ids:
        bullet = compose_bullet(
            claim_id, catalog, jd_text, profile, use_bridge=claim_id in bridge_ids
        )
        if not bullet:
            fallback_count += 1
            continue
            
        sig = _metric_signature(bullet)
        if sig & PRIMARY_METRIC_TOKENS and used_primary_metric:
            rec = catalog.claims.get(claim_id)
            if rec:
                bullet = sanitize_claim_text(rec.body, catalog)
        elif sig & PRIMARY_METRIC_TOKENS:
            used_primary_metric = True

        bullets[claim_id] = bullet

    return bullets, fallback_count

def generate_bullets_for_claims(
    selected_ids: List[str],
    valid_ids: Dict[str, str],
    jd_text: str,
    profile: Optional[JdProfile] = None,
):
    """Entry: compose mode (default) or legacy LLM bullets."""
    from pipeline_env import assert_draft_mode_allowed

    assert_draft_mode_allowed()
    if _draft_mode() == "legacy_llm":
        from bullet_generation import generate_bullets_for_claims as llm_gen
        return llm_gen(selected_ids, valid_ids, jd_text, profile=profile)

    catalog = load_catalog()
    if not catalog.claims:
        from bullet_generation import generate_bullets_for_claims as llm_gen
        return llm_gen(selected_ids, valid_ids, jd_text, profile=profile)

    return generate_bullets_compose(selected_ids, catalog, jd_text, profile)

def select_claims_with_catalog(
    jd_text: str,
    catalog: ClaimCatalog,
    profile: Optional[JdProfile] = None,
    per_employer: int = 3,
) -> List[str]:
    truth = catalog.truth_map()
    selected = select_claims_deterministic(jd_text, truth, per_employer=per_employer)
    if profile:
        selected = sorted(
            selected,
            key=lambda cid: score_claim_for_jd(
                truth.get(cid, catalog.claims[cid].body if cid in catalog.claims else ""),
                profile,
                jd_text,
            ),
            reverse=True,
        )
    return selected
