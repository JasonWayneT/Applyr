"""
Per-stage LLM provider preferences.

Implements FR-093 (CR-014); local-only routing when FR-100–104 local policy active (CR-017).
"""
import os

from utils import call_llm, load_llm_settings, _get_configured_providers

STAGE_PROVIDERS = {
    "jd_profile": ["local", "gemini"],
    "claim_select": ["local", "gemini"],
    "bullet": ["local", "gemini"],
}


def local_only_mode() -> bool:
    if os.environ.get("LOCAL_ONLY_MODE", "").lower() in ("1", "true", "yes"):
        return True
    settings = load_llm_settings()
    primary = settings.get("primaryProvider") or settings.get("provider", "gemini")
    return primary == "local"


def call_llm_stage(stage_id: str, system_prompt: str, user_prompt: str, **kwargs):
    settings = load_llm_settings()
    configured = _get_configured_providers(settings)
    if local_only_mode():
        preferred = ["local"]
    else:
        preferred = STAGE_PROVIDERS.get(stage_id, ["local", "gemini"])
    providers = [p for p in preferred if p in configured]
    if not providers:
        providers = configured
    return call_llm(
        system_prompt,
        user_prompt,
        provider_override=providers,
        **kwargs,
    )
