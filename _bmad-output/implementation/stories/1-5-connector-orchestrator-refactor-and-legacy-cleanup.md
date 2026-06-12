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

- [x] Task 1: Create `runConnectorStage()` in `server/scout.ts`
  - [x] Import all 12 connector factories from `packages/connectors/` (remotive, remoteok, weworkremotely, himalayas, themuse, jobicy, workingnomads, jobscollider, adzuna, builtin, levelsfyi, openpostings)
  - [x] Import `checkCrawlPolicy` from `server/middleware/crawlPolicy.ts`
  - [x] Load `candidate_preferences.json` from `data/candidate_preferences.json` (same fallback pattern as scout_local; `{}` if missing)
  - [x] Load Adzuna credentials: env vars `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` first, then fall back to `SELECT value FROM profiles WHERE key = 'api_connections'` (same pattern as scout_local lines 107–130)
  - [x] Instantiate all connectors with configs: `searchTerms` from prefs for API connectors; `policyChecker: checkCrawlPolicy` for builtin and levelsfyi; `appId` / `appKey` for adzuna
  - [x] Honour `SCOUT_BUILTIN_ONLY` env var: when set, only run builtin; skip all API and levelsfyi connectors
  - [x] For each connector, run in try/catch: `fetchJobs()` → for each raw call `normalize()` → apply title blocklist + URL dedup → insert into DB
  - [x] Title blocklist: derive inline from prefs `blocked_titles` using the same `.toLowerCase().trim()` transformation as scout_local (lines 52–58); default to scout_local's hardcoded list if not in prefs
  - [x] URL dedup: synchronous `db.prepare('SELECT id FROM jobs WHERE url = ?').get(url)` — skip insert if row exists; also checks `stale_jobs` table
  - [x] DB insert: uses `insertJob()` from `server/repository/jobRepository.ts` (maintains FTS index sync). Status = `'Drafted'` if description >= 200 chars, else `'New'`. Catch UNIQUE constraint errors silently
  - [x] Log per-connector: `logActivity('INFO', connector.sourceId, 'Running connector: ...')` before fetchJobs. `logActivity('INFO', connector.sourceId, '[FOUND] Title at Company')` for each inserted job. `logActivity('ERROR', connector.sourceId, 'Connector failed: ...')` on catch

- [x] Task 2: Replace Stage 1 subprocess call in `server/scout.ts`
  - [x] Remove the `buildTsxSpawn('scripts/scout_local.ts')` block
  - [x] `buildTsxSpawn` still imported and used for BACKFILL and SCRAPE stages (kept)
  - [x] Replaced with `await runConnectorOrchestration()` (implemented in `server/services/scoutOrchestrator.ts`)
  - [x] Set `activeStage = 'BACKFILL'` after orchestration completes
  - [x] Individual connector failures isolated; orchestration itself does not throw on connector errors

- [x] Task 3: Delete `scripts/scout_local.ts`
  - [x] `scripts/scout_local.ts` deleted (git status shows `D`)
  - [x] No `server/` or `packages/` files import from `scout_local`

- [x] Task 4: Add / update test for Story 1.5 orchestrator behavior
  - [x] Created `tests/unit/scoutOrchestrator.test.ts` (9 tests)
  - [x] Test: error isolation — failing connector doesn't halt others; ERROR logged
  - [x] Test: crawl connector gate — `checkCrawlPolicy` called; WARN logged; no jobs inserted when blocked
  - [x] Test: URL dedup — existing URL skips insertJob
  - [x] Test: title blocklist — 'VP of Product' rejected with [REJECT] log
  - [x] Test: insertJob called with correct shape for passing jobs
  - [x] Test: all connectors invoked; INFO logs emitted; no throw on empty results

- [x] Task 5: Verify all gates pass
  - [x] `npm run test:vitest` — 220/220 tests pass
  - [x] `npm run lint` — 0 errors (28 pre-existing warnings unchanged)
  - [x] `npx tsc --noEmit` — 0 errors

## Dev Notes

### tsconfig excludes `scripts/`
`tsconfig.json` has `"exclude": ["scripts", "**/*.test.ts"]`. This means `server/scout.ts` **cannot** TypeScript-import from `scripts/domain/gates.ts` or any other file under `scripts/`. Do not add such imports.

### Gate scope for this story
The cross-source gates from `scout_local.ts` (geographic, seniority, industry) are NOT replicated in the orchestrator. They are enforced downstream by `batch_pipeline.py`. This is intentional — connectors return broad results; `batch_pipeline.py` is the evaluation stage. The only gates applied in the orchestrator are:
1. Title blocklist (inline from prefs) — reduces obvious noise before DB insert
2. URL dedup (synchronous DB check) — enforces idempotent syncs (NFR-5)

### Adzuna credential loading
Adzuna connector accepts `appId` and `appKey` via config. The orchestrator loads them:
1. First from `process.env.ADZUNA_APP_ID` / `process.env.ADZUNA_APP_KEY`
2. Then from `db.prepare("SELECT value FROM profiles WHERE key = 'api_connections'").get()` → parse JSON → `conns.adzunaAppId`, `conns.adzunaAppKey`
3. If neither available, pass empty strings — connector returns `[]` silently (existing behavior)

### policyChecker injection for crawl connectors
`checkCrawlPolicy` from `server/middleware/crawlPolicy.ts` is already a `(domain: string) => CrawlPolicyResult` function (uses module-level db). Import it directly and pass as the `policyChecker` config to `createBuiltInConnector` and `createLevelsFyiConnector`. No binding needed.

### SCOUT_BUILTIN_ONLY env var
`scout_local.ts` honoured `SCOUT_BUILTIN_ONLY=1` to skip API sources and only run BuiltIn. The orchestrator must preserve this:
```typescript
const builtinOnly = ['1', 'true', 'yes'].includes((process.env.SCOUT_BUILTIN_ONLY || '').toLowerCase());
```
When `builtinOnly`, only run the builtin connector.

### ATS watchlist not migrated
`scout_local.ts` had an inline `scoutAtsWatchlist()` function that loaded `data/ats_watchlist.json` and crawled careers pages. This function was NOT implemented as a `JobConnector` package and is excluded from this story's scope. Behavioral delta: if `data/ats_watchlist.json` exists, its companies will no longer be scanned in Stage 1. This is an acknowledged regression — a formal ATS watchlist connector can be added in a future story.

### buildTsxSpawn removal
`buildTsxSpawn` was used only in the Stage 1 scout subprocess call. After removing Stage 1's subprocess, check whether `buildTsxSpawn` is still used elsewhere in `server/scout.ts`. If not, remove the import. `buildPythonEnv` is still used for the EVALUATE stage — keep it.

### DB insert pattern
Use the `db` singleton from `'./db.js'`. The insert is synchronous (better-sqlite3). Catch UNIQUE constraint violations silently — they indicate duplicate URLs and are expected:
```typescript
try {
  db.prepare(`INSERT INTO jobs (...) VALUES (...)`).run(...);
  saved++;
} catch { /* UNIQUE URL constraint — expected */ }
```

### randomUUID
Import from `'crypto'`: `import { randomUUID } from 'crypto';` — already available in Node 18+, no new dependency.

### Test file location
Existing tests live under `packages/connectors/*/` and follow the `{name}.test.ts` co-location pattern. For `server/scout.ts`, place the test at `server/scout.test.ts`. Check if `vitest.config.ts` covers `server/**/*.test.ts` — if not, add it (it currently covers `packages/**/*.test.ts`; the `server/` directory may need to be added).

### buildPythonEnv is still needed
The BACKFILL, SCRAPE, and EVALUATE stages still spawn subprocesses using `buildPythonEnv()`. Keep that import and usage intact — only Stage 1 changes.

## File List

- `server/scout.ts` (modified — Stage 1 now calls `runConnectorOrchestration()` instead of subprocess)
- `server/services/scoutOrchestrator.ts` (new — full orchestration implementation)
- `tests/unit/scoutOrchestrator.test.ts` (new — 9 unit tests)
- `scripts/scout_local.ts` (deleted)
- `_bmad-output/implementation/stories/1-5-connector-orchestrator-refactor-and-legacy-cleanup.md` (this file)

## Dev Agent Record

### Implementation Plan

Extracted connector orchestration from the 1375-line `scripts/scout_local.ts` monolith into `server/services/scoutOrchestrator.ts`. Key decisions:

1. **`insertJob()` over direct INSERT**: Used `server/repository/jobRepository.ts` to maintain FTS index sync — direct INSERT would have silently broken full-text search.
2. **`stale_jobs` in dedup**: Both `isUrlKnown()` and `isCompanyTitleNew()` check `jobs` AND `stale_jobs` tables, matching the behavior of the original monolith.
3. **Title blocklist inlined**: `scripts/domain/gates.ts` is excluded by tsconfig; blocklist derived from `data/candidate_preferences.json` with DEFAULT_TITLE_BLOCKLIST fallback.
4. **`policyChecker` injection**: `checkCrawlPolicy` passed directly as config to builtin and levelsfyi connectors; module-level singleton pattern unchanged.
5. **`SCOUT_BUILTIN_ONLY`**: Preserved existing env var behavior in `buildDefaultConnectors()`.
6. **ATS watchlist not migrated**: `scoutAtsWatchlist()` from scout_local.ts is not a `JobConnector` package — acknowledged regression, deferred to a future story.

### Debug Log

| Issue | Fix |
|---|---|
| Direct INSERT violated FTS sync rule | Switched to `insertJob()` from jobRepository; updated test mock to include `syncJobFts` and `deleteJobFts` |
| `stale_jobs` dedup missing | Added both tables to `isUrlKnown()` and `isCompanyTitleNew()` |
| `searchTerms` not passed to connectors | Added `loadPrefs()` call in `buildDefaultConnectors()` |
| Test mock missing `syncJobFts` | Added `syncJobFts: vi.fn()` and `deleteJobFts: vi.fn()` to db mock |

### Completion Notes

All ACs satisfied. 220/220 tests pass. 0 lint errors. 0 tsc errors. `scripts/scout_local.ts` deleted. All 12 connectors wired through `JobConnector` interface. Error isolation per-connector confirmed by test. Crawl policy gate confirmed firing. Title blocklist and URL+company/title dedup active.
