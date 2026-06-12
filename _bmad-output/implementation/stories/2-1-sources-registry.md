---
status: review
baseline_commit: '1862c96c9002b7d4fc45afa24059be15b222f82c'
---

# Story 2.1: Sources Registry, API, and Existing Connector Health Wiring

As a user of Applyr,
I want all job sources tracked in a central registry with health state,
So that I have a single view of every source, its current status, and its sync history.

## Acceptance Criteria

**Given** the server starts after this story is merged
**When** the migration runner applies `003_add_sources.sql`
**Then** a `sources` table exists with columns: `id TEXT PRIMARY KEY`, `name TEXT`, `type TEXT` (ats_api | vendor_api | crawl), `provider TEXT`, `base_url TEXT`, `auth_details TEXT`, `poll_frequency_hours INTEGER`, `status TEXT` (active | warning | error | paused), `last_success_at TEXT`, `last_error_at TEXT`, `consecutive_failures INTEGER DEFAULT 0`, `credits_used_this_month INTEGER DEFAULT 0`, `credits_reset_at TEXT`
**And** seed rows exist for all 12 existing connectors with `status = 'active'`

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

## Tasks/Subtasks

- [x] Task 1: Migration `server/migrations/003_add_sources.sql`
  - [x] `CREATE TABLE IF NOT EXISTS sources` with all columns and CHECK constraint on `type` and `status`
  - [x] `INSERT OR IGNORE` seed rows for all 12 existing connectors with `status = 'active'`, `consecutive_failures = 0`

- [x] Task 2: Sources routes `server/routes/sources.ts`
  - [x] `GET /api/sources` — `SELECT * FROM sources ORDER BY name`, returns flat array
  - [x] `POST /api/sources/:id/sync` — looks up source, finds matching connector from `buildDefaultConnectors()`, runs `runConnectorOrchestration([connector])` async (fire-and-forget), returns `{ id, started: true }`
  - [x] 404 if source id not found in sources table

- [x] Task 3: Register sources router in `server/index.ts`

- [x] Task 4: Wire health updates in `server/services/scoutOrchestrator.ts`
  - [x] On success: `UPDATE sources SET last_success_at = ?, consecutive_failures = 0, status = 'active' WHERE id = ?`
  - [x] On failure: `UPDATE sources SET last_error_at = ?, consecutive_failures = consecutive_failures + 1, status = CASE WHEN consecutive_failures + 1 >= 3 THEN 'error' ELSE 'warning' END WHERE id = ?`
  - [x] Updates are best-effort — missing source row (UPDATE affects 0 rows) is silently ignored

- [x] Task 5: Verify all gates pass
  - [x] `npm run lint` — 0 errors (28 pre-existing warnings)
  - [x] `npx tsc --noEmit` — 0 errors
  - [x] `npm run test:vitest` — 206/206 tests pass (no regression)

## Dev Notes

### Migration number
`001_add_domain_policies.sql` and `002_add_job_ingest_raw.sql` already exist. Sources is `003_add_sources.sql`.

### Seed row ids
Use the connector `sourceId` value as the `sources.id` — this is what the orchestrator uses to match the health update. IDs: `remotive`, `remoteok`, `weworkremotely`, `himalayas`, `themuse`, `jobicy`, `workingnomads`, `jobscollider`, `adzuna`, `openpostings`, `builtin`, `levelsfyi`.

### Type values
- `crawl`: builtin, levelsfyi
- `vendor_api`: all others (remotive, remoteok, weworkremotely, himalayas, themuse, jobicy, workingnomads, jobscollider, adzuna, openpostings)

### POST /api/sources/:id/sync — fire and forget
`void runConnectorOrchestration([connector])` — do not await. The response returns immediately with `{ id, started: true }`. No pipeline lock check needed for single-source sync.

### Health update SQL uses SQL expression for consecutive_failures
`CASE WHEN consecutive_failures + 1 >= 3 THEN 'error' ELSE 'warning' END` — at the time of UPDATE, `consecutive_failures` is the current (pre-increment) value, so `+ 1` gives the new value.
