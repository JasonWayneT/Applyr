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

from utils import call_llm, load_llm_settings, _get_configured_providers, _is_configured

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
    # 2026-09-01: evidence_scale moved from ["local"] to ["groq", "gemini"] — Stage 0
    # no longer uses local Ollama for any LLM call. The NLP classifier (scikit-learn) is
    # the primary extractor; Groq/Gemini handle all cloud fallback including per-item
    # evidence classification and the responsibilities exclusion-zone scanner. Local
    # Ollama is not in the Stage 0 provider chain at all.
    "evidence_scale": ["groq", "gemini"],
    # CR-110 Gap A: LLM-based industry classification — supplementary to the keyword
    # industry gate. Uses the same cloud providers as evidence_scale.
    "industry_semantic": ["groq", "gemini"],
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
# 2026-09-01: evidence_scale removed from _HARD_PROVIDER_STAGES — it now uses
# Groq/Gemini (cloud), not local, so the "refuse to substitute" guard no longer applies.
_HARD_PROVIDER_STAGES = {"rewrite"}


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
        # 2026-09-01: evidence_scale now uses cloud providers (Groq/Gemini). Return
        # None so call_llm uses each provider's own default model (openai/gpt-oss-120b
        # for Groq, gemini-3.5-flash-lite for Gemini) instead of a local model name.
        "evidence_scale": None,
    }
    return defaults.get(stage_id)


def call_llm_stage(stage_id: str, system_prompt: str, user_prompt: str, **kwargs):
    settings = load_llm_settings()
    configured = _get_configured_providers(settings)
    if local_only_mode():
        preferred = ["local"]
    else:
        preferred = STAGE_PROVIDERS.get(stage_id, ["local", "gemini"])
    # 2026-09-01: use _is_configured directly instead of membership in configured,
    # so that Groq (deliberately excluded from _get_configured_providers' fixed_order
    # because it's task-scoped) still works when a stage explicitly lists it.
    providers = [p for p in preferred if _is_configured(p, settings)]
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
