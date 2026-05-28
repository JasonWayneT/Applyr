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
            "You are a strict resume parsing engine. Your job is to extract the action verb and objective from an achievement, "
            "optimizing them for the provided job context. Output ONLY valid JSON matching this exact schema: "
            "{\"action_verb\": \"<single past-tense verb>\", \"objective\": \"<what was done, under 15 words>\"}"
        )
        
        user = f"""Rewrite the achievement below to highlight its relevance to the job. Output JSON.
        
EXAMPLES:
Input: * **[ACC-101] Data Pipeline**: Built a data ingestion pipeline using Python that processed 40M records.
Output: {{"action_verb": "Engineered", "objective": "Python-based data ingestion pipeline"}}

Input: * **[ACC-102] Sales**: Led a team of 5 to increase sales by 20%.
Output: {{"action_verb": "Directed", "objective": "cross-functional sales initiative"}}

Input: * **[ACC-103] API Integration**: Integrated Stripe API to process payments, reducing latency.
Output: {{"action_verb": "Integrated", "objective": "Stripe API payment processing system"}}

JOB CONTEXT (first 600 chars):
{jd_text[:600]}

{req_block}

{bridge_block}

ORIGINAL ACHIEVEMENT:
{source_text}

Rules:
- NEVER include the metrics or numbers in your JSON. We will append them automatically.
- action_verb must be a single strong past-tense verb.
- objective must be under 15 words.
- ONLY output JSON."""

        # Use the options_override to ban vibe words and response_schema to enforce JSON
        vibe_words_penalty = {
            "synergy": -100, "leverage": -100, "spearheaded": -100, "passionate": -100,
            "transformative": -100, "dynamic": -100, "innovative": -100
        }
        
        schema = {
            "type": "object",
            "properties": {
                "action_verb": {"type": "string"},
                "objective": {"type": "string"}
            },
            "required": ["action_verb", "objective"]
        }

        from utils import call_llm
        result = call_llm(
            system, user, 
            temperature=0.0, 
            response_mime_type="application/json",
            options_override={"logit_bias": vibe_words_penalty},
            response_schema=schema
        )

        if result:
            import json
            from utils import extract_json_from_text
            try:
                data = json.loads(extract_json_from_text(result))
                action = data.get("action_verb", "").strip()
                obj = data.get("objective", "").strip()
                
                # Extract the metric clause from the original source deterministically
                from local_draft_stages import _first_metric_clause
                metric_clause = _first_metric_clause(source_text)
                
                if action and obj:
                    if metric_clause:
                        bullet = f"{action} {obj}, {metric_clause}."
                    else:
                        bullet = f"{action} {obj}."
                else:
                    bullet = fallback_bullet(source_text)
            except Exception as e:
                print(f"    [Stage 3] JSON parsing failed: {e}. Using source fallback.")
                bullet = fallback_bullet(source_text)
                
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
