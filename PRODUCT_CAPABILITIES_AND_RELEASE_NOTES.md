# Applyr — Product Capabilities & Release Notes

Welcome to the definitive product capabilities registry and release ledger for **Applyr (The Curated Job Hunt Agent)**. This document serves as the single source of truth for the system's operational architecture and product milestones.

---

## Part 1: Core System Capabilities (Today)

Applyr is a highly specialized, local-first intelligence platform designed to automate the job search lifecycle—from automated discovery and deterministic fit filtering to bespoke resume drafting, WYSIWYG visual asset editing, and application lifecycle tracking. All provider credentials and search preferences live in a local SQLite database configured through the Settings UI—no `.env` file required.

### 1. Automated Job Scouting & Crawling Pipeline
*   **Multi-Platform Scraping Engine:** Orchestrates automated crawls across Built In, public job APIs, optional Adzuna/OpenPostings, and ATS watchlists via Playwright where needed. LinkedIn ingestion is **decommissioned** (CR-010).
*   **Intelligent URL Backfilling:** Allows manual URL injection that automatically scrapes raw job descriptions on the fly, feeding them straight into the evaluation pipeline.
*   **Company DNA Perplexity Intelligence:** Executes targeted real-time Perplexity queries to extract company missions, problem spaces, financial status, and competitor matrices into a `Research_Packet.md` file.

### 2. Deterministic Job-Fit Scoring Engine (Stage A & Stage B)
*   **The Fast Gate (Instant Kill):** A deterministic filter that instantly rejects roles with mismatched seniority levels, solo-PM traps ("0-to-1 PM", "Founding PM"), low compensations (<$70k), or non-US based locations.
*   **Multi-Dimensional Scoring:** Evaluates JDs across four distinct vectors (Direct Leadership/Mentorship availability, Seniority Fit, Technical Execution Depth, and Transition potential) to produce a weighted score from `0` to `100`.
*   **Anchor Safeguard Room:** Validates that a role contains at least two core overlaps (Platform stability, complex migrations, security compliance, or enterprise B2B workflows) before allowing a greenlight.

### 3. Bespoke Asset Generation (The Bridge)
*   **Claim Composition Engine (CR-017):** Default `DRAFT_MODE=compose` builds bullets from the `workExperience.md` ACC catalog with VOC replacements and JD bridge prefixes—no per-claim LLM rewrite unless `legacy_llm` is set. `verification_chain` and `recruiter_qa` fail closed before PDFs ship.
*   **Unified Draft Compiler (CR-014):** One code-owned pipeline (`scripts/draft_compiler.py`) for local-first deployments. LLMs optionally power JD profile JSON and claim selection; resume summary, section order, char budget, and PDF assembly are deterministic templates.
*   **Cover Conversion Engine (CR-024):** With `COVER_ENGINE=v1`, cover letters are a **separate pipeline** from resumes: JD-ranked needs, catalog proof selection, micro-narrative bodies, conversion audit — not resume bullet paste.
*   **Per-Claim Tailoring with Fail-Closed Gates:** Compose-mode bullets pass numeric, tool-block, and seniority-inflation checks; failures use sanitized catalog text. `verify_content` errors block the pipeline instead of logging warnings only.
*   **The "Hallucination" Guard:** `verify_content()` runs on resume text with claim IDs before tags are stripped; `validate_hard_facts()` and `style_compliance_guard` enforce ground truth from `data/workExperience.md` and the master resume. Cloud self-audit (`llm_verify_claims`) is retired for compiler output.
*   **JD-Aware Selection:** `JdProfile` (validated JD extract) plus fit-engine `Summary` scores and ranks claims per employer before bullets are generated.
*   **Audit Trail:** Each submission folder receives `draft_manifest.json` listing selected claim IDs, bullet IDs, fallback counts, and `pipeline_version` for reproducibility.
*   **Resilient Batch Drafting:** `batch_pipeline.py` catches per-job drafting failures, marks jobs `Needs Retry` (up to 3 auto-retries), and continues the queue instead of halting the entire sync.
*   **Research vs. Resume Separation:** Company DNA / Perplexity research feeds interview cheat sheets only—it is not injected into resume or cover letter body text.

### 4. Live Visual Document Workspace
*   **Inline Action Triggers:** Consolidates all file-level actions. Standard PDF download and visual editing triggers reside inline as side-by-side controls within each asset row.
*   **Live Side-by-Side Viewport:** Launches a dual-pane overlay when editing:
    *   **Left Pane:** Browser-native PDF preview iframe that reloads dynamically on file compile.
    *   **Right Pane:** A rich-text visual WYSIWYG editor powered by Toast UI.
*   **Background Single-File PDF Compiler:** Initiates sub-second compilation processes to write edited Markdown directly to the file system and instantly regenerate high-quality PDF binaries.
*   **Setting-Gated AI Copywriter:** Displays an LLM instruction input panel in the editor workspace if a Gemini API key is linked in Settings, enabling direct, prompt-based document rewrites.

### 5. Settings & Local-First Credential Management
*   **SQLite as the sole secrets store:** Gemini, Claude, Perplexity, local LLM URL/models, and Adzuna credentials are saved through **Settings → API or Connections** into `jobagent.sqlite` (`profiles.llm_settings` and `profiles.api_connections`). No `.env` file is required or read.
*   **In-process key resolution:** Python scripts call `load_llm_settings()`; the scout reads Adzuna keys directly from SQLite. Child processes are not passed API keys via environment variables.
*   **Job search materialization:** Saving **Job Search** preferences writes to SQLite and projects `data/candidate_preferences.json` for pipeline scripts (gitignored runtime file).
*   **Optional ATS queue file:** Manual outbound-application URLs can be maintained in `data/ats-pipeline.md` and listed via `GET /api/ats-pipeline`.

---

## Part 2: Release Ledger

### 6.2.23

**Fixed**
- **CI `npm ci`:** Added repo `.npmrc` with `legacy-peer-deps=true` so GitHub Actions installs succeed with React 19 while `@toast-ui/react-editor` declares React 17 peers (same as local installs).
- **`.gitignore`:** Scoped pipeline queue to `/jobs/` (root only) so `server/routes/jobs/` is tracked after the CR-ARCH-005 route split.

**Developer**
- README notes `.npmrc` for contributors; `npm test` (Vitest) remains in `smoke.yml`.

### 6.2.22

**Changed**
- **Documentation cleanup (CR-032):** Added `docs/ACTIVE_WORKFLOW.md` as runtime source of truth; archived chat-era `.agent` workflows; aligned README/FEAT-001 with LinkedIn decommission (CR-010) and `min_fit_score` (default 72); `claim_verifier` rule is reference-only; manual draft uses `readMinFitScore()` from prefs.

**Developer**
- CR index: `docs/spec/05-change-requests/README.md` · stubs at `.agent/DEPRECATED.md`

### 6.2.21

**Developer**
- **Architecture refactor (CR-ARCH-004–006):** `server/pipeline/processRunner.ts` centralizes Python spawn (`spawnPython`, `runBuffered`, `runStreamLines`, `runDetached`); evaluate SSE and manual draft use ProcessRunner; jobs API split into `server/routes/jobs/{crud,files,draft}.ts` with `rerank` before `/:id`; frontend `sse.ts` + `apiClient.ts` + Vitest in CI.

### 6.2.20

**Developer**
- **Architecture refactor (CR-ARCH-000–002):** Spawn inventory doc; Phase 0 CI tests (`test_verify_chain.py`, `test_batch_gate.py`, `check_spawn_paths.py`, REG-15); fixed `re_score_jobs.py` `MIN_FIT_SCORE` import; `server/domain/` for `ACTIVE_STATUSES` and `materializeJobSearchPrefs`; explicit `init_pipeline_prefs()` at smoke/batch entrypoints.

### 6.2.19

**Changed**
- **Draft quality gates (CR-031 / FR-174–FR-179):** Added `approved_metrics.py` as the single numeric allowlist; `catalog_validator.py` for catalog checks and anti-claim hint loading; `baseline_quality_gates.py` for pre-flight reports; optional strict flags (`STRICT_COVER_AUDIT`, `STRICT_METRICS`, `STRICT_ANTI_CLAIMS`, `STRICT_CATALOG_DRIFT`); claim-strength metadata in `draft_manifest.json`; fit-summary append gated by `ALLOW_FIT_SUMMARY`; Document Editor saves run light verification before PDF recompile.

**Developer**
- CI smoke copies `workExperience.example.md` and runs `verify_master_claims.py`.
- Strict gates default **off** — run `python scripts/baseline_quality_gates.py` before enabling.

### 6.2.18
Applyr Release
May 30, 2026

Version 6.2.18, deployed on May 30, 2026

Previous
Applyr 6.2.17

**Fixed**
- **Industry blocklist:** Job Search `industryBlocklist` now enforced at scout ingest and batch zero-token evaluation — was saved to prefs but ignored (`FR-170`, CR-027).
- **Keyword gate:** Zero-token filter respects `must_have_keywords` (AND) and `signal_keywords` (OR); removed overly broad default `"product"` match (`FR-171`, CR-028).
- **Levels.fyi scout:** Stops inventing `"Product Manager"` when card text cannot be parsed (`FR-173`).
- **Remote-only geo:** Empty-description stubs from non-remote boards are rejected instead of bypassing geographic gate (`FR-173`).

**Changed**
- **Preferences materialization:** Preserves `signal_keywords`, `must_have_keywords`, and `required_anchors` across UI saves (ADR-005).
- **Optional anchor gate:** Set `ANCHOR_GATE_ENABLED=1` to require two `required_anchors` hits before LLM fit (default off) (`FR-172`).

**Developer**
- New modules: `scripts/industry_gate.py`, `scripts/anchor_gate.py`; regression tests REG-08–REG-14 in `test_smoke_regression.py`.
- SDD: `CR-027`, `CR-028`, `IMP-CR-027-028-collection-quality-gates.md`, collection-quality section in `SDD_PROCESS.md`.

### 6.2.17
Applyr Release
May 28, 2026

Version 6.2.17, deployed on May 28, 2026

Previous
Applyr 6.2.16

**Fixed**
- **Employer job titles:** Canonical headers — Cision/Sterkly use **Product Manager** only; Zero to Sixty uses **Product Owner** only (no slash-combined titles). Shared `EMPLOYER_EXPERIENCE_HEADERS` + `normalize_employer_job_titles()` (extends `FR-075`).

**Changed**
- Batch resume regen applies corrected experience headers across submission folders.

### 6.2.16
Applyr Release
May 28, 2026

Version 6.2.16, deployed on May 28, 2026

Previous
Applyr 6.2.15

**Fixed**
- **Command injection:** Rerank, skill-gap, ai-rewrite, and file compile routes use `spawn` with array args — no shell interpolation (`FR-164`).
- **Evaluate flow:** SSE `done` event now includes score, company, title, url, and summary from pipeline output (`FR-165`).
- **Skill gap:** Single route returns `{ success, output }`; duplicate dead handler removed.
- **PDF export:** `generate_pdf` raises on failure; manifest written only after PDFs exist (`FR-166`).
- **Document editor:** AI rewrite restores content on stream failure.

**Changed**
- **Pipeline mutex:** Concurrent sync/evaluate/draft returns HTTP 409 when pipeline is busy (`FR-167`).
- **FTS search:** Job insert/update syncs `jobs_fts` index (`FR-168`).
- **Company slugs:** Shared sanitization blocks path traversal (`FR-169`, `scripts/company_slug.py`).
- **CORS:** Restricted to localhost origins; optional `APPLYR_API_TOKEN` for mutating routes when set.
- **Scout dismiss:** Self-reject from sync view uses `Closed` + `Self-Rejected` (Tuning Log consistent).
- **CI:** Smoke workflow runs `npm run build`.

**Developer**
- New: `server/middleware.ts`, `CR-025`, `FR-164`–`FR-169`.

### 6.2.15
Applyr Release
May 28, 2026

Version 6.2.15, deployed on May 28, 2026

Previous
Applyr 6.2.14

**Fixed**
- **CI smoke workflow:** GitHub Actions now installs Python deps, bootstraps `master_claims.example.json` and `candidate_preferences.example.json` before running pipeline smoke tests (`FR-148`, `AC-156`).

**Developer**
- Added `data/master_claims.example.json` — generic claim catalog template for CI and local scaffolding.

### 6.2.14
Applyr Release
May 28, 2026

Version 6.2.14, deployed on May 28, 2026

Previous
Applyr 6.2.13

**New**
- **CR-024 Cover conversion engine:** `COVER_ENGINE=v1` builds Match Brief cover letters from **JD + master claims only** — does not read `Resume.md` for proof selection (`FR-158`).
- **Application-first openers:** Letters lead with “I am applying for the {role} at {company}…” plus posting-alignment line; audit bans “{Company} is hiring…” (`FR-160`).
- **`cover_letter_plan.json`:** Per-submission plan records claim IDs, ranked JD needs, and themes for traceability (`FR-159`).
- **Theme prose helper:** `format_themes_for_prose()` fixes chained “and” in resume summaries (e.g. “platform reliability and data integrity” vs triple-and chains) (`FR-161`).

**Changed**
- **`draft_compiler.py`:** `PIPELINE_VERSION=CR-024-cover-engine`; cover numeric verification uses full claim catalog when `COVER_ENGINE=v1` (`AC-168`).
- **Cover letter length QA:** Single-page char limit raised to 2400 for Match Brief format (salutation + bridge paragraph).
- **Batch scripts:** `regenerate_all_cover_letters.py` sets `COVER_ENGINE=v1` by default.

**Fixed**
- Cover letters no longer paste resume bullets with a generic hook (`FR-088` cover path superseded).
- Jobgether-style salary figures excluded from `ranked_needs` JD extraction.

**Developer**
- New modules: `scripts/cover_letter_compiler.py`, `cover_jd_needs.py`, `cover_claim_picker.py`, `cover_plan_builder.py`, `cover_narrative_templates.py`, `cover_letter_renderer.py`, `cover_letter_audit.py`, `cover_prose.py`, `match_thesis_builder.py`.
- Specs: `CR-024`, `FEAT-013`, `FR-157`–`FR-163`, `IMP-CR-024`, traceability rows `AC-164`–`AC-169`.
- Pilot: `python scripts/pilot_cover_forbes.py`.

### 6.2.13
Applyr Release
May 28, 2026

Version 6.2.13, deployed on May 28, 2026

Previous
Applyr 6.2.12

**New**
- **CR-021 compose hardening:** Default `JD_PROFILE_MODE=deterministic` and `COVER_HOOK_MODE=template` so resume/cover prose stays catalog-grounded; cover body remains proof bullets only.
- **Pre-score queue:** BM25 + embedding pre-score sorts batch jobs before fit LLM; optional `FIT_EVAL_TOP_N` cap.
- **Scout seniority gate:** Title blocklist and max-years check at ingest when description is available.
- **Draft manifest sources:** `claim_sources` and `jd_hash` in `draft_manifest.json`; editor facts panel in Document Editor.
- **ATS watchlist channel:** Optional `config/ats_watchlist.json` / `data/ats_watchlist.json` careers scrape.
- **CI smoke workflow:** GitHub Actions runs `smoke_draft_compiler.py` without LLM.

**Changed**
- **Strict local-only:** `LOCAL_ONLY_MODE=1` no longer falls through to Gemini on fit/draft paths.
- **Fit eval:** BM25-pruned work experience context + JSON schema via `call_llm_stage('fit')` with `qwen2.5:7b-instruct-q4_K_M` default.
- **Grammar lint:** WebGPU reports issues only; does not rewrite resume/cover text.
- **PDF export gate:** Manual compile blocked if `draft_manifest.verification_passed` is not true.

**Developer**
- `scripts/pipeline_env.py`, `scripts/pre_score_jobs.py`, `scripts/build_claim_embeddings.py`, `scripts/draft_linter.py`.
- **SDD completion:** Full CR-021 spec chain (`FR-131`–`FR-150`, `AC-139`–`AC-158`), `IMP-CR-021`, FEAT-001/004/012 updates, per-requirement traceability rows.
- **Agent rule:** `.agent/rules/pipeline_env.md` — always-on defaults for compose, local-only, and forbidden env combinations.
- **Code traceability:** `# Implements FR-*` headers on `pipeline_env.py`, `batch_pipeline.py`, `draft_compiler.py`, `pre_score_jobs.py`, `claim_composer.py`, `llm_stages.py`.

### 6.2.12
Applyr Release
May 28, 2026

Version 6.2.12, deployed on May 28, 2026

Previous
Applyr 6.2.11

**New**
- **Offline Intelligence Pipeline:** Replaced external Perplexity and LinkedIn dependencies with a robust local execution chain. Orchestrated SearXNG local web searching and Playwright-based headless scraping to capture up-to-date company data and job descriptions directly, enabling full disconnected operation.
- **Vector-Based Backlog Reranking:** Upgraded ATS queue management with a fully local vector database. Re-evaluates stale listings by projecting semantic similarity between JD embeddings and candidate preferences to resurface hidden gem roles previously buried in the backlog.
- **Edge-Computed Grammar Inference:** Transferred final stage stylistic and grammatical validation from Python server layers to the client browser using WebGPU. Eliminates server VRAM contention while providing real-time local linting.
- **Responsive Push Notifications:** Plumbed NTFY push-notification webhooks natively into the background batch pipeline, enabling zero-latency cross-device alerts for system failures, completed assets, and rate-limit triggers.
- **On-Device PII Masking Guard:** Implemented a robust SpaCy/Regex PII redaction layer prior to LLM submission, neutralizing the risk of data leakage when connecting to semi-trusted cloud API endpoints.

**Changed**
- **Adaptive PDF Pagination & Layout:** Reworked `compile_single.py` to dynamically measure Markdown token weights and iteratively reflow the single-page layout buffer, virtually guaranteeing zero multi-page spillages regardless of generated text length.
- **Real-Time Streaming Generation Output:** Augmented the server `system.ts` route with Server-Sent Events (SSE), streaming partial draft completions instantly to the React frontend UI to drastically improve perceived performance and keep the user engaged.
- **SQLite FTS5 Rapid Metadata Search:** Re-indexed core SQLite databases with FTS5 tokenizers to dramatically accelerate semantic candidate preference lookups, bypassing slower legacy SQL LIKE wildcard queries.
- **Intelligent Asset Pruning Engine:** Deployed an automated DB grooming script that sweeps stale vector blob embeddings and trims long-abandoned ATS data arrays, enforcing strict data lifecycle policies to ensure maximum runtime speed and minimal storage overhead.

**Developer**
- Hardened multi-process data access to prevent locking across concurrent threading operations, isolating CPU-bound I/O vectors away from constrained GPU compute resources.

### 6.2.11
Applyr Release
May 27, 2026

Version 6.2.11, deployed on May 27, 2026

Previous
Applyr 6.2.10

**New**
- **Local Embedding Vector Selection:** Implemented `local_embeddings.py` to wrap Ollama's `nomic-embed-text` endpoint. Replaced error-prone LLM claim selection in `local_draft_stages.py` with lightning-fast deterministic Cosine Similarity vector matching.
- **BM25 Summary Pruning:** Added a sparse BM25 index to intelligently prune Job Descriptions before feeding them to the LLM, reducing context length and preventing summary hallucinations.
- **Syntactic Skeleton "Mad Libs" Bullets:** Upgraded `bullet_generation.py` to force the LLM to output only an Action Verb and an Objective in strict JSON, appending verified quantitative metrics deterministically via Python code to absolutely prevent number inflation.
- **Automated Self-Correction Loop:** Introduced `SelfCorrectionError` in `drafting_errors.py` and `quality_checker.py`. Modified `batch_pipeline.py` to natively catch QA violations (like Cover Letters exceeding character limits or missing headers) and execute an automated retry loop with injected LLM feedback.

**Changed**
- **Decomposed One-by-One Rewriting:** Re-architected bullet generation to prompt the LLM to rewrite exactly one bullet at a time instead of all at once, maximizing small-model accuracy.
- **Dynamic AST Pruning for PDF Layout:** Modified `draft_compiler.py` to assemble the resume as an AST and dynamically pop off the oldest bullets if the content exceeds a strict 3,200 character budget, guaranteeing a pristine 1-page PDF layout without LLM guessing.
- **Ollama Options Integration:** Extended `utils.py` `call_llm` to natively support native JSON Schema outputs and `logit_bias` parameter overrides for enforcing specific structural formats on local models.
- **Claim Catalog Caching:** Updated `claim_catalog.py` to pre-compute and cache vector embeddings on startup.

**Developer**
- Ensured strict compliance with the local 8GB fallback constraints by shifting text analysis to traditional algorithm libraries.

### 6.2.10

**Changed**
- **Seniority filter refinement (CR-019 / FR-109–110):** Removed blanket "Senior" title block. Years-first gate (`seniority_gate.py`) rejects JDs requiring more than max years (default 7). Title blocklist uses whole-word match on title line only. Rubric distinguishes AI PM roles from AI-tools mentions.
- **Job Search UI:** Max years required field maps to `experience_range.max` in candidate preferences.

**Developer**
- `scripts/re_score_jobs.py` — re-run fit on Rejected jobs after preference changes.
- CSV import writes `Title:` / `URL:` headers into staging JD files.

### 6.2.9

**New**
- **Doppler Secret Injection (SEC-005):** Integrated the Doppler CLI to securely inject secrets (`GEMINI_API_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `OLLAMA_HOST`) via environment variables at runtime (`npm run dev:doppler`), entirely decoupling sensitive strings from the local SQLite database.
- **Tailscale Overlay Support (NFR-006):** Exposed the Vite client and Express server to bind to `0.0.0.0` rather than `localhost`, enabling secure overlay network access (e.g. Tailscale or Cloudflare Tunnels) for "Thin Client" laptop usage while desktop hardware runs workloads.
- **Smart Setting Redaction:** Designed a dynamic UI mechanism (`/api/env_status`) to automatically detect when environment variables are actively injected by Doppler. Passwords inputs are conditionally replaced by secure "Managed via Doppler" lock badges.

**Changed**
- Fallback logic safely permits usage of the local `jobagent.sqlite` identity store when Doppler is not active, seamlessly bridging owner and non-owner workflows without application disruption.

### 6.2.8

**Changed**
- **Zero-touch draft polish (CR-018 / FR-105–108):** Sentence-aware bullet fitting (`bullet_fit.py`, 28-word cap), at most one JD bridge per resume, bridge stripping on cover proof lines, fresh Backlog summaries on successful draft, and template-first interview cheat sheets (`CHEAT_SHEET_MODE=template` default).

**Developer**
- `scripts/refresh_backlog_summaries.py` one-time DB summary refresh for existing Backlog rows.
- Extended `recruiter_qa`, `audit_opportunities`, and `smoke_draft_compiler` for AC-106–110 checks.

### 6.2.7

**Changed**
- **Local claim composition (CR-017 / FR-100–104):** New `claim_catalog`, `claim_composer`, `verification_chain`, and `recruiter_qa` modules. Draft compiler v `CR-017-1` defaults to compose mode, strips all fact ID token formats, fixes resume `## EDUCATION` header (no `& CERTIFICATIONS`), and uses DB company names on cover letters.
- **Local-first LLM routing:** `llm_stages` prefers local providers; fit evaluation in `batch_pipeline` respects `LOCAL_ONLY_MODE` and `primaryProvider: local`.

**Developer**
- Set `DRAFT_MODE=legacy_llm` to restore per-claim LLM bullet rewrites. Smoke tests extended in `scripts/smoke_draft_compiler.py`.
- SDD: `IMP-CR-017`, `FEAT-012`/`FEAT-004`/`DESIGN-002` updated; AC-100–105 in requirements registry.

### 6.2.6
Applyr Release
May 21, 2026

Version 6.2.6, deployed on May 21, 2026

Previous
Applyr 6.2.5

**Fixed**
- **Submissions folder hygiene (BUG-014, FR-030):** Applied and Closed roles no longer leave duplicate or stub folders in `submissions/`. Archiving merges into existing `archive/submissions/` copies instead of failing when the destination already exists. Server startup and `POST /api/jobs/reconcile-submissions` sweep stale folders; `has_assets` now checks archive paths for submitted jobs.

**Developer**
- Added `server/submissionFolders.ts` and `scripts/reconcile_submissions.py` for manual reconciliation.

### 6.2.5
Applyr Release
May 19, 2026

Version 6.2.5, deployed on May 19, 2026

Previous
Applyr 6.2.4

Next
Applyr 6.3 (Planned)

**Changed**
- **SQLite-only secrets (CR-015, FR-095):** All API and data-source keys are read from `jobagent.sqlite` at runtime. Removed `.env`, `dotenv`, `python-dotenv`, and env-var key injection into child processes. Configure everything in **Settings → API or Connections** — no manual env files.

**Fixed**
- **Stale `.env` confusion:** Keys in a local `.env` are no longer consulted; Settings UI is the only supported configuration path, matching the product’s local-first security model.

**Developer**
- `buildPythonEnv()` now sets only `PYTHONUNBUFFERED` (no `GEMINI_API_KEY` / `ADZUNA_*` shuttle).
- `scripts/scout_local.ts` loads `api_connections` from SQLite; `scripts/utils.py` adds `load_api_connections()`.
- Deleted `.env.example`; `scripts/test_llm.py` reads Gemini from SQLite.

### 6.2.4
Applyr Release
May 19, 2026

Version 6.2.4, deployed on May 19, 2026

Previous
Applyr 6.2.3

Next
Applyr 6.2.5

**Changed**
- **Root folder cleanup:** Removed vendored `career-ops-main/` tree; ATS manual queue lives at `data/ats-pipeline.md`. Legacy docs moved to `docs/legacy/`. OpenPostings zip extracted to `OpenPostings-extracted/` (zip removed locally).

**Developer**
- `.gitignore`: `/archive/` only at repo root (fixes `docs/legacy/` being ignored); added `job_hunter.db`, `jobagent_temp.sqlite`, WAL files, `OpenPostings-main.zip`, `career-ops-main/`.
- Deleted orphan DBs and temp audit files; `GET /api/ats-pipeline` now reads `data/ats-pipeline.md`.

### 6.2.3
Applyr Release
May 19, 2026

Version 6.2.3, deployed on May 19, 2026

Previous
Applyr 6.2.2

Next
Applyr 6.2.4

**Changed**
- **Drafting codebase consolidation:** Removed superseded dual-path modules (`local_draft_pipeline.py`, `batch_pipeline_new_only.py`, `repair_resume_content.py`) and dead helpers (`is_local_primary`, `build_draft_manifest`, `group_bullets_by_employer`). Bullet generation now lives in `scripts/bullet_generation.py`.

**Developer**
- Traceability matrix and requirements registry updated: `FR-082` / `083` / `086` / `088` / `093` now point at `draft_compiler.py` and `bullet_generation.py`.
- `scripts/smoke_draft_compiler.py` passes after cleanup; README script index lists the unified compiler modules.

### 6.2.2
Applyr Release
May 19, 2026

Version 6.2.2, deployed on May 19, 2026

Previous
Applyr 6.2.1

Next
Applyr 6.2.3

**Changed**
- **Unified Draft Compiler (CR-014, FR-089–094):** Gemini and local LLMs now run the same `draft_compiler` stage graph—`JdProfile` → claim selection → per-claim bullets (bridge phrases + gates) → deterministic summary/cover templates → `verify_content` → QA/PDF → `draft_manifest.json`. Removed monolithic `_run_gemini_monolithic_draft` and separate cloud vs local routing in `run_drafting_engine`.
- **Per-stage LLM routing:** `call_llm_stage(stage_id)` tries providers in stage-specific order (typically `['gemini','local']`) so quota or timeout on one model does not require a different pipeline shape.
- **Research boundary:** Cheat-sheet / company research runs after the resume pack and is excluded from resume and cover body text.

**Fixed**
- **Batch no longer dies on one bad draft:** Per-job `DraftingPipelineError` handling in `batch_pipeline.py` marks failures as `Needs Retry` (with retry cap) instead of stopping the full sync with `Sync stopped due to stage error`.
- **Local bullet QA failures:** Missing `PROFESSIONAL SUMMARY` and similar structural gaps are repaired via `repair_resume_markdown()` inside the compiler before hard QA, with deterministic fallbacks when LLM bullets fail gates.

**Developer**
- New: `scripts/draft_compiler.py`, `scripts/jd_tailoring.py`, `scripts/llm_stages.py`, `scripts/bullet_generation.py`, `data/bridge_phrases.json`, `scripts/smoke_draft_compiler.py`, `scripts/drafting_errors.py`.
- Retired for compiler output: `llm_verify_claims`, monolithic full-resume cloud generation.
- Specs: `CR-014-unified-draft-compiler.md`, `FEAT-012` updated, `FR-089`–`FR-094` in requirements registry.

### 6.2.1
Applyr Release
May 18, 2026

Version 6.2.1, hotfix deployed on May 18, 2026

Previous
Applyr 6.1.1

Next
Applyr 6.2.2

**Fixed**
- **False-Alarm Stderr Logging Errors (BUG-010):** Addressed Express orchestrator intercepting all stderr buffers from subprocess runs and unconditionally tagging them as critical pipeline `ERROR` entries. Introduced a robust `handleStderr` log routing helper in `server/scout.ts` that filters out safe deprecation warnings, cleanly parses informational debug logs (`[Model Manager]`, `[LLM]`, `[Research]`, etc.) to register under `INFO`, routes warnings to `WARN`, and isolates only legitimate traceback errors under `ERROR`.
- **Local Self-Audit Resume Corruption (BUG-010):** Resolved a failure where the drafting engine called the primary local model (`ministral-3-14b`) to audit its own resume output. Because local models lack the reasoning capacity to audit large files under strict constraints, it returned unstructured text, failing zero-tolerance structural QA checks and causing a `Sync stopped due to stage error` crash. Locked `llm_verify_claims` to cloud providers (`provider_override=['gemini']`) to ensure high-fidelity audits always utilize cloud models when configured, bypassing unreliable local self-auditing.

Developer
- **SDD Integrity:** Codified bug specification `BUG-010-false-alarm-stderr-errors.md`, added tracing rows to `traceability-matrix.md`, and marked tasks complete in `task.md` with explicit `# Implements BUG-010` comments in code.

---

### 6.1.1
Applyr Release
May 14, 2026

Version 6.1.1, hotfix deployed on May 14, 2026

Previous
Applyr 6.1

Next
Applyr 6.2 (Planned)

Fixed
- **Gemini 2.5 Experimental 429 Rate Limit Guard (BUG-009):** Mitigated recurring `429 Resource Exhausted` cascades triggered by Google's restrictive daily quota on the Gemini 2.5 experimental family. Downgraded default cloud model synthesis routing from `gemini-2.5-flash-lite` to stable `gemini-2.0-flash` (Public Preview). This expands Jason's daily free-tier processing ceiling from **20 requests per day** back to the massive **1,500 requests per day** limit (a 75x headroom boost) and restores multi-threaded background batch crawlers without operational lockout.

Developer
- **SDD Compliance Updates:** Formally logged bug specification `BUG-009-gemini-experimental-rate-limits.md` and registered updated integration bindings inside `traceability-matrix.md`.

---

### 6.1
Applyr Release
May 14, 2026

Version 6.1, deployed on May 14, 2026

Previous
Applyr 6.0

Next
Applyr 6.2 (Planned)

New
- **Built In Multi-Term Search Integration (FR-079, CR-009):** Integrated native support for full text search iteration against configured candidate `SEARCH_TERMS`. Replaced single static taxonomy path targeting with dynamic `/jobs?search={term}` navigations, expanding top-of-funnel Built In discovery by 21+ new eligible jobs in local testing.
- **Dual-Archetype Resilient Selector Layouts (FR-078):** Formulated layout-agnostic CSS collection utilizing unified selectors representing both traditional `.job-item` layouts and newer React-based search engine `div[data-id="job-card"]` components, fully resolving DOM architecture scouting gaps.

Fixed
- **High-Risk LinkedIn Scraper Decommission (FR-080, CR-010):** Permanently excised the high-risk automated LinkedIn browser scouter module to safeguard system integrity and comply with session-risk directives. Bypassed parallel browser dispatches targeting `linkedin.com`, deleted the redundant manual authentication asset `login_linkedin.ts`, and rerouted the orchestration sequence exclusively through verified compliant channels.

Developer
- **SDD Registry Hardening:** Added structural mappings for CR-009 and CR-010 requirements inside registry matrices and confirmed TypeScript syntactic stability passing `tsc --noEmit` clean compilations.

---

### 6.0
Applyr Release
May 13, 2026

Version 6.0, deployed on May 13, 2026

Previous
Applyr 5.21

Next
Applyr 6.1

New
- **Fact-Bound Semantic Anti-Hallucination (FR-069):** Replaced literal ID scanning with dynamic numerical containment checking. The audit engine aggregates ground truth sentences for all citations within a generated sentence and mathematically verifies that all generated percentages, dollar values, and user scales represent valid subsets of the ground truth, actively blocking numeric fabrication or inflation.
- **Early Ingestion Location Gate (FR-070):** Embedded geographical boundary validations directly inside the multi-source scouting aggregator. Automatically filters and drops out-of-bounds on-site listings before database storage, enforcing strict compliance with Remote US or San Diego / Carlsbad local requirements.
- **Stateful Orchestration & Stage Recovery (FR-068):** Introduced a persistent `pipeline_runs` schema coupled to a flattened, modular child-process async handler. Sync crashes no longer recycle the full batch queue; re-triggering sync dynamically restores the precise failed sub-stage (`SCOUT` -> `BACKFILL` -> `SCRAPE` -> `EVALUATE`).
- **SQLite Write-Ahead Logging Concurrency:** Configured `PRAGMA journal_mode = WAL` and set a 30,000ms busy timeout globally in Node, and hardened all concurrent Python connections with mandatory `timeout=30.0` parameters. These mitigations completely eliminate single-point-of-failure database locking deadlocks during high-concurrency execution cycles.

Fixed
- **Resilient LinkedIn DOM Obfuscation Workaround:** Replaced brittle, obfuscated CSS selectors with sequential `innerText` text buffer scanning and async locator auto-waiting. This decouples harvester routines from unstable CSS tokens, fully preventing card timeout hangs.
- **Mock Scheme Page Load Bypassing:** Patched the description scraper to automatically intercept and skip `local://` URI schemes, preventing Chromium driver exceptions and system resource waste during manual mock evaluations.

Developer
- **SDD Compliance:** Registered structural mappings for functional requirements `FR-068`, `FR-069`, and `FR-070` inside the Traceability Matrix.
- **Static Integrity Validation:** Fully verified system static typing, passing complete TypeScript `tsc --noEmit` checks with zero compilation errors.

---

### 5.21
Applyr Release
May 12, 2026

Version 5.21, deployed on May 12, 2026

Previous
Applyr 5.20

Next
Applyr 6.0

New
- **Deterministic Claim‑to‑ID Verification (FR-014):** Added code-level validation requiring the LLM to anchor all resume and cover letter factual claims using bracketed Fact IDs (`[ACC-###]`, `[MET-###]`, `[VOC-###]`) directly from the ground truth. Programmatically strips IDs before final document compilation to conform to style rules.
- **Automated Verification Retry Loop:** Configured a 3-attempt generator loop inside the drafting engine. If validation catches a hallucinated or invented Fact ID, the system appends the error details to the prompt, forces a localized rewrite, and retries.
- **Dynamic GPU Model Tiering (FR-015):** Created `scripts/model_manager.py` to parse `nvidia-smi` output at runtime. Dynamically selects high-resource `ministral-3-14b:latest` if free VRAM is ≥ 10 GB, else safely executes `gemma4-e4b:latest` fallback.
- **Intra-Loop Memory Cleanup:** Integrated aggressive `unload_all_models()` execution inside the active `batch_pipeline.py` loop. Every sequential job processing run now finishes with a full VRAM reclamation call to prevent active weight stacking in Ollama.
- **Instant Congestion Failover:** Removed wait-and-polling cycles on Cloud API rate limits. Upon receiving a 429 resource exhausted code, the calling wrapper instantly propagates failure, routing evaluation and drafting operations dynamically to local LLM resources to preserve execution velocity.

Developer
- **SDD compliance:** Updated traceability matrix for FR-014 and FR-015 to map new modules `verify_claims.py` and `model_manager.py`.

---

### 5.20
Applyr Release
May 11, 2026

Version 5.20, deployed on May 11, 2026

Previous
Applyr 5.19

Next
Applyr 6.0 (Planned)

New
- **Dual-Tier Local Intelligence Failover:** Redesigned `utils.py` to dynamically monitor local inference health. If the large primary model throws an Out-Of-Memory (500) exception, the engine automatically locks onto a user-defined lightweight fallback model (`gemma2:9b`) and resumes with zero pipeline lag.
- **Automatic VRAM Reclamation (Eco-Hook):** Authored `unload_local_models()` protocol and hooked it to the `finally` block of `batch_pipeline.py`. As soon as processing finishes, Python sends explicit `keep_alive: 0` signals to Ollama, immediately cleaning local GPU memory for system/gaming performance.
- **Hybrid Local-Cloud Switching:** Introduced explicit `provider_override` logic enabling tiered operations. Rejection triage runs instantly locally while delicate Drafting and Auditing functions dynamically lock to Gemini Pro, eliminating local model hallucinations.

---

### 5.19
Applyr Release
May 11, 2026

Version 5.19, hotfix deployed to local users on May 11, 2026

Previous
Applyr 5.18

Next
Applyr 6.0 (Planned)

Fixed
- **Critical Scraper Context Leak (BUG-008):** Resolved a core execution defect where sequential loops shared a single Playwright `Page` instance. Pending redirects from previous hops would asynchronously interrupt subsequent job loadings, which the system misclassified as "dead links." 
- **Redirection Chain Isolation:** The engine now allocates a fresh, isolated browser context per URL load and enforces strict destruction (`page.close()`) to end lingering network threads, ensuring high-fidelity navigation capture for multi-hop aggregators like Adzuna.

Developer
- **Data Recovery Protocol:** Authored `restore_stale_jobs.ts` to successfully pull 93 false-positively archived records from `stale_jobs` back into `jobs` table.
- **SDD compliance:** Logged `BUG-008` in known-issues registry.

---

### 5.18
Applyr Release
May 11, 2026

Version 5.18, first offered to local users on May 11, 2026

Previous
Applyr 5.17

Next
Applyr 6.0 (Planned)

Fixed
- **Scraper Navigation Interruption Loop (BUG-007):** Resolved an issue where automated client/server redirects (common with expired Adzuna links) interrupted the Playwright navigation cycle, trapping jobs in an infinite `New` processing loop. Dead links are now caught, automatically archived in `stale_jobs`, and removed from the primary queue.

Developer
- **SDD compliance:** Registered `BUG-007` in `traceability-matrix.md` and finalized resolution state in known-issues log.

---

### 5.17
Applyr Release
May 9, 2026

Version 5.17, first offered to local users on May 9, 2026

Previous
Applyr 5.16

Next
Applyr 6.0 (Planned)

New
- **Job Funnel Expansion — 7 Active Sources (CR-004, FR-052):** Added three new job sources to the scout pipeline: Himalayas (remote-focused), The Muse (culture-forward listings), and Adzuna (aggregates thousands of boards). Phase 1 now runs 7 parallel API sources simultaneously, significantly expanding the top of the funnel without additional token spend.
- **Adzuna Optional Connection (FR-054, FR-055, NFR-004):** Adzuna is configured entirely from the UI. If no key is provided the source is silently skipped. A built-in rate guard caps usage at 10 calls per scout run with a 3-second inter-call delay, keeping usage comfortably inside the free tier (25 req/min, 250 req/day).
- **LLM Provider Fallback Chain (CR-006, FR-059, FR-060):** The pipeline now supports automatic multi-provider fallback. The primary provider is tried first; on a non-rate-limit error it falls through to the next configured provider in order (Gemini → Claude → Local → Perplexity). Rate limit errors retry within the same provider. If no providers are configured, an actionable warning is logged and no API call is attempted.
- **Perplexity as Full LLM Provider (FR-061):** Perplexity `sonar-pro` is now a first-class pipeline provider alongside Gemini, Claude, and Local. When a Perplexity key is configured, the research engine uses it first for company intelligence (native web retrieval), then falls back to the primary LLM on failure. No Perplexity key = no Perplexity calls, ever.
- **Four-Card LLM Provider UI (FR-062):** The "API or Connections" settings tab is redesigned into four independent provider cards — Gemini, Claude, Local LLM, and Perplexity. Each card has an always-visible key/URL field, a Connected badge when credentials are present, and a "Set Primary / Primary ✓" toggle. Configure any combination; the pipeline uses whatever is connected.

Fixed
- **RemoteOK Tag Format Bug:** RemoteOK slugs require hyphens (`product-manager`), not URL-encoded spaces (`product+manager`). Fixed tag generation to use the correct format.
- **Remotive Category Lock:** Remotive was locked to a single category search. Fixed to iterate all `SEARCH_TERMS` with per-term dedup via a shared `seenUrls` Set.
- **WWR Single Feed:** We Work Remotely was fetching only one RSS feed. Fixed to pull both the product and management/finance feeds with shared extraction logic.
- **Import-Time Gemini Crash:** `utils.py` instantiated a global `genai.Client` at module import time, causing an immediate crash if `GEMINI_API_KEY` was unset. Removed — clients are now created lazily inside `_call_gemini()` only when that provider is actually invoked.

Changed
- **Role-Aware Muse Routing (FR-056):** The Muse source now derives its category from `TARGET_ROLE` via `getTheMuseCategory()` rather than a hardcoded `"Product"` category. Users targeting Engineering, Design, or Data roles get correct category routing automatically.
- **PM Search Term Expansion (FR-053):** `materializeJobSearchPrefs()` now automatically appends Product Owner, Technical Product Manager, Platform Product Manager, and Digital Product Manager to the search terms when the target role includes "Product Manager" — without hardcoding these anywhere in scout scripts.
- **Perplexity Moved from Data Sources to LLM Providers (SEC-004):** The Perplexity API key is now stored in `llm_settings` alongside Gemini and Claude, not in `api_connections`. Existing keys are transparently migrated on first Settings load.
- **`provider` → `primaryProvider` (FR-063):** The LLM settings field renamed from `provider` to `primaryProvider` in both the frontend and Python. Backward compatibility is maintained — old DB records with `"provider"` continue to work automatically.

Developer
- **`_is_configured()` + `_get_configured_providers()` in `utils.py` (FR-059):** Provider guard functions ensure no LLM API is ever called without a valid key. Configured providers are returned in call order: primary first, then the fixed fallback sequence.
- **`buildPythonEnv()` updated (FR-058, SEC-004):** Reads `perplexityApiKey` from `llm_settings`; reads Adzuna keys from `api_connections`. All LLM keys injected at Python spawn time via environment variables — never written to disk.
- **SDD compliance:** CR-004, CR-005, and CR-006 documents created. Requirements registry updated with FR-052 through FR-063, NFR-005, and SEC-004.

---

### 5.16
Applyr Release
May 8, 2026

Version 5.16, first offered to local users on May 8, 2026

Previous
Applyr 5.15

Next
Applyr 6.0 (Planned)

New
- **Unified Job Search Settings Panel (CR-003, FR-046, FR-047):** Collapsed four disconnected preference islands into a single canonical control surface under a renamed "Job Search" sidebar tab. A primary card covers Target Role, Work Setting, Location, Date Posted, and Experience Level. A secondary card covers Title Blocklist, Industry Blocklist, and Minimum Salary. Every field saved here now actually governs every scout run.
- **Live Settings Materialization Pipeline (FR-048, ADR-005):** Saving Job Search settings writes to `profiles/job_search` in SQLite and immediately materializes `data/candidate_preferences.json` server-side. Python pipeline scripts read only the JSON file — the entire preference chain is now end-to-end live with zero manual file editing required.
- **Dynamic Scout URL Generation (FR-049):** `scout_local.ts` now builds all search URLs at runtime from `candidate_preferences.json` — LinkedIn geo IDs, BuiltIn city/state slugs, RemoteOK tag arrays, search terms, and the freshness window are all derived from user settings. No hardcoded URLs remain.
- **Generic ACC-ID Codification Engine:** Rewrote `codifyExperienceAndAssignIDs()` to use a dynamic employer Map rather than hardcoded per-company seed values. Any number of `### 5.N` experience sections are supported; each section gets IDs in the range `N×100+1` to `(N+1)×100` automatically.
- **Experience Tab Onboarding Flow (FR-050, FR-051):** The Experience tab now branches on file state. An empty or uninitialized file shows a structured onboarding card explaining the VOC/MET/ACC proof-code system before the user pastes anything. A populated file shows a live codification status bar with real-time ACC/VOC/MET count pills and a collapsible edit guide covering the three safe edit patterns: Minor Edit, New Claim, and Retire.
- **Premium Settings Modal (FR-041):** Migrated all app configuration from a static Profile sub-tab into a full-screen backdrop-blur overlay with Claude-style dual-pane navigation. Left pane: vertically stacked tabs (General, Account, Privacy, Billing, Usage, Capabilities, Connectors, LLM Engine). Right pane: dynamic scrolling workspace. LLM provider selection and API key management now live here.

Changed
- **Sidebar Label:** "Scout" renamed to "Job Search" to reflect that the tab now controls all search criteria, not just crawl scheduling.
- **Profile Tab Cleanup:** Removed the "Preferences" sub-tab from the Profile page entirely; those settings now live in the unified Job Search panel.
- **Pipeline Score Threshold:** Hardcoded `score < 72` filter in `batch_pipeline.py` replaced with `MIN_FIT_SCORE` read from `candidate_preferences.json`, making the pass threshold user-configurable.

---

### 5.15
Applyr Release
May 8, 2026

Version 5.15, first offered to local users on May 8, 2026

Previous
Applyr 5.14

Next
Applyr 6.0 (Planned)

New
- **Direct Manual Asset Drafting Triggers (FR-045, AC-046):** Integrated an inline, premium "Draft Assets" manual trigger button directly onto matched role cards that are in "Pending Assets" state. This gives users absolute, granular control to initiate localized single-role background evaluations and resume/cover letter compilations instantly on demand.
- **Background Single-Job Drafting Pipeline (FR-045, AC-046):** Built a dedicated POST `/api/jobs/:id/draft` server endpoint that triggers single-mode batch execution, feeds real-time stdout and stderr logs straight to the Scout page terminal, and dynamically updates system status.

---

### 5.14
Applyr Release
May 8, 2026

Version 5.14, first offered to local users on May 8, 2026

Previous
Applyr 5.13

Next
Applyr 6.0 (Planned)

New
- **Pulsing Active Process Log Console:** Appended a real-time pulsing `ACTIVE` terminal line to the bottom of the Scout page's Log Console. When the background system is crawling feeds or synthesizing assets, the active item is shown natively at the bottom of the log stream, providing continuous visibility.
- **Drawer Active Task Indicators:** Embedded a glowing active indicator at the top of the details panel's log drawer. If the background scouter is actively processing assets for the selected company, a glowing green `ACTIVE` log line is shown to make current pipeline executions instantly transparent.

---

### 5.13
Applyr Release
May 8, 2026

Version 5.13, first offered to local users on May 8, 2026

Previous
Applyr 5.12

Next
Applyr 6.0 (Planned)

New
- **Interactive Pipeline Process Logs (FR-045, AC-046):** Built an inline, monospace background log console inside the `JobDetailPanel` drawer. It dynamically queries the database for any crawling, gate evaluation, and asset synthesis logs matching the selected opportunity's company name. This provides complete visibility and background transparency for roles currently in the "Pending Assets" queue (such as *Vitestro*).

Changed
- **Standardized Pipeline Labels & Badges:** Extended the dynamic *"Pending Assets"* fallback to the Scout page (`SyncActivityView.tsx`) to guarantee label consistency across the app. Jobs in backlog missing assets are now cleanly labeled as *"Pending Assets"* with a neutral amber look instead of being labeled as *"Ready to Apply"*.

---

### 5.12
Applyr Release
May 8, 2026

Version 5.12, first offered to local users on May 8, 2026

Previous
Applyr 5.11

Next
Applyr 6.0 (Planned)

Fixed
- **Strict Backlog Asset Readiness Verification (FR-045, AC-046):** Fixed a logical bug where backlog jobs with missing PDF assets were incorrectly marked as *"Ready to Apply"* with green buttons on the Opportunities board. Now, they dynamically render with a neutral grey **"Pending Assets"** status badge and a standard **"Details"** button, switching to the green **"Apply Now"** button only after their compiled assets become available.
- **Accurate Dashboard & Sidebar Pipeline Metrics:** Hardened Sidebar badge counts and Dashboard progress charts to only include backlog opportunities that have completed asset generation, keeping pending-asset roles cleanly segregated in the background.

---

### 5.11
Applyr Release
May 8, 2026

Version 5.11, first offered to local users on May 8, 2026

Previous
Applyr 5.10

Next
Applyr 6.0 (Planned)

Changed
- **Unified "Opportunities" Branding Refactor (FR-045, AC-046):** Fully re-labeled the central application-tracking vertical to "Opportunities" across the entire user experience. This includes renaming sidebar navigation tags, main page headings, notifications routing callbacks, and active lists inside `TodayView.tsx`, establishing a far more professional, premium, and lifelike terminology.

---

### 5.10
Applyr Release
May 8, 2026

Version 5.10, first offered to local users on May 8, 2026

Previous
Applyr 5.9

Next
Applyr 6.0 (Planned)

New
- **First-Class Settings Panel Tab (FR-041, AC-042):** Transformed Settings from a pop-up modal to a first-class page/tab rendered directly inside the main workspace's right panel. It features a full-panel 2-column layout with vertical tab navigation, fully integrating all 5 subsections (Profile, Job Preferences, Experience, API or Connections, Analytics).
- **Sage-and-Cream Premium Light Styling:** Completely replaced legacy dark mode grays and blacks (`#121212` and `#181818`) with the premium Applyr light theme color tokens (`bg-surface-container-lowest` pure white cards, `bg-surface-container-low` cream text inputs, and charcoal text), creating a beautifully unified first impression.

Changed
- **Direct Sidebar Navigation Routing (FR-041):** Added "Settings" directly into the main sidebar's icon navigation, allowing instant single-click access. Clicking "Settings" inside the lower-left profile menu also automatically redirects the active tab to the main Settings page.

---

### 5.9
Applyr Release
May 8, 2026

Version 5.9, first offered to local users on May 8, 2026

Previous
Applyr 5.8

Next
Applyr 6.0 (Planned)

Fixed
- **Robust Company Folder Resolution (FR-045, AC-046):** Integrated a dynamic `resolveCompanyFolder()` path-compatibility helper in `server/index.ts` to solve file/folder slug mismatches caused by trailing underscores or different spacing (e.g., `'Cisco_Systems_Inc_'`), instantly restoring the visibility of compiled PDF assets on the Dashboard and All Jobs review panes.
- **Background URL Backfill Execution (FR-042):** Updated the background scouter orchestrator (`server/scout.ts`) to target the correct path `scripts/archive/backfill_urls.ts` for missing URL crawls, eliminating module-not-found background execution logs.

Changed
- **Dashboard Ready to Apply Filter Integrity (FR-045, AC-046):** Hardened TodayView and Sidebar indicators to count and display only `'Backlog'` status jobs (which have fully ready compiled assets) under "Ready to Apply", keeping jobs with `'New'` or `'Drafted'` pending states in the background.
- **Friendly "Ready to Apply" Notification Labels (FR-045, AC-046):** Re-mapped the notification panel backlog text to read friendly `"matched roles ready to apply"` instead of `"backlog"`.
- **Scout Matched Roles Layout Correction (FR-045, AC-046):** Fixed inverted status badge labels in the active matches list on the Scout page, mapping `'Backlog'` status to a green **Ready to Apply** badge and `'Drafted'` to an amber **Pending Assets** badge.
- **Action Button Copy Streamlining:** Re-labeled the button for backlog items from `"Review"` to `"Apply Now"` inside the All Jobs grid, removing work-like chore implications and inviting immediate submission.

---

### 5.8
Applyr Release
May 8, 2026

Version 5.8, first offered to local users on May 8, 2026

Previous
Applyr 5.7

Next
Applyr 6.0 (Planned)

New
- **Hybrid Scouting Active Filters Panel (FR-042, AC-043):** Deployed a premium, high-impact scouter parameters control card at the very top of the Scouting dashboard, containing live editable inputs for Target Job Title, option chips for Job Type (Remote, Hybrid, On-site), and a locked location indicator. All parameters auto-save to SQLite with beautiful debounced status indicators.
- **Experience Level Multi-Select Dropdown Filter (FR-044, AC-045):** Implemented a high-fidelity dropdown component containing multi-select experience options (Internship, Entry Level, Junior, Mid Level, Senior, Expert) with an immediate clear action. The selected filter values seamlessly persist in real-time to SQLite scouter preferences.
- **Isolated Portfolio and GitHub Fields (FR-043, AC-044):** Fully separated Portfolio and GitHub link text inputs inside the Profile settings sub-tab, enabling structured, isolated data collection instead of combined values.
- **Master Experience Rich Text Context Editor:** Embedded a direct master markdown textarea context editor inside the settings modal's new Experience tab, complete with a "Save & Sync AI" action button to write to `workExperience.md`.

Changed
- **Dashboard Opportunity Visibility (FR-045, AC-046):** Made all newly matched and backlog jobs show up instantly on the TodayView dashboard as "Pending" while their PDF assets are being drafted, preventing them from appearing lost before compilation finishes.
- **Friendly Backlog Notifications (FR-045, AC-046):** Replaced the confusing "need review" backlog alerts with friendly "matched roles in backlog ready to apply" notifications, fully eliminating chore-like wording.
- **Streamlined Sidebar Layout:** Completely eliminated redundant links (Personalization, Profile) from the lower-left sidebar menu, routing settings workflow entirely through the unified Claude-style Settings Modal.
- **Vertical 5-Tab Modal Restructuring:** Restructured Settings Modal sidebar navigation into five streamlined categories: Profile, Job Preferences, Experience, API or Connections, and Analytics.

---

### 5.7

Next
Applyr 6.0 (Planned)

New
- **Premium Claude-Style Overlay Settings Modal (FR-041, AC-042):** Designed and deployed a stunning, high-fidelity settings room overlay mimicking Anthropic Claude's layout. It includes a responsive 2-column sidebar navigation with 8 fully custom settings sub-tabs (General, Account, Privacy, Billing, Usage, Capabilities, Connectors, LLM Engine).
- **Interactive Usage Limit Indicators (FR-041):** Integrated dynamic session and weekly model progress bars (e.g. 4% session usage, 25% weekly limits, daily Selenium routine runs tracker), alongside a functional "Extra Usage" toggle control.
- **Centralized LLM Engine Configuration Tab:** Migrated the dynamic Multi-LLM card selector and cloud/local API keys settings directly into the modal for seamless, unified setup.

Changed
- **Uncluttered Profile View Tab:** Centralized LLM configuration under the dynamic SettingsModal overlay triggered directly from the lower-left sidebar profile menu.

---

### 5.6
Applyr Release
May 8, 2026

Version 5.6, first offered to local users on May 8, 2026

Previous
Applyr 5.5

Next
Applyr 6.0 (Planned)

New
- **Multi-LLM Provider Support (FR-040, AC-041):** Added fully dynamic Multi-LLM provider selection directly inside the Settings tab of My Profile. Users can select between Google Gemini (Cloud), Anthropic Claude (Cloud), and Local LLM (Ollama / LM Studio) with custom API keys and base URL configurations.
- **Dynamic LLM Routing Engine:** Updated the python backend calling utility (`scripts/utils.py:call_llm()`) to dynamically retrieve LLM configurations from the local SQLite database and route requests in real-time. It supports standard OpenAI-compatible endpoints as well as Ollama's direct `/api/chat` native API for maximum local resiliency.
- **ChatGPT-Style Lower-Left Profile Menu:** Designed and implemented a sleek, stateful user profile card at the bottom of the sidebar displaying name/avatar initials, user plan, and a chevron toggle. Clicking the card opens an interactive popup menu with direct links to Preferences, Identity, and Settings tabs, aligning perfectly with modern ChatGPT UI aesthetics.

Changed
- **Header Cleanup:** Streamlined the main layout by completely removing the legacy top-right settings cog button, unifying settings navigation under the new lower-left sidebar menu.

---

### 5.5
Applyr Release
May 7, 2026

Version 5.5, first offered to local users on May 7, 2026

Previous
Applyr 5.4

Next
Applyr 6.0 (Planned)

New
- **Auto-Merging & Duplicate Resolution Utility:** Implemented a background duplicate audit and resolution strategy across active and archived submission directories. It resolved five major directory collisions (Allstate, Expel, GE Healthcare, PeopleGrove, and Ryan) by analyzing SQLite database status, merging files to preserve the largest and most complete copies, and storing safe pre-deletion backups in `scratch/folder_backups/`.
- **Peach Asset Customization & Tailoring:** Generated and compiled high-fidelity, compliant PDF assets (Resume and Cover Letter) tailored for Peach's modern API-first loan management system-of-record, perfectly aligning technical ingestion experience with corporate compliance.

Fixed
- **Multi-Folder OS Collisions:** Resolved duplicate active and archived submission folder states that previously threw Windows `fs.renameSync` EEXIST errors when users updated job statuses in the UI, fully unblocking the status update workflow.

Changed
- **Bulk Application Clearing:** Automatically cleared and archived all remaining folders in the active `submissions/` directory (Carefull, SpotOn, and Bellese) while updating their database statuses to `Applied`.

---

### 5.4
Applyr Release
May 7, 2026

Version 5.4, first offered to local users on May 7, 2026

Previous
Applyr 5.3

Next
Applyr 6.0 (Planned)

New
- **Job Name & Company on Editor Workspace:** Renders the active job title and target company inline inside the WYSIWYG PDF editor's top bar (e.g. `Editing Resume.md for Secureframe (Product Manager – Platform Trust & Security)`), providing clear candidate context during edits.
- **Line-by-Line Section Stripper & Contact Normalizer:** Refactored the Style Compliance Guard (`style_compliance_guard.py`) to process documents line-by-line rather than using complex multiline regexes. This completely prevents vertical whitespace deletion, line merging, and format corruption while aggressively stripping skills/expertise blocks and formatting contact lines.

Fixed
- **Tagline Hyphenation & Corrupted Characters:** Fixed an empty string replacement bug that caused hyphens to be inserted between every character in the tagline block during compilation. Unescaped backslash parentheses `\( \)` are now successfully converted to professional round brackets.

---

### 5.3
Applyr Release
May 7, 2026

Version 5.3, first offered to local users on May 7, 2026

Previous
Applyr 5.2

Next
Applyr 5.4

New
- **Triple Redundancy Style Compliance Guard (FR-036):** Introduced a state-of-the-art formatting auditor and auto-correction script (`style_compliance_guard.py`). It guarantees perfect HTML single-page resume structures across three distinct checkpoints: immediate post-generation cleanup, pre-compilation text capacity compaction (automatic company bullet trimming and dynamic inline font-size scaling), and save-time interception.

Fixed
- **AI Rewrite Log Pollution & Escaped Characters:** Completely eliminated the `[LLM] Calling...` prefix from ruining saved documents by redirecting all Python utility and LLM logging to `sys.stderr`. Updated the system prompt in `ai_rewrite.py` to prevent Gemini from converting HTML style elements to raw Markdown headings or injecting backslash-escaped characters.

Developer
- **Visual Compliance Enforcement on Save:** Connected the compliance guard directly to the Express server's file PUT route and Python's drafting engine, ensuring that all manual edits, AI rewrites, or background pipeline compilations are automatically verified and polished for single-page style compliance.

### 5.2
Applyr Release
May 6, 2026

Version 5.2, first offered to local users on May 6, 2026

Previous
Applyr 5.1

Next
Applyr 6.0 (Planned)

New
- **End-to-End Background Sync (FR-035):** Fully automated the background sync pipeline. After scouting completes, the system now automatically scrapes full descriptions (`scrape_new_jobs.ts`), evaluates fit via the Gemini fit engine (`batch_pipeline.py`), and drafts tailored resumes/cover letters directly in the background. Passed jobs instantly appear on the dashboard under "Ready to Apply"!

Fixed
- **Gatekeeper Queue Cleanup:** Prevented "New" status clutter and stat inflation by registering non-matching or low-scoring scouted jobs in the `stale_jobs` table (to prevent re-crawling) and then completely deleting them from the primary `jobs` table.

Developer
- **Integrated Database Control in Batch Pipeline:** Modified `batch_pipeline.py` to connect directly to `jobagent.sqlite` using standard python `sqlite3` to dynamically fetch job status for idempotent skips, and write back evaluation results (Backlog/Closed status, score, fit summary) automatically.

### 5.1
Applyr Release
May 6, 2026

Version 5.1, first offered to local users on May 6, 2026

Previous
Applyr 5.0

Next
Applyr 6.0 (Planned)

New
- **Job Pipeline Paradigm:** Introduced the Job Pipeline Paradigm Split! Pipeline jobs (unreviewed and reviewed ready-to-apply jobs) are now completely segmented from submitted active applications.
- **Dynamic Gating:** Added a dynamic status flow where `New` (unseen) jobs feature a prominent green badge to differentiate them from `Backlog` (seen) jobs.

Fixed
- **BUG-003 (Asset Dynamic Gate):** Prevented "Ready to Apply" from showing when no PDF assets exist by checking folder contents dynamically on the Express server (`has_assets` check).
- **BUG-006 (Inflated Stat Card):** Fixed the inflated "Total Active" stat card count on the dashboard. It now accurately reflects submitted applications under "Submitted" instead of backlog/pipeline.

Changed
- **Dashboard Separation:** The dashboard layout is redesigned into two clear list groupings: "Ready to Apply" (pre-submission) and "Active Applications" (waiting for contact).
- **Drafting Muting:** Muted `Drafted` status labels to "Drafting..." and hid them from primary dashboard sections to prevent clutter.
- **Jobs Tab Filters:** Re-aligned AllJobsView tab filters to: Backlog, Active, Interviewing, Closed.

Developer
- **100% SDD Compliance:** Achieved 100% SDD (Spec Driven Development) compliance by backfilling 14 missing matrix rows in `traceability-matrix.md` and adding `docs/spec/` requirements `FR-030` to `FR-034`.
- **Systematic Governance:** Added a formal agent rule in `AGENTS.md` enforcing future SDD compliance and GitHub Release Notes.

---
Applyr Release
May 6, 2026

Version 5.0, first offered to local users on May 6, 2026

Previous
Applyr 4.0

Next
Applyr 6.0 (Planned)

New
We have integrated a stunning side-by-side **Visual Document Workspace**! You can now view generated PDFs natively in an inline iframe and edit their Markdown sources directly in-browser using a Toast UI WYSIWYG editor. No more switching back and forth between Applyr and your IDE to polish your application assets.

We've added a **Setting-Gated AI Prompt Panel**! When a Gemini API key is linked in Settings, you can now issue direct, prompt-based instruction to the GenAI client to automatically rewrite sections or documents.

![Applyr v5.0 Inline Actions Layout](file:///C:/Users/Jason/.gemini/antigravity/brain/e6816052-1f6c-47f9-aae1-f3b2f3b7886a/.system_generated/click_feedback/click_feedback_1778100680612.png)

Fixed
Resolved Windows-specific parameter escaping issues on CLI calls. The Express server now processes AI rewrites using secure temporary files under the `scratch/` directory to fully eliminate CLI length limits and character escaping bugs.

Changed
The application detail panel now features a completely streamlined **Inline Actions Layout**. The separate "Edit CoverLetter" and "Edit Resume" buttons have been replaced with beautiful, side-by-side **Edit (pencil icon)** and **Download** buttons directly inline on each PDF asset card.

Developer
Targeted single-file background compiler is now live. Rather than executing heavy batch generation scripts, the system now runs `scripts/compile_single.py` to regenerate PDFs in under 500ms when a save is completed.

---

### 4.0
Applyr Release
April 15, 2026

Version 4.0, first offered to local users on April 15, 2026

Previous
Applyr 3.0

Next
Applyr 5.0

New
Introduced the local web portal containing backlog metrics, active pipelines, and individual job detail panels. Added a dedicated view to adjust API keys, base career models, and work experience parameters in SQLite.

Changed
Migrated from CLI automation execution to a full local single-page web dashboard using an Express backend server and a Vite React frontend SPA client.

---

### 3.0
Applyr Release
March 12, 2026

Version 3.0, first offered to local users on March 12, 2026

Previous
Applyr 2.0

Next
Applyr 4.0

New
Deployed a cynical verification auditing "Hallucination Guard" to strictly check that every claim made in generated documents is anchored in the baseline `workExperience.md` file to prevent AI seniority inflation.

Built initial Markdown-to-PDF conversion pipelines utilizing standard system packages to package draft files.

---

### 2.0
Applyr Release
February 18, 2026

Version 2.0, first offered to local users on February 18, 2026

Previous
Applyr 1.0

Next
Applyr 3.0

New
Implemented the full multi-dimensional Job-Fit Decision Engine evaluating jobs against Jason's B2B Platform experience. Scripted quick-rejection Stage A filter blocklists to eliminate solo-PM, founding PM, low salary, or international roles.

---

### 1.0
Applyr Release
January 10, 2026

Version 1.0, first offered to local users on January 10, 2026

Next
Applyr 2.0

New
Initial system release establishing automated job discovery and parsing crawls of LinkedIn and Built In. Structured extraction of raw text payloads from JDs.

---

## Part 3: Templates & Guidelines
To maintain consistency in future product updates, refer to the **[Release Notes Template](file:///c:/Users/Jason/Desktop/Jason/Resource/Code%20Projects/JobAgent/docs/RELEASE_NOTES_TEMPLATE.md)** inside your `docs/` folder. Copy and paste its structure when adding new release logs.
