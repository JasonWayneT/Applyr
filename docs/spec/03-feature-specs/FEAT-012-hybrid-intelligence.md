# FEAT-012: Hybrid Local-Cloud Intelligence & Failover

## 1. Overview
Empower the platform to utilize locally-hosted LLMs (via Ollama) for high-throughput operations while dynamically pivoting to cloud models for high-fidelity creative generation. Includes automated resource recovery hooks to maintain desktop health.

## 2. Impacted requirements
- `FR-065`: Intra-Local Model Failover
- `FR-066`: Automatic VRAM Reclamation (Eco-Hook)
- `FR-067`: Hybrid Intelligence Switching
- `FR-071`: Local Model Deterministic Sampling Override *(CR-007)*
- `FR-072`: Two-Phase Local Resume Generation *(CR-007)*
- `FR-081`–`FR-088`: Structured compiler + hardening *(CR-012, CR-013)*
- `FR-089`–`FR-094`: Unified draft compiler — one pipeline for all providers *(CR-014)*
- `FR-100`–`FR-104`: Local claim composition engine — compose-mode bullets, fail-closed verification *(CR-017)*
- `FR-105`–`FR-108`: Zero-touch draft polish — sentence-complete bullets, one bridge, fresh summaries, template cheat sheets *(CR-018)*
- `FR-131`–`FR-150`: Local funnel + compose hardening — pre-score, strict local-only, stage models, template hooks, manifest audit *(CR-021)*

## 3. Design description
The core LLM Router (`utils.py`) manages traffic shaping between local resources and external APIs.

### 3.1 Component Architecture
1.  **Router Override:** `call_llm()` modified to accept `provider_override` param. This gates high-risk calls (Drafting, Verification) explicitly to cloud tier.
2.  **Cascading Local Failover:** `_call_local()` encapsulates try-catch logic looping through `primary` -> `fallback` model definitions loaded from internal state.
3.  **Eco-Hook Handlers:** Native teardown routines triggered via Python `atexit` and standard `finally` blocks push `keep_alive: 0` payload to Ollama API to reclaim system memory instantly.
4.  **Deterministic Sampling Override (FR-071):** `_call_local()` unconditionally overrides caller-supplied temperature with `0.0` and caps `num_predict` at `1000`. `top_k: 40`, `top_p: 0.9` constrain the token distribution. A log line confirms the override. `LOCAL_CONSTRAINT_PREFIX` includes two concrete WRONG/CORRECT bullet examples for few-shot grounding.
5.  **Unified Draft Compiler (FR-089–094, CR-014):** `run_drafting_engine()` delegates only to `draft_compiler.run()`. Gemini and local execute the same stages via `call_llm_stage(stage_id)`:
    - **Stage 1 — JdProfile:** Validated JD themes/requirements (+ fit summary boost).
    - **Stage 2 — Claim selection:** Per-employer JSON or keyword fallback.
    - **Stage 3 — Bullets:** One claim per call with bridge phrase bank + gates; `bullet_generation.fallback_bullet()` on failure.
    - **Stages 4–6 — Summary/cover:** Deterministic templates; JD-ranked proof bullets.
    - **Stage 8+ — verify_content, guards, QA, PDF, `draft_manifest.json`.**
    - Research packet is **not** injected into resume/cover (cheat sheet only).
6.  **Claim Composition Engine (FR-100–104, CR-017):** Default `DRAFT_MODE=compose`. Bullets are rendered from the parsed ACC catalog (`claim_catalog.py`) with Section 3 VOC replacements and JD bridge prefixes (`claim_composer.py`). Per-claim LLM rewrite is opt-in via `DRAFT_MODE=legacy_llm` only.
7.  **Draft polish (FR-105–108, CR-018):** `bullet_fit.py` sentence-aware caps; one bridge bullet per job; cover proofs strip bridge prefixes; Backlog summaries refreshed on success; `generate_cheat_sheet.py` template mode by default.
    - **Stage 3 (compose):** No LLM call per bullet in default mode; `preserves_core_facts` + tool/seniority gates still apply.
    - **Verification chain:** `verification_chain.verify_document_bundle()` runs after assembly — `verify_content` failure is **blocking**; `recruiter_qa` enforces no ID tokens, slug company names, or repeated $40M ARR.
    - **Display company:** `batch_pipeline` passes SQLite `jobs.company` as `display_name` for cover letter salutation (not folder slug).
    - **Local-first routing:** `llm_stages.local_only_mode()` forces `['local']` for JD profile / claim select / fit eval when `LOCAL_ONLY_MODE=1` or `primaryProvider: local`.
8.  **CR-021 compose defaults:** `pipeline_env.py` sets deterministic JdProfile and template cover hooks in compose mode. `utils.call_llm` does not fall through to cloud when `LOCAL_ONLY_MODE=1`. Fit eval uses `call_llm_stage('fit')` with BM25-pruned work experience and JSON schema. Pre-score (`pre_score_jobs.py`) orders batch queue before fit LLM.

## 4. User interactions
- Zero user interactions required for normal switching; routing decisions reside inside the automation engine algorithms.
- Users notice dramatically reduced system VRAM usage between pipeline runs.
- Drafting engines maintain hallucination-suppressed fidelity even if local is set as primary global model; invented numbers and tools are caught and discarded before output.

## 5. Verification Plan
- **Automation:** `scripts/smoke_draft_compiler.py` — catalog load, `strip_ids`, compose bullet, JD profile, employer routing, bullet gates, claim scoring *(CR-017 AC-100–104)*.
- **Automation:** `smoke_test_gemma.py` for local sampling when LLM stages enabled.
- **Manual:** Regenerate a Backlog submission folder; confirm `draft_manifest.json` has `pipeline_version: CR-017-1`, `draft_mode: compose`, `verification_passed: true`, and no `ACC-`/`MET-` tokens in `Resume.md` / `CoverLetter.md`.
- **Manual:** Watch system memory task manager upon script completion to confirm immediate unloading.
- **Hallucination check:** Inspect `[HARD FACT AUDIT]` log — target is 0 invented-number warnings; pipeline must not reach Backlog if `recruiter_qa` fails.
