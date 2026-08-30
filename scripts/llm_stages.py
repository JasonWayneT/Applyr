"""
Per-stage LLM provider preferences.

Implements FR-093 (CR-014), FR-133, FR-134 (CR-021);
local-only routing when FR-100–104 policy active (CR-017).

OPT-IN / LOCAL-LLM SURFACE (CR-070 kept-intact decision): still used by the
UI Draft path (batch_pipeline → drafting_engine) and by CR-062 local_rewrite.
Default generate-submission Stage 1 authoring does not call this. Do not
archive until the server batch_pipeline wire is intentionally retired.
"""
import os

from utils import call_llm, load_llm_settings, _get_configured_providers

# CR-106: intentionally not unified onto taskProviderOverrides. This is a separate, older
# per-stage override used only by the legacy/opt-in UI Draft path (batch_pipeline →
# drafting_engine) and CR-062 local_rewrite — not the default generate-submission Stage 1
# authoring flow. Unifying it would risk regressing a working mechanism for a path that
# isn't used day to day. Scope cut, not an oversight.
STAGE_PROVIDERS = {
    "jd_profile": ["local", "gemini"],
    "claim_select": ["local", "gemini"],
    "bullet": ["local", "gemini"],
    "fit": ["local", "gemini"],
    # Local-only, no cloud fallback: this stage exists specifically to prove local-model
    # reliability (CR-062 / Deterministic-Minimal-LLM), so silently falling through to a
    # cloud provider on local failure would defeat the point. call_llm_stage below enforces
    # this — it raises rather than substituting a cloud provider for a hard-local stage.
    "rewrite": ["local"],
    "evidence_scale": ["local"],
}

STAGE_MODEL_KEYS = {
    "jd_profile": "localModelJdProfile",
    "claim_select": "localModelClaimSelect",
    "bullet": "localModelBullet",
    "fit": "localModelFit",
    "rewrite": "localModelRewrite",
}

# Stages in this set must never silently substitute a different provider than the ones
# listed in STAGE_PROVIDERS, even if none of them are "configured" — see call_llm_stage.
_HARD_PROVIDER_STAGES = {"rewrite", "evidence_scale"}


def local_only_mode() -> bool:
    if os.environ.get("LOCAL_ONLY_MODE", "").lower() in ("1", "true", "yes"):
        return True
    settings = load_llm_settings()
    primary = settings.get("primaryProvider") or settings.get("provider", "gemini")
    return primary == "local"


def stage_model(stage_id: str) -> str | None:
    settings = load_llm_settings()
    key = STAGE_MODEL_KEYS.get(stage_id)
    if key and settings.get(key):
        return settings[key]
    defaults = {
        "fit": settings.get("localModelFit") or "qwen2.5:7b-instruct-q4_K_M",
        "jd_profile": settings.get("localModel") or "llama3.1:8b-instruct-q5_K_M",
        "rewrite": settings.get("localModelRewrite") or "qwen2.5:7b-instruct-q4_K_M",
        "evidence_scale": "qwen2.5:7b-instruct-q4_K_M",
    }
    return defaults.get(stage_id)


def call_llm_stage(stage_id: str, system_prompt: str, user_prompt: str, **kwargs):
    settings = load_llm_settings()
    configured = _get_configured_providers(settings)
    if local_only_mode():
        preferred = ["local"]
    else:
        preferred = STAGE_PROVIDERS.get(stage_id, ["local", "gemini"])
    providers = [p for p in preferred if p in configured]
    if not providers:
        if stage_id in _HARD_PROVIDER_STAGES:
            raise RuntimeError(
                f"Stage '{stage_id}' requires {preferred} but none are configured; "
                "refusing to silently substitute a different provider."
            )
        providers = configured
    model = kwargs.pop("model", None) or stage_model(stage_id)
    return call_llm(
        system_prompt,
        user_prompt,
        provider_override=providers,
        model=model,
        **kwargs,
    )
