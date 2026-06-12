# Changelog — Applyr

All notable changes are documented here at the major milestone level.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Full granular release history (60+ patch versions) is in [PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md](./PRODUCT_CAPABILITIES_AND_RELEASE_NOTES.md).

---

## [Unreleased]

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
