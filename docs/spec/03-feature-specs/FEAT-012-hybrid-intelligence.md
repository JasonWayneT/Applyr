# FEAT-012: Hybrid Local-Cloud Intelligence & Failover

## 1. Overview
Empower the platform to utilize locally-hosted LLMs (via Ollama) for high-throughput operations while dynamically pivoting to cloud models for high-fidelity creative generation. Includes automated resource recovery hooks to maintain desktop health.

## 2. Impacted requirements
- `FR-065`: Intra-Local Model Failover
- `FR-066`: Automatic VRAM Reclamation (Eco-Hook)
- `FR-067`: Hybrid Intelligence Switching
- `FR-071`: Local Model Deterministic Sampling Override *(CR-007)*
- `FR-072`: Two-Phase Local Resume Generation *(CR-007)*

## 3. Design description
The core LLM Router (`utils.py`) manages traffic shaping between local resources and external APIs.

### 3.1 Component Architecture
1.  **Router Override:** `call_llm()` modified to accept `provider_override` param. This gates high-risk calls (Drafting, Verification) explicitly to cloud tier.
2.  **Cascading Local Failover:** `_call_local()` encapsulates try-catch logic looping through `primary` -> `fallback` model definitions loaded from internal state.
3.  **Eco-Hook Handlers:** Native teardown routines triggered via Python `atexit` and standard `finally` blocks push `keep_alive: 0` payload to Ollama API to reclaim system memory instantly.
4.  **Deterministic Sampling Override (FR-071):** `_call_local()` unconditionally overrides caller-supplied temperature with `0.0` and caps `num_predict` at `1000`. `top_k: 40`, `top_p: 0.9` constrain the token distribution. A log line confirms the override. `LOCAL_CONSTRAINT_PREFIX` includes two concrete WRONG/CORRECT bullet examples for few-shot grounding.
5.  **Two-Phase Generation (FR-072):** When `is_local_provider_active()` is True, `run_drafting_engine()` routes to `_generate_resume_local_twophase()`:
    - **Phase 1 — Selection:** `call_local_json()` sends only the ACC ID menu + compressed JD with `format: "json"` and `num_predict: 200`. Model returns `{"selected_ids": [...]}`. Tiny task, near-impossible to hallucinate.
    - **Phase 2 — Bullet Generation:** For each selected ID, one focused call returns 2 bullets. Each call is ≤ 150 tokens output. Per-bullet `preserves_core_facts()` runs before LLM self-verification; on failure, `_fallback_bullet()` reformats source text directly.
    - `llm_verify_claims()` is bypassed for local output; deterministic guards (`validate_hard_facts`) run instead.

## 4. User interactions
- Zero user interactions required for normal switching; routing decisions reside inside the automation engine algorithms.
- Users notice dramatically reduced system VRAM usage between pipeline runs.
- Drafting engines maintain hallucination-suppressed fidelity even if local is set as primary global model; invented numbers and tools are caught and discarded before output.

## 5. Verification Plan
- **Automation:** Validated via `smoke_test_gemma.py` and standard unbuffered shell logging.
- **Manual:** Watch system memory task manager upon script completion to confirm immediate unloading.
- **Hallucination check:** Inspect `[HARD FACT AUDIT]` log after a local-model run — target is 0 invented-number warnings.
