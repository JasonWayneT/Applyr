"""
Central pipeline environment flags.

Implements FR-131, FR-136, FR-141, FR-150 (CR-021).
See .agent/rules/pipeline_env.md and docs/spec/05-change-requests/CR-021-local-funnel-compose-hardening.md.

Defaults favor compose-mode drafting with deterministic JD profile and cover hooks.
"""
from __future__ import annotations

import os


def _flag(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip().lower()


def draft_mode() -> str:
    return _flag("DRAFT_MODE", "compose")


def local_only_mode() -> bool:
    return _flag("LOCAL_ONLY_MODE") in ("1", "true", "yes")


def stage0_section_mode() -> str:
    """llm | deterministic -- which extractor build_stage0_fit_gate.py's
    _extract_sections_llm()/_extract_sections() split uses. Defaults to
    "llm" (2026-08-17, Jason-supplied): the regex header-matcher proved
    unreliable across real JD phrasing (see build_stage0_fit_gate.py's module
    docstring). This flag only controls whether the LLM path is attempted at
    all (tests / explicit offline runs). A failed LLM extract raises rather
    than silently using the regex extractor."""
    return _flag("STAGE0_SECTION_MODE", "llm")


# DRAFT_MODE values that keep the compose-path deterministic defaults (JD profile,
# cover hook). "local_rewrite" (CR-062) is an additive layer on top of "compose" — it
# changes how already-selected text is phrased, not how the JD gets profiled or which
# cover-hook mode runs — so it must not silently fall through to the "llm" branch below
# the way an unrecognized DRAFT_MODE value does.
_COMPOSE_LIKE_DRAFT_MODES = ("compose", "local_rewrite")


def jd_profile_mode() -> str:
    """deterministic | llm — compose(-like) path defaults to deterministic."""
    mode = _flag("JD_PROFILE_MODE")
    if not mode:
        return "deterministic" if draft_mode() in _COMPOSE_LIKE_DRAFT_MODES else "llm"
    return mode


def cover_hook_mode() -> str:
    """template | llm — template avoids ungrounded cover openings."""
    mode = _flag("COVER_HOOK_MODE")
    if not mode:
        return "template" if draft_mode() in _COMPOSE_LIKE_DRAFT_MODES else "llm"
    return mode


def research_mode() -> str:
    """local | skip | cloud — local uses SearXNG; skip uses template cheat sheet only."""
    return _flag("RESEARCH_MODE", "local" if local_only_mode() else "cloud")


def batch_fast_mode() -> bool:
    """Faster batch: smaller fit model, skip optional embed steps, no inter-job sleep."""
    return _flag("BATCH_FAST_MODE") in ("1", "true", "yes")


def skip_metadata_tagger() -> bool:
    if _flag("SKIP_METADATA_TAGGER") in ("1", "true", "yes"):
        return True
    return batch_fast_mode()


def anchor_gate_enabled() -> bool:
    """Implements FR-172 (CR-028) — deterministic two-anchor gate; default off."""
    return _flag("ANCHOR_GATE_ENABLED") in ("1", "true", "yes")


def skip_duplicate_vector_check() -> bool:
    if _flag("SKIP_DUPLICATE_VECTOR") in ("1", "true", "yes"):
        return True
    return batch_fast_mode()


def resume_bullet_quotas() -> dict[str, int]:
    """
    Target bullets per employer on composed resumes (default 5 / 3 / 3).
    Override: RESUME_BULLET_QUOTAS=acme_corp:5,example_inc:3,startup_co:3
    """
    from candidate_context import default_resume_bullet_quotas

    defaults = default_resume_bullet_quotas()
    raw = os.environ.get("RESUME_BULLET_QUOTAS", "").strip()
    if not raw:
        return defaults
    out = dict(defaults)
    for part in raw.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        key, val = part.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        try:
            out[key] = max(1, int(val.strip()))
        except ValueError:
            pass
    return out


def resume_only_mode() -> bool:
    return _flag("RESUME_ONLY") in ("1", "true", "yes")


def cover_only_mode() -> bool:
    return _flag("COVER_ONLY") in ("1", "true", "yes")


def apply_quality_batch_defaults() -> None:
    """
    Safe local-batch defaults — does not override explicit env vars.
    Keeps full-size fit model; removes reload/sleep overhead only.
    """
    if batch_fast_mode() or not local_only_mode():
        return
    os.environ.setdefault("BATCH_UNLOAD_MODELS", "0")
    os.environ.setdefault("BATCH_INTER_JOB_SLEEP_SEC", "2")
    os.environ.setdefault("FIT_NUM_PREDICT", "768")


def batch_inter_job_sleep_sec() -> float:
    if batch_fast_mode():
        return 0.0
    raw = os.environ.get("BATCH_INTER_JOB_SLEEP_SEC", "").strip()
    if raw:
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
    return 2.0 if local_only_mode() else 8.0


def batch_unload_models_between_jobs() -> bool:
    """Default: keep Ollama models loaded between jobs when running local batch."""
    if _flag("BATCH_UNLOAD_MODELS") in ("0", "false", "no"):
        return False
    if _flag("BATCH_UNLOAD_MODELS") in ("1", "true", "yes"):
        return True
    if batch_fast_mode() or local_only_mode():
        return False
    return True


def fit_num_predict() -> int:
    raw = os.environ.get("FIT_NUM_PREDICT", "").strip()
    if raw:
        try:
            return max(128, int(raw))
        except ValueError:
            pass
    if batch_fast_mode():
        return 512
    if local_only_mode():
        return 768
    return 1024


def fit_model_override() -> str | None:
    """Optional local model for fit stage (fast mode uses primary llama, not phi)."""
    explicit = os.environ.get("FIT_MODEL", "").strip()
    if explicit:
        return explicit
    if batch_fast_mode():
        return "llama3.1:8b-instruct-q5_K_M"
    return None


def batch_parallel_workers() -> int:
    """Evaluate/draft jobs sequentially by default (honest progress, one GPU fit at a time)."""
    raw = os.environ.get("BATCH_PARALLEL_WORKERS", "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def fit_llm_timeout_sec() -> int:
    """HTTP timeout for local fit LLM calls (prevents hung qwen from blocking the batch)."""
    raw = os.environ.get("FIT_LLM_TIMEOUT_SEC", "180").strip()
    try:
        return max(30, int(raw))
    except ValueError:
        return 180


def fit_eval_top_n() -> int | None:
    raw = os.environ.get("FIT_EVAL_TOP_N", "").strip()
    if not raw:
        return None
    try:
        n = int(raw)
        return n if n > 0 else None
    except ValueError:
        return None


def strict_cover_audit() -> bool:
    """CR-031 — block export when cover_letter_audit grade != Pass."""
    return _flag("STRICT_COVER_AUDIT") in ("1", "true", "yes")


def block_cover_pdf_on_audit_fail() -> bool:
    """Skip CoverLetter.pdf when cover audit grade != Pass (default on)."""
    return _flag("ALLOW_COVER_AUDIT_FAIL") not in ("1", "true", "yes")


def strict_metrics() -> bool:
    """CR-031 — raise on unapproved numeric tokens in verification chain."""
    return _flag("STRICT_METRICS") in ("1", "true", "yes")


def strict_anti_claims() -> bool:
    """CR-031 — enforce workExperience anti-claim hints."""
    return _flag("STRICT_ANTI_CLAIMS") in ("1", "true", "yes")


def strict_catalog_drift() -> bool:
    """CR-031 — fail compile when master_claims drifts from workExperience."""
    return _flag("STRICT_CATALOG_DRIFT") in ("1", "true", "yes")


def strict_conversion_critique() -> bool:
    """CR-042 — block export when conversion_critique.pass is false."""
    return _flag("STRICT_CONVERSION_CRITIQUE") in ("1", "true", "yes")


def conversion_retry_max() -> int:
    """CR-042 — max auto-retry attempts before strict gate (default 2)."""
    raw = (os.environ.get("CONVERSION_RETRY_MAX") or "2").strip()
    try:
        n = int(raw)
        return max(1, min(n, 5))
    except ValueError:
        return 2


def allow_fit_summary() -> bool:
    """When false (default), do not append fit-eval sentence to resume summary."""
    return _flag("ALLOW_FIT_SUMMARY") in ("1", "true", "yes")


def assert_draft_mode_allowed() -> None:
    if local_only_mode() and draft_mode() == "legacy_llm":
        raise RuntimeError(
            "DRAFT_MODE=legacy_llm is blocked when LOCAL_ONLY_MODE=1. "
            "Use DRAFT_MODE=compose for fact-grounded bullets."
        )


def submission_mode() -> bool:
    """True when SUBMISSION_MODE=1 is set.

    Activates all strict guards for real employer submissions:
      - STRICT_METRICS=1      (unapproved numbers are hard errors)
      - STRICT_COVER_AUDIT=1  (cover letter must pass audit or pipeline fails)
      - STRICT_ANTI_CLAIMS=1  (anti-claim violations block export)
      - USE_BRIDGE_PREFIXES=0 (JD-derived reframing disabled)
      - ALLOW_FIT_SUMMARY=0   (LLM fit sentence blocked from summary)
      - DRAFT_MODE=compose    (deterministic bullets only)
      - COVER_HOOK_MODE=template (no LLM cover hook)

    Equivalent to setting all of the above individually. Prefer this flag
    for all real application runs to avoid forgetting a guard.
    """
    return _flag("SUBMISSION_MODE") in ("1", "true", "yes")


def apply_submission_defaults() -> None:
    """Enforce all strict guards when SUBMISSION_MODE=1.

    Call early in any pipeline entry point. Uses setdefault so explicit
    overrides in the environment still take precedence.
    """
    if not submission_mode():
        return
    os.environ.setdefault("STRICT_METRICS", "1")
    os.environ.setdefault("STRICT_COVER_AUDIT", "1")
    os.environ.setdefault("STRICT_ANTI_CLAIMS", "1")
    os.environ.setdefault("STRICT_CONVERSION_CRITIQUE", "1")
    os.environ.setdefault("USE_BRIDGE_PREFIXES", "0")
    os.environ.setdefault("ALLOW_FIT_SUMMARY", "0")
    os.environ.setdefault("DRAFT_MODE", "compose")
    os.environ.setdefault("COVER_HOOK_MODE", "template")
