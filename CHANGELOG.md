# Changelog — Applyr

All notable changes are documented here at the major milestone level.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
System capabilities reference (what the app can do today) is in [PRODUCT_CAPABILITIES.md](./PRODUCT_CAPABILITIES.md) (local only, gitignored).

---

## [Unreleased]

### Fixed
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
