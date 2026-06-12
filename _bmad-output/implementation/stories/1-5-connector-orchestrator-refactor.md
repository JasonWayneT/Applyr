---
status: review
baseline_commit: '1862c96c9002b7d4fc45afa24059be15b222f82c'
---

# Story 1.5: Connector Orchestrator Refactor and Legacy Cleanup

As a user of Applyr,
I want the sync pipeline to invoke all connectors through the clean `packages/connectors/` modules,
So that `scout_local.ts` is eliminated and connector behavior is fully modular and transparent.

## Acceptance Criteria

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

## Tasks/Subtasks

- [x] Task 1: Create `server/services/scoutOrchestrator.ts`
  - [x] Import all 12 connector factories from `packages/connectors/`
  - [x] `buildDefaultConnectors()` — wires `checkCrawlPolicy` into builtin and levelsfyi via `policyChecker`; loads Adzuna credentials from env / profiles table
  - [x] `runConnectorOrchestration(connectors?: JobConnector[]): Promise<void>` — iterates connectors, calls `fetchJobs()` + `normalize()`, inserts into `jobs` table via `INSERT OR IGNORE`
  - [x] Per-connector try/catch: on error, calls `logActivity('ERROR', source, message)` and continues
  - [x] Logs `INFO` before each connector and after completion summary

- [x] Task 2: Modify `server/scout.ts`
  - [x] Add `import { runConnectorOrchestration } from './services/scoutOrchestrator.js'`
  - [x] Replace Stage 1 subprocess spawn block with `await runConnectorOrchestration()`
  - [x] Remove the output-handler callbacks that parsed `[LOG]`, `[FOUND]`, `[ACTION]`, `[REJECT]` prefixes

- [x] Task 3: Delete `scripts/scout_local.ts`

- [x] Task 4: Write `tests/unit/scoutOrchestrator.test.ts`
  - [x] Mock `server/db.js` (db + logActivity) and `server/middleware/crawlPolicy.js`
  - [x] Test: all provided connectors are invoked
  - [x] Test: error in one connector does not block remaining connectors
  - [x] Test: `logActivity('ERROR', source, ...)` is called when connector throws
  - [x] Test: INFO entries logged per connector run

- [x] Task 5: Verify all gates pass
  - [x] `npm run test:vitest` — 197/197 tests pass (192 prior + 5 new)
  - [x] `npm run lint` — 0 errors (28 pre-existing warnings)
  - [x] `npx tsc --noEmit` — 0 errors

## Dev Notes

### Crawl policy wiring
`checkCrawlPolicy(domain)` from `server/middleware/crawlPolicy.ts` uses the module-level `db` singleton (synchronous better-sqlite3). Pass it as `policyChecker` when constructing the builtin and levelsfyi connectors:
```typescript
createBuiltInConnector({ policyChecker: checkCrawlPolicy })
createLevelsFyiConnector({ policyChecker: checkCrawlPolicy })
```
The connectors call `policyChecker(domain)` before any Playwright action — the logActivity call inside `checkCrawlPolicy` creates the activity log entry the AC requires.

### Adzuna credentials
Load from `process.env.ADZUNA_APP_ID` / `ADZUNA_APP_KEY` first; fall back to `profiles` table key `api_connections` (same pattern as the original `loadApiConnections` in `scout_local.ts`).

### Insert pattern
Use `INSERT OR IGNORE INTO jobs` to silently skip URL-duplicate rows. Determine status based on description length (≥ 200 chars → `'Drafted'`, otherwise `'New'`).

### Stage 1 output handlers removed
The `[LOG]`, `[FOUND]`, `[ACTION]`, `[REJECT]` prefix parsing was a bridge for subprocess stdout. With direct invocation, connectors surface errors via thrown exceptions, not stdout. Remove the output handler entirely.

### buildTsxSpawn still needed
Stages 2–4 (backfill, requeue, scrape, evaluate) still use `buildTsxSpawn`. Keep the import; only the Stage 1 spawn block is removed.
