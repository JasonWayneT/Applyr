"""
Per-claim resume bullet generation (CR-014 Stage 3).
"""
import re

from local_draft_stages import validate_bullet_for_local
from jd_tailoring import bridge_hints_for_jd
from llm_stages import call_llm_stage


def fallback_bullet(source_text: str) -> str:
    """Reformat ground-truth line as a plain bullet without LLM creativity."""
    clean = re.sub(r"\[(ACC|MET|VOC)-\d+\]", "", source_text)
    clean = re.sub(r"\*+", "", clean)
    clean = clean.strip().lstrip("-•").strip()
    if clean and not clean.endswith("."):
        clean += "."
    return clean


def generate_bullets_for_claims(selected_ids, valid_ids, jd_text, profile=None):
    """
    Compose-mode (default) or legacy LLM per claim. Returns (bullets dict, fallback_count).
    """
    import os
    if os.environ.get("DRAFT_MODE", "compose").lower() != "legacy_llm":
        from claim_composer import generate_bullets_for_claims as compose_entry
        return compose_entry(selected_ids, valid_ids, jd_text, profile=profile)

    # Legacy: one LLM call per claim; gates + fallback.
    req_block = ""
    if profile and getattr(profile, "requirements", None):
        req_block = "PRIORITY JD REQUIREMENTS:\n" + "\n".join(
            f"- {r}" for r in profile.requirements[:3]
        )

    bridge = bridge_hints_for_jd(jd_text)
    bridge_block = f"ALLOWED BRIDGE FRAMING:\n{bridge}" if bridge else ""

    bullets = {}
    fallback_count = 0
    for claim_id in selected_ids:
        source_text = valid_ids.get(claim_id, "")
        if not source_text:
            continue

        system = (
            "You are a resume bullet writer. Write exactly ONE resume bullet point. "
            "Output ONLY the bullet — no preamble, no ID tags, no explanation."
        )
        user = f"""Rewrite the achievement below as one resume bullet point reframed for the job.

ORIGINAL ACHIEVEMENT:
{source_text}

JOB CONTEXT (first 600 chars):
{jd_text[:600]}

{req_block}

{bridge_block}

Rules:
- Keep ALL numbers and dollar values EXACTLY as stated in the original
- Do NOT invent tools, metrics, or facts not in the original
- Do NOT add technologies from the JD unless they appear in the original
- Start with an action verb
- Maximum 25 words
- Output the bullet only

Bullet:"""

        result = call_llm_stage("bullet", system, user, temperature=0.0)

        if result:
            bullet = result.strip().lstrip("-•").strip()
            valid, err = validate_bullet_for_local(source_text, bullet)
            if valid:
                bullets[claim_id] = bullet
            else:
                print(f"    [Stage 3] {claim_id} failed validation ({err}). Using source fallback.")
                bullets[claim_id] = fallback_bullet(source_text)
                fallback_count += 1
        else:
            bullets[claim_id] = fallback_bullet(source_text)
            fallback_count += 1

    if fallback_count:
        print(f"    [Stage 3] {fallback_count} bullet(s) used deterministic fallback.")
    return bullets, fallback_count
