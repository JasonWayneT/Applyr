# Changelog — Applyr

All notable changes are documented here at the major milestone level.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
System capabilities reference (what the app can do today) is in [PRODUCT_CAPABILITIES.md](./PRODUCT_CAPABILITIES.md) (local only, gitignored).

---

## [Unreleased]

### Added
- **`no-ai-slop` skill integration:** installed the [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop) writing skill globally (`~/.claude/skills/no-ai-slop`) and diffed its AI-slop pattern catalog against `submission_linter.py`'s existing `LR`/`LW` rules for genuine gaps. Added six new `WARN` rules: `LW-015` (throat-clearing openers), `LW-016` (faux-insight/rhetorical setups), `LW-017` (importance puffery), `LW-018` (weasel attribution), `LW-019` (fake-strong hub-verb, e.g. "serves as a centralized hub"), `LW-020` (binary-contrast two-sentence shape, "It's not X. It's Y."). Widened `LW-007` to also catch "Ultimately,"/"Overall," as summary-recap sentence-starters. 9 new tests in `scripts/test_submission_linter.py`. See CLAUDE.md's "Forbidden Language" section for the full rationale and the patterns deliberately left un-mechanized.

### Fixed
- **Job posting URLs never reached the database:** a full 13-submission batch (2026-07-24) went into `jobs` with `url` left `NULL` on every row, and 5 of the 13 had no `jobs` row at all. Root cause: `server/submissionFolders.ts`'s `readJdMeta()` already parses a `URL: <url>` first line out of `Original_JD.txt` when linking a folder to a DB row via `reconcileOrphanSubmissionFolders()`, but nothing in the authoring process had ever written that line — the mechanism existed, it was just never fed. Backfilled the 13 real URLs (from the source CSV exports) directly into `data/jobagent.sqlite` and prepended the `URL:` line to each `Original_JD.txt`. Documented the required format in CLAUDE.md/AGENTS.md's Submission Folder Structure section and in `generate-submission/SKILL.md`'s Stage 3 so future submissions capture it from the start.
- **generate-submission Stage 1 restatement leak:** Stage 2 kept failing the same way across most of a 9-JD batch — cover letters reused resume bullet phrasing for shared accomplishments. Root cause: Stage 1 told authors not to reuse phrases but deferred the check to Stage 2, and `LW-008-PAIR` only caught contrast-frame density, not general phrase overlap. Added `LW-009-PAIR` (shared 6+ word sequences across the resume+letter pair, allowing metric/scope cores) and made Stage 1 require a clean `lint_folder` pair check before handoff.

### Changed
- **2026-07-18/19 architecture pivot:** the biggest change to how the product actually authors documents had zero changelog visibility until now. The deterministic drafting pipeline (`draft_compiler.py` and everything the CR-062→068 entries below improve) is retired as the *authoring* method — Claude now writes resumes/cover letters directly from job-description text and `data/workExperience.md`/`data/master_claims.json` ground truth, verified against `data/conversion_rubric.md` plus a fixed set of deterministic checks (`submission_linter.py`, `quality_checker.py`, `approved_metrics.py`). The pipeline scripts stay in the repo, unmodified, still live behind the web UI's own "Draft" button — this is an authoring-method change, not a deletion. Process: `.claude/skills/generate-submission/SKILL.md`. See `docs/spec/08-implementation/SESSION-HANDOFF-2026-07-18-authoring.md` and `C:\Users\Jason\.claude\plans\magical-booping-wilkes.md`.

### Added
- **CR-062:** `scripts/local_rewrite.py` — the first local-LLM-generation call site in the drafting pipeline that's actually wired live (per CR-059, the default pipeline previously called zero local LLMs for generation, only for embeddings). Implements the "Deterministic-Minimal-LLM" architecture (see `docs/reports/local-llm-builder-architecture-options.md`, ranked #1 of 10 candidate designs): a new `DRAFT_MODE=local_rewrite` value, additive to the existing `compose` default, that naturalizes an already-selected, already-fact-checked sentence at 3 call sites (resume bullets via `claim_composer.compose_bullet`; the summary proof clause via `local_draft_stages.build_summary_deterministic`; cover-letter paragraphs via `cover_letter_renderer._render_block_letter`) using a new `rewrite` stage (`qwen2.5:7b-instruct-q4_K_M`, escalating to `phi3.5:3.8b-mini-instruct-q8_0` on gate failure, hard local-only with no cloud fallback). Grounding is enforced twice: input is always already-verified source text, and output is re-validated against numeric-token-set *equality* (not just no-fabrication) plus a proper-noun/tool subset check, falling back to the verbatim source on any failure — logged to a per-batch audit file (`data/submissions/_batch_audit/{batch_id}/rewrite_fallbacks.log`) for an after-the-fact skim, never a blocking per-submission step. Claim selection, JD profiling, and structure are entirely untouched. 26 regression tests in `scripts/test_local_rewrite.py`; end-to-end calibration run against a real archived JD (tropic) confirmed identical rubric score to the `compose` baseline (76.2/100) with cleaner bullet/paragraph phrasing, 1-page output, and a clean lint pass. See `docs/spec/05-change-requests/CR-062-local-rewrite-harness.md`.
- **CR-062:** Fixed a real side-effect bug found while calibrating the above: `pipeline_env.jd_profile_mode()` and `cover_hook_mode()` treated *any* `DRAFT_MODE` value other than `"compose"` as an implicit switch to the free-form LLM path for JD profiling and cover-hook generation — meaning the new `local_rewrite` mode was silently also flipping unrelated pipeline behavior it was never designed to touch. Both functions now treat `local_rewrite` the same as `compose` for these decisions.
- **CR-063:** Ran the JD theme-extraction & claim-selection test-and-iterate loop against a new 16-JD human-verified eval set (`docs/reports/jd-theme-claim-eval-set.md`). Baseline: 14/45 should-surface claims hit, 0/16 companies with a full pass. Added 10 `THEME_KEYWORDS` entries to `scripts/jd_tailoring.py` (privacy/compliance/identity/access/governance/genai/agentic/llm/cursor/claude) across three rounds — net aggregate stayed flat (one fix + one tag-collision regression, one correctly-firing-but-too-weak fix, one candidate ruled out by hand-calculation before implementation). Piloted both of the CR's own proposed fallbacks with real local infra: semantic re-ranking via cached embeddings (`scripts/measure_semantic_rerank.py`, new) made the aggregate monotonically *worse* across 6 tested scale values (14/45 → 11/45); `jd_profile_mode="llm"` produced byte-identical selection accuracy to the deterministic path on the 3 worst JDs despite genuinely better theme extraction. Both ruled out with measured data. Root cause pinned to `score_claim_for_jd`'s scoring formula (three uncapped, non-deduped scoring loops let generic PM vocabulary out-accumulate rare precise matches) — handed off as CR-064. See `docs/spec/08-implementation/CR-063-jd-theme-claim-selection-loop-tracker.md` for the full round-by-round trail.
- **CR-064:** Reworked `score_claim_for_jd`'s scoring formula in `scripts/jd_tailoring.py` (dedup + rarity weight + DCG breadth dampener), keeping the existing 3-argument signature so all 8 call sites (6 production: `local_draft_stages.py`, `claim_composer.py` ×2, `draft_compiler.py` ×2, `cover_claim_picker.py`; plus `measure_semantic_rerank.py`, `smoke_draft_compiler.py`) need no changes. Fixed two real, verified defects: cross-loop/cross-line token double-counting (a single token like `platform` could score 3+ times) and rare precise matches being under-scored against generic PM vocabulary. **Closed partial (`closed_partial`), goal NOT achieved:** the CR's headline acceptance criterion — that `ACC-105-EXECUTION`'s cross-JD top-5 over-representation measurably drops — was not met. Three independently-implemented, security-cleared, QA-verified mechanisms (dedup, rarity, breadth dampener) each behaved exactly as designed on isolated hand-checks yet moved the metric ~0 on the fullest eval measurement (ACC-105 stayed 10/14 top-5 appearances before and after, 14 companies including archive-sourced sailpoint/group_1001). Two known cover-letter test regressions are deferred, not fixed (`test_cover_claim_picker.py::test_fintech_jd_prefers_dropoff_story`, `test_cover_word_padding.py::test_thin_jd_still_produces_proof_content` — `cover_claim_picker.py`'s flat proof-bonuses interacting with the CR's inflated score scale; a Jason-gated calibration follow-up, deliberately not retuned inside this CR). Recommended next direction is a separate investigation into JD-profile/keyword extraction (upstream of this function, flagged by CR-063), not a further round of scoring-arithmetic. See `docs/spec/05-change-requests/CR-064-claim-score-formula-rework.md` and the round-by-round trail in `docs/spec/08-implementation/CR-064-claim-score-formula-rework-tracker.md`.

### Fixed
- **CR-068:** `build_jd_profile_deterministic`'s `requirements` field (`scripts/jd_tailoring.py`) captured job-posting boilerplate (location, employment type, salary band, benefits copy, interview steps, bare section headings) instead of the JD's real requirement bullets in 4/13 measured companies — starving downstream claim scoring of the real requirement signal. Fixed in two measured rounds, one hypothesis each (CR-064 discipline). Round 1: added `who you are` and `required education and experience` to `_REQ_SECTION_RE`'s heading alternation, and rewired the `requirements` line-scan to source from `extract_req_section(jd_text)` instead of raw `jd_text` (previously the heading-scoping helper was never called on this field). Round 2: raised the line-length cap from 120 to 250 on both the upper-bound test and the store-slice, in lockstep (250 is the measured break point between the real single-bullet population, which tops out ~245-250 chars, and the multi-sentence paragraph-boilerplate class above it — the original cap was silently dropping every long "Trait: elaboration"-style real bullet). Second production code change in the CR-063→064→065→066→067→068 arc. All 4 originally-broken companies substantially improved: OneStream and Remote clean, Ontra and Covideo at 5/6 real bullets + 1 residual section-boundary/ordering artifact each (out of the length-cap-only scope, flagged for a possible Round 3). Full-archive regression check across 250 archived JDs found exactly one marginal regression (`visionaire_partners`, an already near-100%-boilerplate job-board scrape); zero regressions among the 8 previously-good companies. Pytest 28F/195P/1S → 28F/200P/1S (5 new tests in `scripts/test_jd_profile_requirements.py`, same 28 pre-existing failures). No change to `_NEXT_SECTION_RE`, `keywords`, `priority_themes`, `score_claim_for_jd`, `THEME_KEYWORDS`, or `data/master_claims.json`. See `docs/spec/05-change-requests/CR-068-requirements-section-extraction-fix.md` and `docs/spec/08-implementation/CR-068-requirements-section-extraction-fix-tracker.md`.
- **CR-066:** `build_jd_profile_deterministic`'s `keywords` field (`scripts/jd_tailoring.py`) selected the JD's top-12 length-≥5 words by **alphabetical order** (`sorted(set(...))[:12]`), which discarded frequency entirely and systematically surfaced whatever generic vocabulary sorts early over the JD's own defining nouns. Changed to descending in-JD-frequency with alphabetical tie-break (`Counter`-based), keeping the same `[a-z]{5,}` length filter, same 5-word stopword set, same `_jd_body_for_themes()` source text, and same `[:12]` cutoff — signature and all call sites unchanged. This is the first production code change in the CR-063→064→065→066 arc and its first measured win: CR-063 diagnosed the selection problem, CR-064 wrongly attributed it to downstream ranking arithmetic (null result, closed partial), CR-065 root-caused it to `keywords` extraction, CR-066 fixes it. Measured across the 12 available eval-set companies: `ACC-105-EXECUTION`'s cross-JD top-5 over-representation dropped 9/12 → 5/12 (every drop was a company where it was never should-surface), aggregate should-surface hit rate improved 10/34 → 11/34 with zero regressions, pytest 28F/190P/1S → 28F/195P/1S (5 new tests in `scripts/test_jd_profile_keywords.py`, same 28 pre-existing failures). The `requirements`/`extract_req_section()` boilerplate-capture defect (a distinct, still-undiagnosed root cause) is explicitly reserved for a future CR-067, and the under-scoring `ACC-401-AITOOLS`/`ACC-204` problem remains open with no measured evidence an extraction fix addresses it. See `docs/spec/05-change-requests/CR-066-jd-profile-keywords-frequency-fix.md` and `docs/spec/08-implementation/CR-066-jd-profile-keywords-frequency-fix-tracker.md`.
- **CR-061:** AI-Native trigger (batch2-jd-tailoring-findings.md P-005) confirmed failing on ~13 of ~20 manually-reviewed submissions. Root cause was two separate gaps, not one: (1) `draft_compiler.py` stripped the resume PROJECTS section (FR-208) on *any* over-budget render before trimming a single bullet, so it almost never survived — reordered pruning so bullets trim to floor first and PROJECTS is the last resort; also capped `build_projects_section` to the single highest-priority entry (`MAX_PROJECTS`, `local_draft_stages.py`) instead of 3, reducing its budget footprint. (2) The cover letter path had no mechanism at all — `projects_catalog.json` was resume-only and no equivalent claim existed in `master_claims.json` for `cover_claim_picker.py` to select. Added `ACC-401-AITOOLS` (grounded in `workExperience.md` line 44's existing Jason-confirmed AI-tooling note) with `employer: ""` so it can never be mis-selected as a resume experience-section bullet, plus a `has_ai_signal`-gated scoring bonus in `cover_claim_picker._proof_score`. Also found and fixed: the picker's metric-density guard was silently discarding this claim after selection because it has no digit (by design — it's a qualitative capability claim, not a fabricated metric); added a narrow protected-slot exception gated on the same AI signal. Verified against 15 real archived JDs: 12/12 with genuine AI/LLM language now select the claim, 0/3 without it do. Regression tests in `scripts/test_ai_signal_routing.py`.
- **CR-061:** All 8 entries in `data/projects_catalog.json` used a literal em-dash in the project name (`"JobAgent — AI-Powered..."`), which would have hard-blocked the linter (`LR-006`) the first time the PROJECTS section actually survived to a final resume — found while verifying the fix above. Replaced with colons.
- **CR-057:** Missing SQLite transaction boundaries in `jobRepository.ts`. Mutating `jobs` and syncing `jobs_fts` were sequential but non-transactional; a crash midway permanently desynced the full-text search index. Fixed by wrapping `insertJob`, `patchJob`, and `deleteJobRecord` in `db.transaction()`.
- **CR-057:** Type safety vulnerability in external ATS connectors (demonstrated in `theirstack`). `res.json()` was casted and sliced without runtime array validation, causing TypeErrors on malformed payloads. Fixed for TheirStack (returning empty array safely); globally deferred for Zod overhaul.
- **CR-057:** Silent data loss and logic failures caused by swallowed exceptions. `scoutOrchestrator.ts` swallowed `UNIQUE` constraint errors from concurrent inserts, and `openpostings` swallowed ATS sync fetch errors. Both now log errors correctly.
- **CR-056:** Ashby connector called a private/authenticated endpoint (`v1/publishing-posts`, always 401) instead of the public `posting-api/job-board` endpoint; also fixed response parsing (`{jobs:[...]}` wrapper, not a raw array) and the job-URL field name (`jobUrl`, not `jobPostingUrl`). Was returning 0 jobs on every run; now returns real results (verified live: 0 → 15 on the existing watchlist).
- **CR-056:** Workable connector called a deprecated endpoint (`www.workable.com/api/accounts/...`) that Cloudflare now blocks with a 302 redirect instead of JSON. Switched to the working `apply.workable.com/api/v1/widget/accounts/...` endpoint.
- **CR-056:** Working Nomads connector filtered on `category_name` for "product"/"management" — that category never appears in Working Nomads' real taxonomy (Marketing, Development, Design, Sales, etc.), so it always returned 0 regardless of what was actually posted. Switched to title-text matching, consistent with the other connectors; added configurable `searchTerms`.
- **CR-056:** OpenPostings connector pointed at a project-root path that never existed (`OpenPostings-extracted/OpenPostings-main`) and, even when pointed at the right path, parsed the wrong response shape (`{items:[...]}`, not a raw array) — both bugs meant it silently returned 0 jobs on every run, forever. Found the actual OpenPostings project already sitting in `data/archive/` from a prior cleanup, installed its 4 real server dependencies (skipping its unrelated Expo/React-Native app tree), repointed the connector, and fixed the parsing bug. Verified live through the full spawn → sync → search flow (0 → 3 jobs, including a company not on any existing watchlist).
- **CR-056:** Geographic gate (`passesGeographicGate`) auto-rejected any job with a thin/missing description if it wasn't from one of 7 pre-approved remote job boards — even when the job's *title* explicitly named the candidate's local area (e.g. "Product Manager – San Diego, CA"). The short-description branch never checked the title at all. Now checks title against `localAreaTerms` before falling back to the work-setting/source-allowlist check.
- **CR-056:** Settings page (`SettingsView.tsx`) used a single shared debounce timer across every settings field on the page. Editing the Adzuna API key fields, then touching any other field (e.g. the TheirStack key sitting right below it) within 1 second silently cancelled the pending Adzuna save with no error shown — the save badge still read "Saved" for whichever key won the race. Switched to per-key debounce timers. Confirmed via the live database: `adzunaAppId`/`adzunaAppKey` had been silently dropped twice while `theirstackApiKey`, saved through the identical mechanism, persisted correctly.
- **CR-054:** Post-drafting audit non-convergence no longer reports pipeline success. `audit_and_improve_company` returns an `AuditImproveResult` contract; `run_drafting_engine` raises on failure; pre-audit file snapshots restore on non-convergence so bad enhanced drafts cannot ship under normal filenames.
- **CR-055:** Years-gate false positives from incidental JD prose (Jackson Laboratory 90-year history, Civica founded-years) fixed via requirements anchoring and plausibility caps in `seniority_gate.py`.
- **CR-055:** Title blocklist uses role-designation vs focus-area split; `Product Manager, Growth` and NVIDIA developer-productivity titles no longer false-block.
- **CR-053:** Location gate rejects non-SD onsite/hybrid cities, Canada in-person, and EST/CST-only remote postings.
- **CR-053:** Structured evidence-tiered fit scoring (`structured_fit.py`) replaces holistic LLM 0-100 as default path; anchor floor no longer force-promotes scores.

### Removed
- **CR-056:** BuiltIn and Levels.fyi connectors — both used Playwright with a stealth plugin to impersonate a real browser against a live site. Levels.fyi had been silently returning 0 jobs for 10+ days with no visible errors; both were the same category of ban-risk the rest of the connector stack (pure JSON APIs) was built to avoid.
- **CR-056:** Per-company Greenhouse, Lever, Ashby, and Workable connectors — these only work by hand-curating a list of companies to watch, which no longer matches how job search is actually being run (broad PM search by location, not a fixed company list). OpenPostings already covers these same ATS platforms (plus Workday, iCIMS, and others) across ~7,700 companies via free-text search with no watchlist required, making the per-company connectors redundant. Also removed the now-orphaned `shared/domain/atsBoards.ts` loader.

### Changed
- **CR-056:** `experience_range.max` (years-of-experience ceiling used by both the ingestion-time years gate and `seniority_gate.py`) raised from 7 to 8 to match actual years of experience and stop silently rejecting "Senior Product Manager" roles requiring 8 years. Updated through the real `job_search` settings API so the change persists correctly rather than being overwritten on next Settings save.
- **CR-053:** `apply_anchor_floor` records anchor hits in `RiskFlags` only (no score overwrite).
- **CR-054:** `blocked_companies` list in `candidate_preferences.json` enforced at zero-token gate (Unity in example prefs).

### Developer
- **CR-054 Epic 1:** `scripts/test_audit_convergence.py` regression coverage.
- **CR-053/055:** New tests: `test_location_gate`, `test_title_blocklist`, `test_structured_fit`, `test_blocked_companies`, `test_template_lint_sources`; `calibration_harness.py`, `rescore_location_gates.py`.
- **Rollout:** `npm run gate-rollout` / `gate-rollout:apply` merges gate prefs from example and rescores Backlog/New location gates (`apply_gate_rollout.py`).
- **SDD closeout:** Formal `CR-053`/`CR-054`/`CR-055` specs; registry `FR-242`–`FR-248` + `AC-264`–`AC-271`; traceability matrix; `job_fit_engine.md` v5.0; `FR-248` preserve keys in `jobSearchPrefs.ts` + vitest.

---

## [7.1.0] — 2026-06-24

### Changed
- **Cross-device data portability** — All private data (`submissions/`, `archive/`, `jobagent.sqlite`) consolidated under `data/`. Google Drive sync of one folder (`data/`) is now sufficient to move the full application state between devices. No hosted database required.
- **Repo hygiene** — Removed root-level duplicate docs, stale `data/job_fit_engine.md`, accidental `=` file, and 18 files that should never have been tracked (`data/thinking/`, `_bmad-output/`). CI smoke tests now pass reliably after fixing step-ordering bug that caused `python: command not found` on ubuntu-latest.

### Fixed
- `server/routes/system.ts` — local-model streaming route no longer crashes; reads LLM settings from SQLite `profiles` table instead of missing `.agent/llm_settings.json`.
- `scripts/utils.py` — `ARCHIVE_DIR` constant aligned to `data/archive/submissions` (was `archive/`, now matches the active archive path used by all scripts).
- README doc links in root table pointed at deleted root copies of `AGENTS.md` and `SDD_PROCESS.md`; corrected to `docs/` canonical versions.
- Example files moved to live next to their real counterparts in `data/`: `ats_watchlist.example.json`, `cover_voice.example.md`.

### Developer
- 64-file path refactor updating every `submissions/`, `archive/`, and `jobagent.sqlite` reference across Python scripts, TypeScript scripts, server files, CI config, audit script, and `.gitignore`.
- `package.json` `dev:server` tsx watch exclusions simplified — single `--exclude "data/**"` replaces four separate patterns.
- `scripts/regeneration_log.txt` added to `.gitignore` (was untracked runtime output).

---

## [7.0.0] — 2026-06-12

### Added
- **Epic 1: Modular Connector Architecture & Crawl Governance** — Refactored all 12 existing connectors to a clean, isolated `JobConnector` contract; introduced a domain policy gate (`domain_policies`) to govern BuiltIn and Levels.fyi crawlers.
- **Epic 2: Expanded Source Coverage** — Added Greenhouse, Lever, Ashby, Workable, and TheirStack API connectors with credit usage checks (200 credits/month TheirStack cap).
- **Epic 3: Raw Ingest & Deduplication** — Storing raw job payloads in `job_ingest_raw` with post-sync job clustering (`clusterDedup`), showcasing multi-source attribution in the job details.
- **Epic 4: Scoring Transparency** — Persisted multi-dimensional scoring breakdowns in `job_scores` and rendered interactive score breakdowns ( seniorities, domain compatibility, salary, location gates) in the job detail panel.
- **Epic 5: Live Pipeline Observability** — Implemented Server-Sent Events (SSE) stream backend and real-time React EventSource hooks to update progress logs, active stage progress, and source health badges dynamically.
- Unified test runner (`npm test`) that runs both Python unit/regression test scripts and the Vitest TypeScript suite, providing a clean dashboard summary and non-zero exit code on failure (CR-046).
- Windows encoding robustness in the test runner, setting `PYTHONIOENCODING=utf-8` on child processes and using `errors="replace"` on `subprocess.run` decoders to prevent console crashes.


---

## [6.2.31] — 2026-06-01

### Added
- Deterministic cover letter voice engine — proof paragraphs use verified catalog text only, no LLM voice rewrite, word band enforced at 300–400 words
- Resume quality enforcement with strict conversion critique gate — blocks PDF export until human-mirror critique passes, with auto-retry loop

### Changed
- Cover letters no longer append boilerplate bridge phrases on every proof paragraph
- Job source count expanded to 12 active sources (added Jobicy, Working Nomads, JobsCollider)

---

## [6.0.0] — 2026-05-13

### Added
- Semantic anti-hallucination engine — mathematical verification that all percentages, dollar values, and user scales in generated text are valid subsets of ground truth
- Stateful orchestration with stage recovery — sync crashes no longer reset the full batch queue; re-triggering restores the precise failed sub-stage
- Early location gate embedded in the scout aggregator — filters out-of-bounds listings before database storage

### Fixed
- SQLite write-ahead logging configured globally — eliminates database locking deadlocks during high-concurrency execution

---

## [5.0.0] — 2026-04-16

### Added
- Deterministic claim-to-ID verification — LLM must anchor all resume and cover letter claims using bracketed proof codes (`ACC-NNN`, `MET-NNN`, `VOC-NNN`) from `workExperience.md`; codes stripped before final PDF output
- Automated verification retry loop — up to 3 attempts; hallucinated or invented IDs trigger a localized rewrite before failing
- Multi-LLM fallback chain — Gemini → Claude → Ollama with instant failover on 429 or provider error; no run lost to a single provider outage

---

## [4.0.0] — 2026-04-15

### Added
- Local web portal with dashboard metrics, active pipeline view, and per-job detail panels
- Settings UI for LLM provider keys, work experience, and search preferences — all stored in SQLite, no `.env` file required

### Changed
- Migrated from CLI-only execution to a full local single-page web app (React 19 + Vite frontend, Express backend)

---

## [3.0.0] — 2026-03-12

### Added
- Anti-hallucination guard — audits every generated document against `workExperience.md` to prevent AI seniority inflation or invented credentials
- Markdown-to-PDF compilation pipeline using headless Chromium

---

## [2.0.0] — 2026-02-18

### Added
- Multi-dimensional job-fit scoring engine evaluating roles across four vectors: leadership fit, seniority fit, technical depth, transition potential
- Deterministic fast gate — instantly rejects roles matching solo-PM traps, founding PM roles, low salary, or non-US location before spending any LLM tokens

---

## [1.0.0] — 2026-01-10

### Added
- Initial release: automated job discovery and crawling across LinkedIn and Built In
- Structured extraction of raw job description text for downstream processing
