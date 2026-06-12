---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
lastStep: 8
status: 'complete'
completedAt: '2026-06-11'
inputDocuments:
  - docs/product-brief.md
  - docs/spec/04-design-specs/DESIGN-002-pipeline-architecture.md
  - docs/spec/05-change-requests/CR-006-llm-provider-architecture.md
  - _bmad-output/planning-artifacts/prds/prd-Applyr-2026-06-11/prd.md
workflowType: 'architecture'
project_name: 'Applyr'
user_name: 'Jason'
date: '2026-06-11'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

---

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
26 FRs across 6 clusters. The connector abstraction (Cluster 2) is the structural prerequisite — FR-201 defines the `JobConnector` interface that all 16 connectors must implement. Every downstream cluster (observability instrumentation, deduplication routing, health reporting, crawl governance) depends on connectors being isolated modules with a known shape. Cluster 5 (observability) has an explicit hard dependency on Cluster 2 completion.

**Non-Functional Requirements:**
- Schema migrations must be idempotent and non-destructive — 7 new tables added to a live SQLite database with existing job data
- Local-first — no data leaves the machine across all new connectors
- TheirStack hard cap — 200 API credits/month enforced in code via filtered queries
- Connector isolation — one failure cannot cascade
- Idempotent syncs — running twice produces the same result
- API compliance — rate limits and ToS respected for all Lane 1 sources

**Scale & Complexity:**
- Complexity level: **Medium** — single user, local SQLite, no auth, no multi-tenancy, no cloud infrastructure
- Primary domain: Full-stack local tool (TypeScript backend + Python pipeline + React frontend)
- Real-time: SSE already in use, extending scope to per-source metrics
- External integrations: 5 new APIs (Greenhouse, Lever, Ashby, Workable, TheirStack)

### Technical Constraints & Dependencies

- **SQLite only** — no external database, no queue system (BullMQ/Redis explicitly out of scope)
- **Python for scoring** — `batch_pipeline.py` is preserved; TypeScript owns discovery and persistence only
- **Existing Express API preserved** — additions only, no framework swap
- **better-sqlite3** — synchronous SQLite driver; all DB writes are blocking by design
- **SSE for real-time** — not WebSockets; existing SSE mechanism extended, not replaced
- **React UI preserved** — component additions only, no redesign
- **Session-sized implementation chunks** — all phases must have clear handoff points for context window continuity

### Cross-Cutting Concerns Identified

| Concern | Components Touched |
|---------|-------------------|
| Schema migration safety | All 7 new tables — must be idempotent ADD operations |
| JobConnector contract | All 16 connectors (12 refactored + 4 new) |
| Source health state machine | sources table → SSE event bus → SyncActivityView |
| Crawl policy gate | domain_policies table → crawl connectors (must fire before fetch) |
| Deduplication routing | Raw ingest → job_clusters → job_source_links → canonical jobs |
| SSE event shape | Connectors → Express routes → React SyncActivityView |
| TypeScript / Python boundary | Connector layer (TS) hands off to batch_pipeline.py (Python) — boundary must not blur |

---

## Foundation Assessment (Brownfield Expansion)

### Existing Stack Confirmed as Foundation

| Layer | Current | Expansion Status |
|-------|---------|-----------------|
| Backend runtime | Node.js 18+ / TypeScript + Express | Carry forward — no change |
| Frontend | React 19 + Vite + Tailwind | Carry forward — additions only |
| Database driver | better-sqlite3 (WAL, FTS5) | Carry forward — 7 new tables via idempotent migrations |
| Script runner | tsx 4.x | Carry forward — connectors are TypeScript |
| Browser automation | Playwright 1.59 | Carry forward — used by crawl connectors |
| Scoring pipeline | Python + Gemini/Claude/Ollama | Carry forward — boundary preserved |
| Test runner | Vitest | Carry forward — connector unit tests added here |

### Net-New Dependencies

**None.** All 6 clusters are implemented within the existing technology choices:
- ATS and vendor connectors use native `fetch` (Node 18 built-in)
- Crawl policy engine is pure TypeScript logic against SQLite
- SSE extension uses existing Express SSE mechanism
- Deduplication layer uses better-sqlite3 (already installed)

This is a structural refactor + schema addition + new connector modules — no new runtime dependencies required.

---

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Schema migration strategy — must be established before any table is added
- JobConnector interface location — all 16 connectors depend on this contract
- Connector module location — determines import paths across the whole codebase
- TypeScript/Python boundary — must be explicit before connector refactor begins

**Important Decisions (Shape Architecture):**
- Deduplication timing — hybrid approach touches both ingest and post-processing layers
- SSE event shape — typed envelopes must be defined before UI work begins
- job_scores shape — 1:many affects query patterns throughout scoring layer
- Crawl policy placement — middleware pattern affects connector orchestration design

**Deferred (Post-MVP):**
- Full monorepo tooling (Turborepo/Nx) — `packages/connectors/` structure adopted without formal monorepo tooling for now

---

### Data Architecture

**Schema Migration Strategy**
- **Decision:** Version table + numbered migration files
- **Rationale:** More traceable than bare try/catch ADD COLUMN; explicit version state makes it easy to reason about what has and hasn't run on a given install
- **Implementation:** Add a `schema_migrations` table tracking migration ID + applied timestamp; migration files named `001_add_sources.sql`, `002_add_job_ingest_raw.sql`, etc.; run on server startup in order, skip already-applied
- **Affects:** server/db.ts, all 7 new tables

**job_scores Shape**
- **Decision:** 1:many with `is_latest` flag
- **Rationale:** Preserves score history across rescore runs; enables before/after comparison when lever validation (FR-403) is done; `is_latest = true` is the query path for normal UI rendering
- **Schema:** `job_scores(id, job_id, score_total, score_breakdown_json, reason_summary, review_state, scored_at, is_latest)`
- **Affects:** FR-401, FR-402, FR-403, FR-404

**TheirStack Credit Enforcement**
- **Decision:** In-connector guard reading running count from `sources` table
- **Rationale:** Enforcement co-located with the code that consumes credits; no new table needed; logged as a warning when cap is approached or hit
- **Implementation:** `sources` table gains `credits_used_this_month` and `credits_reset_at` fields; TheirStack connector checks before each fetch and aborts with a structured log entry if cap would be exceeded
- **Affects:** FR-105, sources table schema

---

### Connector Architecture

**Connector Module Location**
- **Decision:** `packages/connectors/`
- **Rationale:** Formal package boundary signals production-quality intent; importable cleanly from both server orchestration and test harness; positions for future monorepo tooling without requiring it now
- **Structure:** `packages/connectors/{greenhouse,lever,ashby,workable,theirstack,builtin,levelsfyi,remotive,remoteok,weworkremotely,himalayas,themuse,jobicy,workingnomads,jobscollider,adzuna}/index.ts`
- **Affects:** FR-201 through FR-204, all 16 connectors

**Shared Types Location**
- **Decision:** `shared/types/connectors.ts`
- **Rationale:** Repo-root shared layer importable by `packages/connectors/`, `server/`, and test files without circular dependencies; clean separation from server domain logic
- **Types defined here:** `JobConnector`, `RawJobPayload`, `NormalizedJob`, `ConnectorHealth`, `SourceStatus`, `SSEEvent`
- **Affects:** FR-201, all connectors, server orchestration layer

**Deduplication Timing**
- **Decision:** Hybrid — URL dedup at ingest, full cross-source dedup post-ingest pass
- **Rationale:** URL dedup at ingest prevents obvious duplicates from entering `job_ingest_raw`; full cross-source dedup (Company+Title normalization, vector similarity, cluster assignment) runs as a dedicated pass after all connectors complete, operating on the full picture
- **Two services:** `ingestDedup` (inline, fast) + `clusterDedup` (post-run, operates on `job_ingest_raw`)
- **Affects:** FR-301 through FR-306

**Crawl Policy Placement**
- **Decision:** Middleware layer above connectors
- **Rationale:** Crawl connectors stay focused on fetching; policy enforcement is a separate concern; impossible to accidentally invoke a crawl connector without policy check firing; orchestrator calls `checkCrawlPolicy(domain)` before invoking any connector with `source_type = 'crawl'`
- **Implementation:** `server/middleware/crawlPolicy.ts` — reads `domain_policies` table, returns allow/block/backoff decision
- **Affects:** FR-601, FR-602, FR-603

---

### API & Communication Patterns

**SSE Event Shape**
- **Decision:** Typed event envelopes with discriminated `type` field
- **Rationale:** UI switches on `type` to update the correct part of SyncActivityView; forward-compatible — new event types can be added without breaking existing handlers
- **Event types defined:**
  ```ts
  { type: 'source_progress', source: string, fetched: number, filtered: number, passed: number }
  { type: 'stage_handoff', from: string, to: string, total_passed: number }
  { type: 'source_health', source: string, status: 'active' | 'warning' | 'error' }
  { type: 'connector_error', source: string, error: string, http_status?: number }
  { type: 'run_complete', total_fetched: number, total_passed: number, sources_warned: string[] }
  ```
- **Affects:** FR-501 through FR-505, SyncActivityView

**Error Surfacing**
- **Decision:** Both — SSE real-time event during run + write to `activity_log` for history
- **Rationale:** Real-time visibility during active sync (SSE); permanent record for post-run diagnosis (activity_log); the two complement each other
- **Affects:** FR-106, FR-107, FR-505

---

### Operational Concerns

**Source Health State Updates**
- **Decision:** Each connector writes directly to `sources` table after completing its run
- **Rationale:** No separate health service needed at current scale; health state is owned by the connector that knows whether it succeeded; orchestrator reads `sources.status` before deciding whether to invoke a connector on the next run
- **Fields updated per run:** `last_success_at`, `last_error_at`, `consecutive_failures`, `status`, `credits_used_this_month` (TheirStack only)
- **Affects:** FR-101, FR-106, FR-107

**TypeScript / Python Boundary**
- **Decision:** SQLite `jobs` table is the explicit handoff — TypeScript writes `status = 'New'`, Python reads and processes
- **Rationale:** No direct TS→Python calls in the connector layer; existing `processRunner.ts` subprocess spawn pattern handles pipeline orchestration; boundary is enforced by the DB, not by calling convention
- **Affects:** All clusters — this boundary must not be crossed during connector refactor

---

### Decision Impact on Implementation Sequence

```
1. shared/types/connectors.ts         ← defines contracts everything else imports
2. Schema migrations (version table)  ← 7 new tables before any code uses them
3. packages/connectors/ structure     ← package skeleton before connector code
4. JobConnector interface (FR-201)    ← in shared/types, implements the contract
5. Refactor 12 existing connectors    ← migrate into packages/connectors/
6. domain_policies seed + middleware  ← gate crawl connectors before new ones added
7. 5 new connectors                   ← Greenhouse, Lever, Ashby, Workable, TheirStack
8. Hybrid dedup services              ← ingestDedup + clusterDedup
9. job_scores + scoring calibration   ← parallel to connectors work
10. SSE typed events + UI updates     ← after connector seams exist
```

---

## Implementation Patterns & Consistency Rules

### Naming Patterns

**Database (SQLite) — `snake_case` everywhere:**
- Tables: `sources`, `job_ingest_raw`, `job_scores` ✓ — never `Sources`, never `jobScores`
- Columns: `source_id`, `fetched_at`, `is_latest` ✓ — never `sourceId`, never `isLatest`
- Indexes: `idx_{table}_{column}` — e.g. `idx_jobs_status`, `idx_job_scores_job_id`

**TypeScript — `camelCase` variables/functions, `PascalCase` types/interfaces/classes:**
- Interface: `JobConnector`, `RawJobPayload`, `NormalizedJob`, `ConnectorHealth`
- Function: `fetchJobs()`, `checkDomainPolicy()`, `runClusterDedup()`
- File names: `camelCase.ts` — e.g. `greenhouseConnector.ts`, `crawlPolicy.ts`

**API endpoints — `kebab-case` plural nouns (existing pattern):**
- New endpoints: `/api/sources`, `/api/sources/:id/sync`, `/api/domain-policies`

---

### Structure Patterns

**Connector module shape:**
```
packages/connectors/
  {name}/
    index.ts          ← implements JobConnector interface
    {name}.test.ts    ← unit tests co-located
    fixtures/         ← example raw payloads for testing
```

**Shared types:** `shared/types/connectors.ts` — single file, no barrel re-exports from nested folders.

**Migrations:** `server/migrations/{NNN}_{description}.sql` — idempotent (`CREATE TABLE IF NOT EXISTS`). Migration runner in `server/db.ts` checks `schema_migrations` table before applying each file in order.

**Tests:** Co-located with connector/domain logic (`{name}.test.ts` alongside `{name}.ts`). Integration tests in `tests/` root.

---

### Format Patterns

**API responses — direct JSON, no wrapper envelope:**
```ts
// ✓ correct
res.json({ id: job.id, title: job.title })
// ✗ wrong
res.json({ data: { id: job.id }, error: null })
```

**API errors:** `{ error: string, code?: string }` with appropriate HTTP status code.

**Dates:** ISO 8601 strings everywhere — `2026-06-11T14:30:00Z`. Never Unix timestamps.

**JSON field naming:** `camelCase` in TypeScript objects, `snake_case` in SQLite. Explicit mapping at the repository layer — SQLite column names never leak directly into API responses.

---

### Communication Patterns

**SSE events — always typed event envelopes, never free-form strings:**
```ts
// ✓ correct
emit({ type: 'source_progress', source: 'greenhouse', fetched: 14, filtered: 3, passed: 11 })
// ✗ wrong
emit(`greenhouse: 14 fetched, 3 filtered, 11 passed`)
```

**Activity log:** Always include `level` (INFO/WARN/ERROR), `source` (connector or service name), `message` (human-readable), `meta` (structured JSON). Never `console.log` in production paths.

---

### Process Patterns

**Connector error handling — 3-step rule:**
1. Catch the error in the connector
2. Write to `sources` table: `last_error_at`, increment `consecutive_failures`, update `status`
3. Emit `{ type: 'connector_error', source, error, http_status? }` SSE event

**Crawl policy — always check before fetch:**
```ts
// ✓ correct — orchestrator checks before invoking crawl connector
const policy = await checkCrawlPolicy(domain)
if (policy.status !== 'allowed') return
await connector.fetchJobs()
```

**Idempotent ingest — URL dedup before insert:**
Every `fetchJobs()` checks URL existence in `job_ingest_raw` before inserting. Returns existing `external_job_id` if already present. Never inserts duplicates.

**TypeScript/Python boundary — never cross it:**
- TypeScript writes `status = 'New'` to `jobs` table; Python reads and processes
- TypeScript never calls Python functions directly from connector layer
- Python never writes to: `sources`, `domain_policies`, `job_ingest_raw`, `job_clusters`, `job_source_links`
- Shared surfaces: `jobs`, `job_scores`, `job_tags`, `activity_log` only

---

### Enforcement — All Implementation Agents MUST:

- Use `snake_case` for all SQLite identifiers
- Import `JobConnector` from `shared/types/connectors.ts` — never redefine it locally
- Run crawl policy check before any domain fetch
- Use typed SSE event envelopes — never free-form strings for structured data
- Write connector errors to both `sources` table and SSE stream
- Check URL existence before inserting to `job_ingest_raw`
- Apply schema changes via the migration runner — never bare `CREATE TABLE` calls in application code
- Respect the TypeScript/Python boundary — the `jobs` table is the handoff point

---

## Project Structure & Boundaries

### Complete Project Directory Structure

Existing files marked `(existing)`. New additions are unmarked. Files marked `← UPDATED` receive additions only.

```
Applyr/
├── index.html                                      (existing)
├── package.json                                    (existing — no new runtime deps)
├── tsconfig.json                                   (existing)
├── vite.config.mts                                 (existing)
├── vitest.config.ts                                (existing)
├── tailwind.config.mjs                             (existing)
├── requirements.txt                                (existing)
│
├── shared/                                         ← NEW
│   └── types/
│       └── connectors.ts          JobConnector, RawJobPayload, NormalizedJob,
│                                  ConnectorHealth, SourceStatus, SSEEvent (FR-201)
│
├── packages/                                       ← NEW
│   └── connectors/
│       ├── greenhouse/
│       │   ├── index.ts           implements JobConnector (FR-102, FR-203)
│       │   ├── greenhouse.test.ts (FR-204)
│       │   └── fixtures/job-sample.json
│       ├── lever/
│       │   ├── index.ts           (FR-103, FR-203)
│       │   ├── lever.test.ts
│       │   └── fixtures/
│       ├── ashby/
│       │   ├── index.ts           (FR-104, FR-203)
│       │   ├── ashby.test.ts
│       │   └── fixtures/
│       ├── workable/
│       │   ├── index.ts           (FR-108, FR-203)
│       │   ├── workable.test.ts
│       │   └── fixtures/
│       ├── theirstack/
│       │   ├── index.ts           credit-guarded (FR-105, FR-203)
│       │   ├── theirstack.test.ts
│       │   └── fixtures/
│       ├── builtin/               refactored crawl connector (FR-202, FR-603)
│       │   ├── index.ts
│       │   ├── builtin.test.ts
│       │   └── fixtures/
│       ├── levelsfyi/             refactored crawl connector (FR-202, FR-603)
│       │   ├── index.ts
│       │   ├── levelsfyi.test.ts
│       │   └── fixtures/
│       ├── remotive/index.ts      refactored (FR-202)
│       ├── remoteok/index.ts      refactored (FR-202)
│       ├── weworkremotely/index.ts
│       ├── himalayas/index.ts
│       ├── themuse/index.ts
│       ├── jobicy/index.ts
│       ├── workingnomads/index.ts
│       ├── jobscollider/index.ts
│       └── adzuna/index.ts
│
├── server/
│   ├── index.ts                                    (existing)
│   ├── db.ts                  ← UPDATED: add migration runner (7 new tables)
│   ├── middleware.ts                               (existing)
│   ├── pipelineLock.ts                             (existing)
│   ├── shared.ts                                   (existing)
│   ├── submissionFolders.ts                        (existing)
│   │
│   ├── migrations/                                 ← NEW
│   │   ├── 001_add_sources.sql                     (FR-101, FR-106)
│   │   ├── 002_add_job_ingest_raw.sql              (FR-301)
│   │   ├── 003_add_job_clusters.sql                (FR-302)
│   │   ├── 004_add_job_source_links.sql            (FR-303)
│   │   ├── 005_add_job_scores.sql                  (FR-401)
│   │   ├── 006_add_domain_policies.sql             (FR-601)
│   │   └── 007_add_schema_migrations.sql           (version table)
│   │
│   ├── middleware/                                 ← NEW
│   │   └── crawlPolicy.ts     gate before any crawl fetch (FR-602)
│   │
│   ├── services/                                   ← NEW
│   │   ├── ingestDedup.ts     URL dedup at ingest (FR-304)
│   │   └── clusterDedup.ts    cross-source cluster dedup post-ingest (FR-304)
│   │
│   ├── pipeline/
│   │   └── processRunner.ts                        (existing — TS→Python boundary)
│   │
│   ├── repository/
│   │   ├── jobRepository.ts                        (existing)
│   │   ├── jobSearchPrefs.ts                       (existing)
│   │   ├── jobStatus.ts                            (existing)
│   │   └── paths.ts                                (existing)
│   │
│   └── routes/
│       ├── jobs/                                   (existing)
│       ├── pipeline.ts                             (existing)
│       ├── profile.ts                              (existing)
│       ├── system.ts                               (existing)
│       ├── sources.ts         ← NEW: GET/POST /api/sources (FR-101, FR-106, FR-107)
│       └── domainPolicies.ts  ← NEW: GET/PATCH /api/domain-policies (FR-601)
│
├── scripts/
│   ├── scout_local.ts         ← DELETED after Cluster 2 refactor completes (FR-202)
│   ├── batch_pipeline.py                           (existing — Python boundary preserved)
│   └── ...                                         (all other scripts unchanged)
│
├── src/
│   ├── App.tsx                                     (existing)
│   ├── main.tsx                                    (existing)
│   │
│   ├── components/
│   │   ├── JobDetailPanel.tsx ← UPDATED: score breakdown section (FR-402)
│   │   └── ...                                     (all other components unchanged)
│   │
│   ├── pages/
│   │   ├── SyncActivityView.tsx ← UPDATED: live per-source metrics + health badges (FR-502–504)
│   │   └── ...                                     (all other pages unchanged)
│   │
│   ├── lib/                                        (existing, unchanged)
│   └── types/                                      (existing, unchanged)
│
└── tests/
    ├── fixtures/                                   (existing)
    ├── unit/                  ← UPDATED: scoring gate tests (FR-404)
    ├── sse.ts                                      (existing)
    └── sse.test.ts                                 (existing)
```

---

### Architectural Boundaries

**API Boundaries — New Endpoints:**

| Endpoint | Method | File | FRs |
|---|---|---|---|
| `/api/sources` | GET | `server/routes/sources.ts` | FR-101, FR-106 |
| `/api/sources/:id/sync` | POST | `server/routes/sources.ts` | FR-101, FR-107 |
| `/api/domain-policies` | GET | `server/routes/domainPolicies.ts` | FR-601 |
| `/api/domain-policies/:id` | PATCH | `server/routes/domainPolicies.ts` | FR-602 |

All existing endpoints (`/api/jobs`, `/api/pipeline`, `/api/profile`, `/api/system`) preserved unchanged.

**Component Boundaries:**

- React → Express: all via `src/lib/apiClient.ts` — no direct DB access from frontend
- SSE channel: `SyncActivityView.tsx` subscribes to existing SSE endpoint; typed envelopes emitted by `server/scout.ts` during sync runs
- Score display: `JobDetailPanel.tsx` fetches score breakdown from job record — no new endpoint needed, data joined at query layer

**Data Boundaries:**

| Territory | Tables |
|---|---|
| TypeScript owns (read + write) | `sources`, `domain_policies`, `job_ingest_raw`, `job_clusters`, `job_source_links` |
| Handoff surface (TS writes `status='New'`, Python reads) | `jobs` |
| Shared (both layers can write) | `job_scores`, `job_tags`, `activity_log` |
| Python-only — TypeScript must never write | Scoring logic in `batch_pipeline.py` |

**Service Boundaries:**

| Service | File | Responsibility |
|---|---|---|
| Connector orchestrator | `server/scout.ts` (refactored) | Runs 16 connectors in sequence; emits SSE |
| Crawl policy gate | `server/middleware/crawlPolicy.ts` | allow/block/backoff before any domain fetch |
| URL dedup | `server/services/ingestDedup.ts` | Checks URL before inserting to `job_ingest_raw` |
| Cluster dedup | `server/services/clusterDedup.ts` | Cross-source cluster assignment post-ingest |
| Migration runner | `server/db.ts` | Applies `server/migrations/*.sql` at startup |
| Python pipeline | `scripts/batch_pipeline.py` | Scores `status='New'` jobs; writes `job_scores` |

---

### Requirements to Structure Mapping

**Cluster 1 — Source Expansion:**

| FR | File |
|---|---|
| FR-101 — Source Registry | `server/migrations/001_add_sources.sql` + `server/routes/sources.ts` |
| FR-102–104, FR-108 — ATS connectors | `packages/connectors/{greenhouse,lever,ashby,workable}/index.ts` |
| FR-105 — TheirStack | `packages/connectors/theirstack/index.ts` |
| FR-106 — Source health | `server/routes/sources.ts` + `src/pages/SyncActivityView.tsx` |
| FR-107 — Graceful failure | All `packages/connectors/*/index.ts` (error → `sources` table + SSE) |

**Cluster 2 — Connector Architecture:**

| FR | File |
|---|---|
| FR-201 — Interface | `shared/types/connectors.ts` |
| FR-202 — Refactor 12 existing | `packages/connectors/{remotive,remoteok,weworkremotely,himalayas,themuse,jobicy,workingnomads,jobscollider,adzuna,builtin,levelsfyi,…}/index.ts` |
| FR-203 — New 5 to interface | `packages/connectors/{greenhouse,lever,ashby,workable,theirstack}/index.ts` |
| FR-204 — Testability | `packages/connectors/*/{name}.test.ts` + `fixtures/` |

**Cluster 3 — Ingest & Dedup:**

| FR | File |
|---|---|
| FR-301 — Raw store | `server/migrations/002_add_job_ingest_raw.sql` |
| FR-302 — Clusters | `server/migrations/003_add_job_clusters.sql` |
| FR-303 — Source links | `server/migrations/004_add_job_source_links.sql` |
| FR-304 — Dedup | `server/services/ingestDedup.ts` + `server/services/clusterDedup.ts` |
| FR-305 — Canonical UI | `src/components/JobDetailPanel.tsx` (source attribution) |
| FR-306 — Overlap data | `server/routes/sources.ts` |

**Cluster 4 — Scoring:**

| FR | File |
|---|---|
| FR-401 — job_scores | `server/migrations/005_add_job_scores.sql` |
| FR-402 — Score breakdown | `src/components/JobDetailPanel.tsx` |
| FR-403/405 — Lever + bands | `scripts/batch_pipeline.py` |
| FR-404 — Test coverage | `tests/unit/` |

**Cluster 5 — Observability:**

| FR | File |
|---|---|
| FR-501/503 — SSE metrics + handoffs | `server/scout.ts` + `shared/types/connectors.ts` |
| FR-502/504 — SyncActivityView | `src/pages/SyncActivityView.tsx` |
| FR-505 — Post-run summary | `server/scout.ts` → `activity_log` |

**Cluster 6 — Crawl Governance:**

| FR | File |
|---|---|
| FR-601 — Domain policies | `server/migrations/006_add_domain_policies.sql` + `server/routes/domainPolicies.ts` |
| FR-602 — Policy engine | `server/middleware/crawlPolicy.ts` |
| FR-603 — Existing crawl connectors | `packages/connectors/{builtin,levelsfyi}/index.ts` |

---

### Data Flow

```
connector.fetchJobs()
  → ingestDedup.checkUrl()           skip if URL already in job_ingest_raw
  → job_ingest_raw                   raw store with payload_hash
  → clusterDedup.run()               cluster + link → canonical job
  → jobs (status='New')              TypeScript/Python boundary
  → batch_pipeline.py                reads 'New', scores, writes job_scores
  → job_scores (is_latest=true)      available for UI
  → SyncActivityView                 live via SSE during run
  → JobDetailPanel                   score breakdown on demand
```

---

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
Zero new runtime dependencies — all 6 clusters implement within the existing Node 18 + TypeScript + better-sqlite3 + Playwright + React 19 stack. No version conflicts possible. SSE extension is backward-compatible: existing mechanism is extended with typed envelopes, not replaced. Python boundary is enforced through SQLite — the existing `processRunner.ts` subprocess pattern is untouched. `packages/connectors/` sits outside `server/` and `src/` — importable from both the server orchestrator and test harness without circular dependencies.

**Pattern Consistency:**
Naming conventions align with the existing codebase: `snake_case` in all SQL files, `camelCase/PascalCase` in TypeScript — confirmed consistent with `server/repository/jobRepository.ts` and current schema patterns. All connectors import `JobConnector` from `shared/types/connectors.ts` — the enforcement rule explicitly prohibits local re-definitions, eliminating interface drift. Migration file naming (`NNN_description.sql`) matches the version table strategy decision.

**Structure Alignment:**
`server/middleware/crawlPolicy.ts` sits correctly above connectors in the call chain — orchestrator calls `checkCrawlPolicy(domain)` before invoking any crawl connector. `shared/types/` at the repo root is importable from `packages/connectors/`, `server/`, and `tests/` without circular deps. `server/services/` for dedup is correctly positioned as a post-connector pass, not embedded in individual connector logic.

No contradictions found between any two decisions.

---

### Requirements Coverage Validation ✅

**All 26 FRs are architecturally supported:**

| Cluster | FRs | Status |
|---|---|---|
| Cluster 1 — Source Expansion | FR-101 through FR-108 (8 FRs) | ✅ All covered |
| Cluster 2 — Connector Architecture | FR-201 through FR-204 (4 FRs) | ✅ All covered |
| Cluster 3 — Raw Ingest & Dedup | FR-301 through FR-306 (6 FRs) | ✅ All covered |
| Cluster 4 — Scoring Calibration | FR-401 through FR-405 (5 FRs) | ✅ All covered |
| Cluster 5 — Pipeline Observability | FR-501 through FR-505 (5 FRs) | ✅ All covered (Cluster 2 dependency properly sequenced) |
| Cluster 6 — Crawl Governance | FR-601 through FR-603 (3 FRs) | ✅ All covered |

**All 6 NFRs are architecturally addressed:**

| NFR | How Addressed |
|---|---|
| NFR-1 — Idempotent migrations | Version table + `CREATE TABLE IF NOT EXISTS` in all migration files |
| NFR-2 — Local-first | SQLite-only; no cloud sync or telemetry; all connectors write locally |
| NFR-3 — TheirStack 200 credit cap | In-connector guard reading `credits_used_this_month` from `sources` before each fetch |
| NFR-4 — Connector isolation | Each connector runs independently; errors write to `sources` + SSE without interrupting others |
| NFR-5 — Idempotent syncs | `ingestDedup.checkUrl()` prevents duplicate inserts to `job_ingest_raw` |
| NFR-6 — API compliance | `crawlPolicy.ts` enforces rate limits + ToS gate; each ATS connector respects published rate limits |

---

### Implementation Readiness Validation ✅

**Decision Completeness:** All 8 critical decisions documented with rationale, implementation detail, and affected FRs. Enforcement section gives implementation agents explicit MUST rules.

**Structure Completeness:** Every new file and directory is named and FR-linked. Modified existing files (`server/db.ts`, `server/scout.ts`, `src/components/JobDetailPanel.tsx`, `src/pages/SyncActivityView.tsx`, `scripts/scout_local.ts` deletion) are identified.

**Pattern Completeness:** All five pattern categories (naming, structure, format, communication, process) are specified with examples. The 3-step connector error rule and crawl policy gate are concrete and enforceable.

---

### Gap Analysis Results

**Critical Gaps:** None.

**Important Gaps:**

1. `server/scout.ts` refactor scope — the doc calls it a "thin orchestrator" after Cluster 2, but does not document its current internal structure. Agent beginning the refactor must read `server/scout.ts` first to map existing connector invocations to the new `packages/connectors/` module paths before making changes.

2. **OQ-1 (Ashby auth)** remains open — flagged in the PRD as a pre-implementation dependency. If Ashby requires a private API key rather than public access, `packages/connectors/ashby/index.ts` will need a secrets pattern. Agent must resolve before starting FR-104.

3. **OQ-3 (unit test coverage bar)** remains open. Recommended minimum: happy path + one error case + one URL-dedup case per connector.

**Nice-to-Have Gaps:**

- Rate limit specifics for Lever, Ashby, Workable not documented beyond "respect ToS" — agents look these up at implementation time.
- No `tsconfig.json` path alias for `shared/*` — agents should add `"paths": { "shared/*": ["./shared/*"] }` to avoid deep relative imports.

---

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with rationale
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

---

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High — all FRs and NFRs are covered, no critical gaps, patterns are concrete and enforceable.

**Key Strengths:**
- Zero new runtime dependencies — no version management risk, no new tooling surface
- TypeScript/Python boundary is explicit and enforced at the DB layer — no ambiguity about ownership
- Connector isolation with typed interface — one agent can implement one connector without touching any other
- Enforcement section gives agents unambiguous MUST rules — reduces implementation variance

**Areas for Future Enhancement:**
- Formal monorepo tooling (Turborepo/Nx) when `packages/connectors/` grows beyond current scope
- `tsconfig.json` path aliases for `shared/*` to clean up relative imports
- Per-connector rate limit specifications once confirmed with each ATS provider
