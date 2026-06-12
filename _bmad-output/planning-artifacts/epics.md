---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-Applyr-2026-06-11/prd.md
  - _bmad-output/planning-artifacts/architecture.md
---

# Applyr - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Applyr, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

**Cluster 1 — Source Expansion**

FR-101: Create a `sources` table as a registry for all job sources. Each record tracks: source name, type (ats_api / vendor_api / crawl), provider, base URL or API endpoint, authentication details, poll frequency, and current status (active / warning / error / paused).

FR-102: Add Greenhouse as a Lane 1 ATS API connector using the public Job Board API. Fetches structured job postings directly from employer ATS systems. Implements the `JobConnector` interface (FR-201).

FR-103: Add Lever as a Lane 1 ATS API connector using the public postings feed. Implements the `JobConnector` interface.

FR-104: Add Ashby as a Lane 1 ATS API connector using the public posting API. Targets newer startups and AI-native companies. Implements the `JobConnector` interface.

FR-105: Add TheirStack as a Lane 2 vendor connector. Must use filtered queries (PM roles, US, recent postings) to stay within the 200 API credit/month hard cap. Credits are consumed per job record returned — unfiltered queries are not permitted. Implements the `JobConnector` interface.

FR-106: Source health states surface in the existing Sync Activity UI: Warning (source returned 0 jobs or HTTP error) and Error (3+ consecutive sync failures). Health badges update live during a sync run.

FR-107: A failing source does not block the rest of the pipeline. Each source connector runs independently; failures are logged to the sources table and surfaced via FR-106 without interrupting other sources.

FR-108: Add Workable as a Lane 1 ATS API connector using the public widget/API. Implements the `JobConnector` interface.

**Cluster 2 — Connector Architecture**

FR-201: Define a formal TypeScript interface that all connectors must implement: `sourceId: string`, `fetchJobs(since?: string): Promise<RawJobPayload[]>`, `healthCheck(): Promise<ConnectorHealth>`, `normalize(raw: RawJobPayload): NormalizedJob`. This interface is the contract for all connectors — new and existing.

FR-202: All 12 existing connectors currently in `scout_local.ts` are refactored into isolated modules implementing `JobConnector`. Connector behavior is preserved; only structure changes.

FR-203: Greenhouse, Lever, Ashby, Workable, and TheirStack connectors are built as isolated modules implementing `JobConnector` from the start.

FR-204: Each connector lives in its own module under `packages/connectors/`. Each is independently testable with unit tests and example fixtures. Source-specific logic does not leak across connectors.

**Cluster 3 — Raw Ingest & Deduplication**

FR-301: Create a `job_ingest_raw` table that stores every raw payload before normalization. Fields: source_id, fetched_at, external_job_id, payload_json, payload_hash (for change detection), http_status, request_url. Supports replay and debugging when upstream APIs change format.

FR-302: Create a `job_clusters` table that groups duplicate job records identified across sources into a single cluster.

FR-303: Create a `job_source_links` table that links every source copy of a job to its canonical record in the `jobs` table. One canonical job can have many source links.

FR-304: Existing deduplication logic (URL normalization, Company + Title pair matching, vector similarity) is promoted into a formal dedup service that writes results to `job_clusters` and `job_source_links`. Logic is preserved; structure is formalized. Two services: `ingestDedup` (inline URL check at ingest) and `clusterDedup` (cross-source cluster assignment post-ingest).

FR-305: The UI shows one canonical job record. Source attribution (which sources the job appeared in) is accessible as metadata on the job detail, not as separate job entries.

FR-306: The system tracks which sources contribute unique jobs vs. duplicating jobs already seen from other sources. This data is available in the sources table or run metrics for coverage analysis.

**Cluster 4 — Scoring Calibration**

FR-401: Create a `job_scores` table storing the full scoring breakdown per job: component scores for each scoring dimension (role-family match 30pts, domain match 20pts, seniority match 15pts, work arrangement 15pts, company desirability 10pts, location compatibility 5pts, compensation signal 5pts), deterministic gate results (title blocklist, salary, location), total score, human-readable reason summary, and review state. Schema: `job_scores(id, job_id, score_total, score_breakdown_json, reason_summary, review_state, scored_at, is_latest)`.

FR-402: The score breakdown from `job_scores` is surfaced in the existing job detail panel. A user can open any surfaced job and immediately see why it scored the way it did — no pipeline debugging required.

FR-403: The existing scoring levers (title blocklist, industry blocklist, salary threshold, min fit score, location gate) are validated against documented expected behavior. Any mismatch between configuration and actual gate behavior is identified and corrected.

FR-404: Unit tests cover the deterministic gate (title blocklist, salary, location) and scoring thresholds. Tests include PM-positive examples (should pass) and non-PM examples (should be rejected) to catch regressions.

FR-405: Jobs are bucketed into priority tiers based on total score: 85–100 = High priority (triggers full action workflow), 70–84 = Review queue (surfaced for manual review), 50–69 = Low-priority backlog (available but not surfaced by default), <50 = Hidden (not shown in UI).

**Cluster 5 — Pipeline Observability**
*(Note: FR-501 through FR-505 depend on Cluster 2 being complete)*

FR-501: Each connector emits real-time metrics during a sync run via the existing SSE mechanism: jobs fetched, jobs filtered, jobs passed to scoring. Emitted per source, per stage.

FR-502: The existing SyncActivityView displays live per-source counts during a sync: fetched / filtered / passed to scoring. Counts update in real-time as each connector completes.

FR-503: Real-time counts are visible at each pipeline stage boundary: Scout → Backfill → Scrape → Evaluate. Users can see where jobs are being filtered out during the active run.

FR-504: Source health badges (FR-106) update in real-time during a sync. A source that goes to warning or error mid-run is surfaced immediately in the Sync Activity UI.

FR-505: After each sync completes, a summary is written to the activity log: per-source job counts, any sources that went to warning or error, and total jobs passed to scoring.

**Cluster 6 — Crawl Governance**

FR-601: Create a `domain_policies` table that governs all crawl activity. Each record tracks: domain, robots.txt review status and date, terms-of-service review status and date, max requests per second, cooldown window in seconds, and current status (allowed / paused / blocked / manual_review).

FR-602: No crawl connector may fetch a domain unless `domain_policies.status = allowed`. Rules: never crawl without explicit `allowed` status; stop automatically after repeated 403 or 429 responses (update status to `blocked`); apply exponential backoff and jitter on 429; do not bypass auth walls or CAPTCHAs; log every crawl decision to activity log.

FR-603: The two existing Playwright crawl connectors (BuiltIn, Levels.fyi) are brought under the domain policy engine as part of the Cluster 2 refactor. Their domains are pre-reviewed and seeded into `domain_policies` with appropriate rate limits before the refactor ships.

---

### NonFunctional Requirements

NFR-1: Schema migrations are idempotent and non-destructive — 7 new tables added to a live SQLite database with existing data; no data loss permitted.

NFR-2: Local-first — no data leaves the user's machine. All new connectors fetch to local storage only; no cloud sync or telemetry.

NFR-3: TheirStack hard credit cap — maximum 200 API credits/month. TheirStack connector must use filtered queries and enforce this limit in code before each fetch.

NFR-4: Connector isolation — one connector failure cannot cascade to other connectors or block the pipeline.

NFR-5: Idempotent syncs — running a sync twice produces the same result. No duplicate jobs, no duplicate raw ingest records.

NFR-6: API compliance — rate limits and terms of service respected for all Lane 1 ATS connectors and TheirStack.

---

### Additional Requirements

- **Brownfield expansion** — no starter template. All new code adds to the existing Node 18+ / TypeScript / Express 5 / React 19 / SQLite stack.
- **Migration runner**: `server/migrations/NNN_description.sql` with a `schema_migrations` version table. Runner in `server/db.ts` checks the version table before applying each file at server startup. All migration SQL must be idempotent (`CREATE TABLE IF NOT EXISTS`).
- **7 new tables** to create via migrations: `sources`, `job_ingest_raw`, `job_clusters`, `job_source_links`, `job_scores`, `domain_policies`, `schema_migrations` (version table).
- **Shared types file**: `shared/types/connectors.ts` is the single source of truth for `JobConnector`, `RawJobPayload`, `NormalizedJob`, `ConnectorHealth`, `SourceStatus`, `SSEEvent`. Never redefined locally.
- **Connector module location**: `packages/connectors/{name}/index.ts` for all 16 connectors (12 refactored + 4 new ATS + TheirStack).
- **Hybrid dedup services**: `server/services/ingestDedup.ts` (URL existence check before inserting to `job_ingest_raw`) and `server/services/clusterDedup.ts` (cross-source cluster assignment post-ingest pass).
- **Crawl policy middleware**: `server/middleware/crawlPolicy.ts` — orchestrator calls `checkCrawlPolicy(domain)` before invoking any connector with `source_type = 'crawl'`.
- **SSE typed event envelopes** — 5 event types: `source_progress`, `stage_handoff`, `source_health`, `connector_error`, `run_complete`. Never free-form strings.
- **`job_scores` write pattern**: Always a 2-step transaction — (1) set `is_latest = false` on all existing rows for that `job_id`, then (2) insert new row with `is_latest = true`.
- **TheirStack credit fields**: `sources` table gains `credits_used_this_month` and `credits_reset_at`. Connector reads before every fetch; logs WARN within 20% of cap; aborts with ERROR when cap would be exceeded.
- **`server/scout.ts` refactor**: Currently the monolith connector runner. After Cluster 2 it becomes a thin orchestrator invoking `packages/connectors/` modules.
- **`scripts/scout_local.ts` deletion**: Deleted after Cluster 2 refactor completes.
- **New API endpoints**: `GET /api/sources`, `POST /api/sources/:id/sync`, `GET /api/domain-policies`, `PATCH /api/domain-policies/:id`.
- **Two existing files updated**: `src/components/JobDetailPanel.tsx` (score breakdown section) and `src/pages/SyncActivityView.tsx` (live per-source metrics + health badges).
- **No new runtime dependencies** — zero new packages by architecture decision.
- **Cluster 5 implementation sequence constraint**: Observability instrumentation (FR-501–505) must be implemented after Cluster 2 connector architecture is complete.

---

### UX Design Requirements

None — no UX design document exists for this expansion. All UI changes are targeted additions to existing components (`JobDetailPanel.tsx`, `SyncActivityView.tsx`) as defined by the PRD and Architecture.

---

### FR Coverage Map

FR-101: Epic 2 — Sources registry table tracking all configured sources
FR-102: Epic 2 — Greenhouse connector
FR-103: Epic 2 — Lever connector
FR-104: Epic 2 — Ashby connector
FR-105: Epic 2 — TheirStack connector with credit guard
FR-106: Epic 2 — Source health visibility in Sync Activity UI
FR-107: Epic 2 — Graceful source failure, no pipeline blocking
FR-108: Epic 2 — Workable connector
FR-201: Epic 1 — JobConnector interface in shared/types/connectors.ts
FR-202: Epic 1 — Refactor 12 existing connectors to interface
FR-203: Epic 2 — New connectors built to JobConnector interface
FR-204: Epic 1 — Connector isolation, testability, unit tests and fixtures
FR-301: Epic 3 — job_ingest_raw table
FR-302: Epic 3 — job_clusters table
FR-303: Epic 3 — job_source_links table
FR-304: Epic 3 — Formal dedup services (ingestDedup + clusterDedup)
FR-305: Epic 3 — Canonical UI presentation with source attribution in job detail
FR-306: Epic 3 — Source overlap tracking in sources table / run metrics
FR-401: Epic 4 — job_scores table (1:many, is_latest flag)
FR-402: Epic 4 — Score breakdown section in JobDetailPanel
FR-403: Epic 4 — Lever validation and correction
FR-404: Epic 4 — Scoring unit test coverage
FR-405: Epic 4 — Score bands and priority tier routing
FR-501: Epic 5 — Real-time source metrics via SSE
FR-502: Epic 5 — Enhanced SyncActivityView with live per-source counts
FR-503: Epic 5 — Per-stage handoff counts (Scout → Backfill → Scrape → Evaluate)
FR-504: Epic 5 — Live source health badge updates during sync
FR-505: Epic 5 — Post-run summary to activity log
FR-601: Epic 1 — domain_policies table
FR-602: Epic 1 — Crawl policy engine (checkCrawlPolicy middleware)
FR-603: Epic 1 — Existing crawl connectors (BuiltIn, Levels.fyi) governed

## Epic List

### Epic 1: Connector Architecture Foundation
The system has a clean, testable connector architecture. All 12 existing connectors run through the `JobConnector` interface, crawl connectors are governed by a domain policy gate, and the numbered migration runner is in place — making the codebase safely extensible for all expansion work that follows. Existing behavior is fully preserved.
**FRs covered:** FR-201, FR-202, FR-204, FR-601, FR-602, FR-603

### Epic 2: Expanded Source Coverage
The pipeline pulls from 5 additional high-quality job sources — Greenhouse, Lever, Ashby, Workable, and TheirStack. All sources are tracked in a central registry. Source health states (warning/error) are visible in the Sync Activity UI, and one failing source never blocks the rest of the run.
**FRs covered:** FR-101, FR-102, FR-103, FR-104, FR-105, FR-106, FR-107, FR-108, FR-203

### Epic 3: Raw Ingest & Deduplication
Every raw job payload is stored before processing, enabling debugging and replay when upstream APIs change. Duplicate jobs appearing across multiple sources are merged into single canonical records. Source attribution (which sources a job appeared in) is visible in the job detail panel.
**FRs covered:** FR-301, FR-302, FR-303, FR-304, FR-305, FR-306

### Epic 4: Scoring Transparency
Every surfaced job shows a detailed score breakdown in the job detail panel — role-family match, domain fit, seniority, work arrangement, and more. Priority tiers automatically route jobs to the right queue. Scoring levers are validated against expected behavior and regression-tested.
**FRs covered:** FR-401, FR-402, FR-403, FR-404, FR-405

### Epic 5: Live Pipeline Observability
During any sync run, users see real-time per-source metrics (fetched / filtered / passed), live health badge updates, and stage-by-stage handoff counts — all in the existing Sync Activity UI. A post-run summary is written to the activity log after each sync.
**FRs covered:** FR-501, FR-502, FR-503, FR-504, FR-505
**Prerequisite:** Epic 1 must be complete

---

## Epic 1: Connector Architecture Foundation

The system has a clean, testable connector architecture. All existing connectors run through the `JobConnector` interface, crawl connectors are governed by a domain policy gate, and the numbered migration runner is in place — making the codebase safely extensible for all expansion work that follows. Existing behavior is fully preserved.

### Story 1.1: Migration Runner and Connector Contract

As a developer implementing the Applyr expansion,
I want a versioned migration runner and the `JobConnector` shared type contract in place,
So that all downstream stories have a consistent interface to implement and a safe, idempotent mechanism for applying schema changes.

**Acceptance Criteria:**

**Given** the server starts after this story is merged
**When** `server/db.ts` runs its startup initialization
**Then** a `schema_migrations` table exists with columns `id TEXT PRIMARY KEY` and `applied_at TEXT`
**And** the runner scans `server/migrations/` for `*.sql` files in ascending numeric order, applies any not yet recorded, and records each applied file in `schema_migrations`

**Given** a migration file has already been applied and recorded in `schema_migrations`
**When** the server restarts
**Then** the runner skips that file — no re-execution, no error

**Given** `shared/types/connectors.ts` is created at the repo root
**When** imported from `packages/connectors/`, `server/`, or `tests/`
**Then** the following are exported: `JobConnector` (interface with `sourceId: string`, `fetchJobs(since?: string): Promise<RawJobPayload[]>`, `healthCheck(): Promise<ConnectorHealth>`, `normalize(raw: RawJobPayload): NormalizedJob`), plus `RawJobPayload`, `NormalizedJob`, `ConnectorHealth`, `SourceStatus`, `SSEEvent`

**Given** a connector file at `packages/connectors/{name}/index.ts` imports `import type { JobConnector } from '../../../shared/types/connectors.js'`
**When** TypeScript compiles
**Then** the import resolves without error

**Given** `npm run lint` and `npx tsc --noEmit` run
**When** both complete
**Then** zero errors

---

### Story 1.2: Refactor Remote-First API Connectors — Batch 1

As a developer,
I want six of the existing remote-first API connectors refactored into isolated `JobConnector` modules,
So that they are independently testable and consistently structured ahead of the orchestrator refactor.

*Connectors in scope: remotive, remoteok, weworkremotely, himalayas, themuse, jobicy*

**Acceptance Criteria:**

**Given** each connector is created at `packages/connectors/{name}/index.ts`
**When** the module is imported
**Then** it exports a named `{name}Connector` constant typed as `JobConnector`
**And** `JobConnector` is imported from `shared/types/connectors.ts` — never redefined locally

**Given** `fetchJobs()` is called with a fixture payload in `packages/connectors/{name}/{name}.test.ts`
**When** the unit test runs
**Then** the test asserts the normalized output matches `NormalizedJob[]` shape
**And** a second test asserts an empty-response fixture returns `[]` without throwing

**Given** each connector's directory at `packages/connectors/{name}/`
**When** inspected
**Then** contains `index.ts`, `{name}.test.ts`, and `fixtures/` with at least one sample JSON payload

**Given** `npm run test:vitest` and `npm run lint`
**When** both run
**Then** all 6 connectors' tests pass and zero ESLint errors

---

### Story 1.3: Refactor Remaining API Connectors — Batch 2

As a developer,
I want the remaining non-crawl API connectors refactored into isolated `JobConnector` modules,
So that all non-crawl sources are consistently structured before the orchestrator refactor.

*Connectors in scope: workingnomads, jobscollider, adzuna (plus any remaining non-crawl connectors from scout_local.ts not covered in Batch 1)*

**Acceptance Criteria:**

**Given** each connector is created at `packages/connectors/{name}/index.ts`
**When** imported
**Then** exports `{name}Connector: JobConnector` with `JobConnector` from `shared/types/connectors.ts`

**Given** unit tests run against fixture data
**When** `npm run test:vitest` executes
**Then** normalized output shape is asserted and empty-response test passes for each connector

**Given** each connector directory
**When** inspected
**Then** contains `index.ts`, `{name}.test.ts`, `fixtures/` with at least one sample payload

**Given** `npm run lint`
**When** run
**Then** zero ESLint errors on all new files

---

### Story 1.4: Crawl Governance and Crawl Connector Refactor

As a user of Applyr,
I want all crawl activity governed by a domain policy gate before any browser fetch occurs,
So that BuiltIn and Levels.fyi are crawled responsibly and no future crawl connector can bypass policy review.

**Acceptance Criteria:**

**Given** the server starts after this story is merged
**When** the migration runner applies pending files
**Then** a `domain_policies` table exists with columns: `domain TEXT PRIMARY KEY`, `robots_reviewed INTEGER`, `robots_reviewed_at TEXT`, `tos_reviewed INTEGER`, `tos_reviewed_at TEXT`, `max_rps REAL`, `cooldown_seconds INTEGER`, `status TEXT` (CHECK `allowed` | `paused` | `blocked` | `manual_review`)
**And** seed rows exist for `builtin.com` and `levels.fyi` with `status = 'allowed'` and conservative rate limits

**Given** `checkCrawlPolicy(domain)` from `server/middleware/crawlPolicy.ts` is called with a domain where `status = 'allowed'`
**When** the function executes
**Then** it returns `{ status: 'allowed' }` via synchronous `better-sqlite3` (no async/await)

**Given** `checkCrawlPolicy(domain)` is called for a domain not in `domain_policies` or with `status != 'allowed'`
**When** the check runs
**Then** it returns a non-`'allowed'` result, logs a WARN via `logActivity`, and does NOT throw

**Given** `packages/connectors/builtin/index.ts` and `packages/connectors/levelsfyi/index.ts` implement `JobConnector`
**When** `fetchJobs()` is called on either
**Then** `checkCrawlPolicy(domain)` runs before any Playwright browser action
**And** if policy status is not `'allowed'`, `fetchJobs()` returns `[]` immediately and logs a WARN

**Given** a unit test simulates a `blocked` domain policy for a crawl connector
**When** `fetchJobs()` runs
**Then** returns `[]` with no Playwright interaction (verified by mock/spy)

**Given** `npm run lint` and `npm run test:vitest`
**When** both run
**Then** zero errors, all tests pass

---

### Story 1.5: Connector Orchestrator Refactor and Legacy Cleanup

As a user of Applyr,
I want the sync pipeline to invoke all connectors through the clean `packages/connectors/` modules,
So that `scout_local.ts` is eliminated and connector behavior is fully modular and transparent.

**Acceptance Criteria:**

**Given** `server/scout.ts` is refactored into a thin orchestrator
**When** a sync run is triggered
**Then** all connectors from stories 1.2, 1.3, and 1.4 are invoked via their `JobConnector` interface exports from `packages/connectors/`
**And** `scripts/scout_local.ts` does not exist in the repository

**Given** any single connector throws an error or returns unexpectedly empty results
**When** the orchestrator processes that connector
**Then** execution continues to the next connector without halting the pipeline
**And** the error is written via `logActivity('ERROR', sourceName, message)`

**Given** a crawl connector (builtin or levelsfyi) is invoked by the orchestrator
**When** the orchestrator calls it
**Then** an activity log entry from `checkCrawlPolicy` is present, confirming the gate fired

**Given** a full sync run completes after the refactor
**When** the activity log is inspected
**Then** all previously-working connector sources appear — no sources silently dropped

**Given** `npm run lint`, `npm run test:vitest`, and `npx tsc --noEmit`
**When** all three run
**Then** zero errors in all checks

---

## Epic 2: Expanded Source Coverage

The pipeline pulls from 5 additional high-quality job sources — Greenhouse, Lever, Ashby, Workable, and TheirStack. All sources are tracked in a central registry. Source health states (warning/error) are visible in the Sync Activity UI, and one failing source never blocks the rest of the run.

### Story 2.1: Sources Registry, API, and Existing Connector Health Wiring

As a user of Applyr,
I want all job sources tracked in a central registry with health state,
So that I have a single view of every source, its current status, and its sync history.

**Acceptance Criteria:**

**Given** the server starts after this story is merged
**When** the migration runner applies `001_add_sources.sql`
**Then** a `sources` table exists with columns: `id TEXT PRIMARY KEY`, `name TEXT`, `type TEXT` (ats_api | vendor_api | crawl), `provider TEXT`, `base_url TEXT`, `auth_details TEXT`, `poll_frequency_hours INTEGER`, `status TEXT` (active | warning | error | paused), `last_success_at TEXT`, `last_error_at TEXT`, `consecutive_failures INTEGER DEFAULT 0`, `credits_used_this_month INTEGER DEFAULT 0`, `credits_reset_at TEXT`
**And** seed rows exist for all existing connectors with `status = 'active'`

**Given** `GET /api/sources` is called
**When** the request completes
**Then** response is a flat JSON array of source records (no wrapper envelope)

**Given** `POST /api/sources/:id/sync` is called for a valid source id
**When** received
**Then** a single-source sync is triggered and response includes `{ id, started: true }`

**Given** a connector run completes successfully in `server/scout.ts`
**When** the orchestrator finishes that connector
**Then** `sources.last_success_at` is updated to the current ISO timestamp and `consecutive_failures` is reset to 0

**Given** a connector run fails
**When** the orchestrator catches the error
**Then** `sources.last_error_at` updates, `consecutive_failures` increments by 1, and `status` is set to `'warning'` (1–2 failures) or `'error'` (3+ failures)

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

---

### Story 2.2: Greenhouse and Lever Connectors

As a user of Applyr,
I want job postings fetched from Greenhouse and Lever ATS systems,
So that the pipeline covers companies using these two widely-adopted platforms.

**Acceptance Criteria:**

**Given** `packages/connectors/greenhouse/index.ts` exports `greenhouseConnector: JobConnector`
**When** `fetchJobs()` runs against a fixture
**Then** normalized output matches `NormalizedJob[]` shape with correct field mapping

**Given** `packages/connectors/lever/index.ts` exports `leverConnector: JobConnector`
**When** `fetchJobs()` runs against a fixture
**Then** normalized output matches `NormalizedJob[]` shape

**Given** a successful run for either connector
**When** the run completes
**Then** `sources.last_success_at` updates and `consecutive_failures` resets to 0

**Given** a run fails (HTTP error, network timeout)
**When** the failure is caught
**Then** `sources.last_error_at` and `consecutive_failures` update in `sources`
**And** a `{ type: 'connector_error', source, error, http_status? }` SSE event is emitted

**Given** an empty-response fixture
**When** the unit test runs
**Then** `fetchJobs()` returns `[]` without throwing

**Given** both connectors are added to the orchestrator in `server/scout.ts`
**When** a sync runs
**Then** both are invoked as part of the run sequence

**Given** `npm run test:vitest` and `npm run lint`
**When** both run
**Then** all tests pass, zero ESLint errors

---

### Story 2.3: Ashby and Workable Connectors

As a user of Applyr,
I want job postings fetched from Ashby and Workable ATS systems,
So that the pipeline covers newer startups (Ashby) and SMBs (Workable) using these platforms.

**Dev note — Ashby auth (OQ-1):** Verify whether Ashby requires a public board token or a private API key before implementing. If a private key is needed, follow the existing auth pattern in the codebase — do not hardcode credentials.

**Acceptance Criteria:**

**Given** `packages/connectors/ashby/index.ts` exports `ashbyConnector: JobConnector`
**When** `fetchJobs()` runs against a fixture
**Then** normalized output matches `NormalizedJob[]` shape

**Given** `packages/connectors/workable/index.ts` exports `workableConnector: JobConnector`
**When** `fetchJobs()` runs against a fixture
**Then** normalized output matches `NormalizedJob[]` shape

**Given** successful and failure scenarios for both connectors
**When** runs complete or fail
**Then** both update `sources` health fields and emit `connector_error` SSE on failure (same pattern as Story 2.2)

**Given** empty-response fixtures
**When** unit tests run
**Then** both return `[]` without throwing

**Given** both connectors added to `server/scout.ts`
**When** a sync runs
**Then** both are invoked

**Given** `npm run test:vitest` and `npm run lint`
**When** both run
**Then** all tests pass, zero ESLint errors

---

### Story 2.4: TheirStack Connector with Credit Guard

As a user of Applyr,
I want job postings fetched from TheirStack with a hard 200 credit/month cap enforced in code,
So that the pipeline benefits from TheirStack's coverage without ever exceeding the free-tier limit.

**Acceptance Criteria:**

**Given** `packages/connectors/theirstack/index.ts` exports `theirstackConnector: JobConnector`
**When** `fetchJobs()` runs and `credits_used_this_month` in `sources` is below 160 (80% of cap)
**Then** the connector proceeds with a filtered PM-role / US / recent query

**Given** `credits_used_this_month` is between 160 and 199
**When** `fetchJobs()` runs
**Then** the fetch proceeds AND `logActivity('WARN', 'theirstack', 'Approaching credit cap: N/200 used')` fires

**Given** `credits_used_this_month` is 200 or the planned fetch would reach or exceed 200
**When** `fetchJobs()` is called
**Then** returns `[]` immediately — no HTTP request is made
**And** `logActivity('ERROR', 'theirstack', 'Credit cap reached: fetch aborted')` fires
**And** `sources.status` is set to `'paused'`

**Given** the credit guard reads from `sources`
**When** it executes
**Then** uses synchronous `better-sqlite3` — no async/await on the DB call

**Given** a unit test simulates `credits_used_this_month = 200`
**When** `fetchJobs()` runs
**Then** no HTTP fetch is made and `[]` is returned

**Given** connector added to `server/scout.ts`
**When** a sync runs
**Then** TheirStack is invoked as part of the sequence

**Given** `npm run test:vitest` and `npm run lint`
**When** both run
**Then** all tests pass, zero ESLint errors

---

### Story 2.5: Source Health Visibility in Sync Activity UI

As a user of Applyr,
I want to see the health state of each source in the Sync Activity UI,
So that I can immediately tell which sources are working, warning, or failing.

**Acceptance Criteria:**

**Given** `SyncActivityView.tsx` is updated to fetch `GET /api/sources`
**When** the page loads
**Then** each source appears with a health badge reflecting its current `status` (active | warning | error | paused)

**Given** a source's `status` is `'warning'`
**When** the badge renders
**Then** it shows a warning indicator visually distinct from active

**Given** a source's `status` is `'error'`
**When** the badge renders
**Then** it shows an error indicator visually distinct from warning

**Given** a source's `status` is `'paused'`
**When** the badge renders
**Then** it shows a paused indicator (e.g., TheirStack when credit cap is hit)

**Given** `npm run lint`
**When** run
**Then** zero ESLint errors including no unescaped JSX entities

---

## Epic 3: Raw Ingest & Deduplication

Every raw job payload is stored before processing, enabling debugging and replay when upstream APIs change. Duplicate jobs appearing across multiple sources are merged into single canonical records. Source attribution (which sources a job appeared in) is visible in the job detail panel.

### Story 3.1: Raw Ingest Store and URL Dedup Service

As a user of Applyr,
I want every raw job payload stored before normalization with URL-based deduplication at ingest,
So that syncs are idempotent and I can debug or replay payloads if upstream APIs change format.

**Acceptance Criteria:**

**Given** the server starts after this story is merged
**When** the migration runner applies `002_add_job_ingest_raw.sql`
**Then** a `job_ingest_raw` table exists with columns: `id TEXT PRIMARY KEY`, `source_id TEXT`, `fetched_at TEXT`, `external_job_id TEXT`, `payload_json TEXT`, `payload_hash TEXT`, `http_status INTEGER`, `request_url TEXT`

**Given** `server/services/ingestDedup.ts` exports `checkUrlExists(url: string): string | null`
**When** called with a URL already present in `job_ingest_raw`
**Then** returns the existing `external_job_id` — no insert performed

**Given** `checkUrlExists` is called with a URL not yet in `job_ingest_raw`
**When** called
**Then** returns `null` — signaling the caller to proceed with insert

**Given** a connector's `fetchJobs()` result is processed
**When** each job URL is checked before inserting to `job_ingest_raw`
**Then** duplicate URLs (same URL seen in a previous sync) are skipped — no duplicate rows inserted

**Given** a sync runs twice with identical job payloads
**When** the second run completes
**Then** `job_ingest_raw` row count for those jobs is unchanged (idempotent — NFR-5)

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

---

### Story 3.2: Job Clusters, Source Links, and Cross-Source Dedup Service

As a user of Applyr,
I want duplicate jobs appearing across multiple sources merged into single canonical records with source attribution tracked,
So that the same role doesn't clutter the job list just because it was posted on multiple platforms.

**Acceptance Criteria:**

**Given** the migration runner applies `003_add_job_clusters.sql` and `004_add_job_source_links.sql`
**When** the server starts
**Then** a `job_clusters` table exists with columns `id TEXT PRIMARY KEY`, `canonical_job_id TEXT`, `created_at TEXT`
**And** a `job_source_links` table exists with columns `id TEXT PRIMARY KEY`, `cluster_id TEXT`, `source_id TEXT`, `external_job_id TEXT`, `raw_ingest_id TEXT`

**Given** `server/services/clusterDedup.ts` exports `runClusterDedup()`
**When** called after all connectors complete
**Then** it processes `job_ingest_raw` entries, identifies duplicates using URL normalization and Company+Title matching (preserving existing logic from scout_local.ts), and writes cluster and source link records

**Given** two raw ingest records from different sources represent the same job (same normalized URL or same Company+Title)
**When** `runClusterDedup()` runs
**Then** both records are linked to the same `job_clusters` row via `job_source_links`
**And** a single canonical `jobs` record represents the role

**Given** `runClusterDedup()` is called on ingest records already clustered
**When** it runs again
**Then** no duplicate cluster or source link records are created (idempotent)

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

---

### Story 3.3: Canonical Job Presentation and Source Attribution

As a user of Applyr,
I want the job list to show one entry per role and the job detail panel to show which sources that role appeared in,
So that I'm not reviewing duplicates and I can see how broadly a role is posted.

**Acceptance Criteria:**

**Given** multiple source links exist for the same canonical job
**When** the jobs list API responds
**Then** only one record per canonical job appears — no duplicate entries for the same role

**Given** `JobDetailPanel.tsx` renders a job that has source links
**When** the job detail is opened
**Then** a source attribution section shows which sources the job was found in (e.g., "Found on: Greenhouse, LinkedIn")

**Given** `GET /api/jobs/:id` (or the underlying job query)
**When** the response is constructed
**Then** it includes a `sources` array with the contributing source names drawn from `job_source_links` joined to `sources`

**Given** `GET /api/sources` or the run metrics
**When** queried
**Then** per-source counts of unique vs. duplicate job contributions are available (FR-306)

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors including no unescaped JSX entities

---

## Epic 4: Scoring Transparency

Every surfaced job shows a detailed score breakdown in the job detail panel — role-family match, domain fit, seniority, work arrangement, and more. Priority tiers automatically route jobs to the right queue. Scoring levers are validated against expected behavior and regression-tested.

### Story 4.1: Job Scores Table and Score Write Pattern

As a developer,
I want a `job_scores` table with a safe 2-step `is_latest` write pattern in place,
So that the scoring pipeline can store full score history and the UI can reliably query the current score for any job.

**Acceptance Criteria:**

**Given** the migration runner applies `005_add_job_scores.sql`
**When** the server starts
**Then** a `job_scores` table exists with columns: `id TEXT PRIMARY KEY`, `job_id TEXT`, `score_total INTEGER`, `score_breakdown_json TEXT`, `reason_summary TEXT`, `review_state TEXT`, `scored_at TEXT`, `is_latest INTEGER DEFAULT 0`
**And** an index `idx_job_scores_job_id` exists on `job_id`

**Given** a new score row is written for a `job_id` that already has existing rows
**When** the write executes
**Then** it runs as a single transaction: first sets `is_latest = 0` on all existing rows for that `job_id`, then inserts the new row with `is_latest = 1`

**Given** a query runs `SELECT * FROM job_scores WHERE job_id = ? AND is_latest = 1`
**When** executed
**Then** it returns exactly one row — the most recent score for that job

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

---

### Story 4.2: Score Breakdown in Job Detail Panel

As a user of Applyr,
I want to see a detailed score breakdown for any surfaced job in the job detail panel,
So that I understand exactly why a job passed or was scored the way it was without any pipeline debugging.

**Acceptance Criteria:**

**Given** `JobDetailPanel.tsx` is updated to display score data
**When** a job detail is opened for a job with a `job_scores` record where `is_latest = 1`
**Then** the panel shows the total score and a breakdown of component scores: role-family match, domain match, seniority match, work arrangement, company desirability, location compatibility, and compensation signal

**Given** a job detail is opened for a job with no `job_scores` record
**When** the panel renders
**Then** the score section shows a "Not yet scored" state rather than an error

**Given** the job query that powers `JobDetailPanel.tsx`
**When** the response is constructed
**Then** it joins `job_scores WHERE is_latest = 1` and includes `score_total`, `score_breakdown_json`, and `reason_summary` in the response

**Given** `npm run lint`
**When** run
**Then** zero ESLint errors including no unescaped JSX entities

---

### Story 4.3: Score Bands and Lever Validation

As a user of Applyr,
I want jobs automatically routed to the correct priority tier and the existing scoring levers validated against their documented behavior,
So that high-priority roles surface immediately and I can trust the scoring gates are working as configured.

**Acceptance Criteria:**

**Given** the scoring pipeline processes a job with `score_total` of 85 or above
**When** `batch_pipeline.py` completes scoring
**Then** the job is routed to the high-priority tier and the appropriate `review_state` is set in `job_scores`

**Given** scores in the ranges 70–84, 50–69, and below 50
**When** scoring completes
**Then** jobs are routed to review queue, low-priority backlog, and hidden respectively

**Given** the existing scoring levers (title blocklist, industry blocklist, salary threshold, min fit score, location gate) are audited against `batch_pipeline.py`
**When** lever behavior is compared to documented expectations in the PRD
**Then** any mismatch between configured lever and actual gate behavior is identified and corrected in `batch_pipeline.py`

**Given** lever corrections are applied
**When** representative PM-positive and non-PM test cases run
**Then** all PM-positive cases pass all gates and all non-PM cases are correctly rejected

---

### Story 4.4: Scoring Test Coverage

As a developer,
I want unit tests covering the deterministic scoring gates and scoring thresholds,
So that future changes to `batch_pipeline.py` or gate configuration cannot silently regress scoring behavior.

**Acceptance Criteria:**

**Given** test files are added in `tests/unit/` targeting the deterministic gate logic
**When** tests run for the title blocklist gate
**Then** a set of known-blocked titles (e.g., "Software Engineer", "Sales Manager") are asserted to be rejected
**And** a set of known-passing titles (e.g., "Senior Product Manager", "Group PM") are asserted to pass

**Given** tests for the salary gate
**When** run
**Then** jobs below the configured salary threshold are rejected and jobs above pass

**Given** tests for the location gate
**When** run
**Then** non-US / non-remote jobs are rejected and US-remote jobs pass

**Given** tests for scoring thresholds
**When** representative PM-fit and non-PM-fit job fixtures run through the scoring pipeline
**Then** PM-fit jobs score at or above the configured `min_fit_score` and non-PM jobs score below it

**Given** `npm run test:vitest`
**When** run
**Then** all new tests pass with no failures

---

## Epic 5: Live Pipeline Observability

During any sync run, users see real-time per-source metrics (fetched / filtered / passed), live health badge updates, and stage-by-stage handoff counts — all in the existing Sync Activity UI. A post-run summary is written to the activity log after each sync.

### Story 5.1: Typed SSE Event Emission in Connector Orchestrator

As a user of Applyr,
I want the connector orchestrator to emit real-time typed SSE events during a sync run,
So that per-source progress, stage handoffs, and errors are visible the moment they occur.

**Acceptance Criteria:**

**Given** a sync run starts and a connector completes
**When** the orchestrator finishes each connector
**Then** it emits `{ type: 'source_progress', source: string, fetched: number, filtered: number, passed: number }` via the existing SSE channel in `server/routes/pipeline.ts`

**Given** the pipeline transitions between stages (Scout → Backfill → Scrape → Evaluate)
**When** each stage boundary is crossed
**Then** the orchestrator emits `{ type: 'stage_handoff', from: string, to: string, total_passed: number }`

**Given** a connector fails during a run
**When** the error is caught
**Then** the orchestrator emits `{ type: 'connector_error', source: string, error: string, http_status?: number }`
**And** also updates `sources` table health fields (3-step error rule: catch → write sources → emit SSE)

**Given** a source's health state changes to warning or error during a run
**When** the state change occurs
**Then** the orchestrator emits `{ type: 'source_health', source: string, status: 'active' | 'warning' | 'error' }`

**Given** all connectors complete
**When** the run finishes
**Then** the orchestrator emits `{ type: 'run_complete', total_fetched: number, total_passed: number, sources_warned: string[] }`
**And** writes a summary entry to `activity_log` with per-source counts and the list of warned/errored sources

**Given** all SSE events are emitted
**When** inspected
**Then** every event uses a typed envelope (discriminated `type` field) — never a free-form string

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

---

### Story 5.2: Live Metrics and Health Badges in Sync Activity UI

As a user of Applyr,
I want the Sync Activity UI to update in real time during a sync run,
So that I can see per-source progress, live health badge changes, and stage-by-stage handoff counts without refreshing the page.

**Acceptance Criteria:**

**Given** `SyncActivityView.tsx` subscribes to the SSE endpoint during an active sync
**When** a `source_progress` event arrives
**Then** the per-source counts (fetched / filtered / passed) for that source update in real-time without a page reload

**Given** a `stage_handoff` event arrives
**When** it is received by the SSE consumer
**Then** the stage progress indicator updates to reflect the current active stage and the total jobs passed so far

**Given** a `source_health` event arrives with `status: 'warning'` or `status: 'error'`
**When** it is received
**Then** the health badge for that source updates immediately to the new state (live update, not just on page load)

**Given** a `connector_error` event arrives
**When** it is received
**Then** the affected source's badge reflects the error state and the error message is surfaced in the UI

**Given** a `run_complete` event arrives
**When** it is received
**Then** the SSE connection closes cleanly and the UI shows a final summary of the run (total fetched, total passed, sources warned)

**Given** `npm run lint`
**When** run
**Then** zero ESLint errors including no unescaped JSX entities
