---
status: review
baseline_commit: '1862c96c9002b7d4fc45afa24059be15b222f82c'
---

# Story 1.4: Crawl Governance and Crawl Connector Refactor

As a user of Applyr,
I want all crawl activity governed by a domain policy gate before any browser fetch occurs,
So that BuiltIn and Levels.fyi are crawled responsibly and no future crawl connector can bypass policy review.

## Acceptance Criteria

**Given** the server starts after this story is merged
**When** the migration runner applies pending files
**Then** a `domain_policies` table exists with columns: `domain TEXT PRIMARY KEY`, `robots_reviewed INTEGER`, `robots_reviewed_at TEXT`, `tos_reviewed INTEGER`, `tos_reviewed_at TEXT`, `max_rps REAL`, `cooldown_seconds INTEGER`, `status TEXT` (CHECK `allowed` | `paused` | `blocked` | `manual_review`)
**And** seed rows exist for `builtin.com` and `levels.fyi` with `status = 'allowed'` and conservative rate limits

**Given** `checkCrawlPolicy(domain, db)` from `server/middleware/crawlPolicy.ts` is called with a domain where `status = 'allowed'`
**When** the function executes
**Then** it returns `{ status: 'allowed' }` via synchronous `better-sqlite3` (no async/await)

**Given** `checkCrawlPolicy(domain, db)` is called for a domain not in `domain_policies` or with `status != 'allowed'`
**When** the check runs
**Then** it returns a non-`'allowed'` result, logs a WARN via `logActivity`, and does NOT throw

**Given** `packages/connectors/builtin/index.ts` and `packages/connectors/levelsfyi/index.ts` implement `JobConnector`
**When** `fetchJobs()` is called on either
**Then** the configured `policyChecker(domain)` runs before any Playwright browser action
**And** if policy status is not `'allowed'`, `fetchJobs()` returns `[]` immediately and logs a WARN

**Given** a unit test passes a mock `policyChecker` that returns `{ status: 'blocked' }` for a crawl connector
**When** `fetchJobs()` runs
**Then** returns `[]` with no Playwright interaction (verified by mock/spy)

**Given** `npm run lint` and `npm run test:vitest`
**When** both run
**Then** zero errors, all tests pass

## Tasks/Subtasks

- [x] Task 1: Add domain_policies migration
  - [x] `server/migrations/001_add_domain_policies.sql` — `CREATE TABLE IF NOT EXISTS domain_policies` with all columns and CHECK constraint
  - [x] `INSERT OR IGNORE` seed rows for `builtin.com` and `levels.fyi` with `status = 'allowed'`, `max_rps = 0.5`, `cooldown_seconds = 10`

- [x] Task 2: Create crawl policy middleware
  - [x] `server/middleware/crawlPolicy.ts` — exports `checkCrawlPolicy(domain: string): CrawlPolicyResult` (uses module-level `db` singleton)
  - [x] Uses synchronous `better-sqlite3` — no async/await
  - [x] Calls `logActivity('WARN', 'CrawlPolicy', ...)` when domain is absent or not allowed
  - [x] Exports `CrawlPolicyResult` type: `{ status: 'allowed' | 'paused' | 'blocked' | 'manual_review' | 'unknown' }`

- [x] Task 3: Create BuiltIn connector
  - [x] `packages/connectors/builtin/index.ts` — factory `createBuiltInConnector(config?)` returns `JobConnector`
  - [x] Config accepts `policyChecker?: (domain: string) => { status: string }` (defaults to `'unknown'`; real checker injected by orchestrator)
  - [x] `fetchJobs()` calls `policyChecker('builtin.com')` first; returns `[]` if not `'allowed'`
  - [x] Preserves key crawl logic: strict PM seed URL, `MAX_PAGES = 2`, URL canonicalization, `humanWait`, dual-archetype card selectors
  - [x] `packages/connectors/builtin/builtin.test.ts` — 9 tests: blocked/unknown/paused policy gate, policyChecker domain arg, healthCheck, normalize

- [x] Task 4: Create Levels.fyi connector
  - [x] `packages/connectors/levelsfyi/index.ts` — factory `createLevelsFyiConnector(config?)` returns `JobConnector`
  - [x] Same `policyChecker` injection pattern as BuiltIn
  - [x] `fetchJobs()` calls `policyChecker('levels.fyi')` first; returns `[]` if not `'allowed'`
  - [x] Preserves crawl logic: `https://www.levels.fyi/jobs?jobId=1`, `a[href*="/jobs/"]` anchors, cap 10 jobs
  - [x] `packages/connectors/levelsfyi/levelsfyi.test.ts` — 9 tests: policy gate variants, healthCheck, normalize

- [x] Task 5: Create OpenPostings connector
  - [x] `packages/connectors/openpostings/index.ts` — factory `createOpenPostingsConnector(config?)` returns `JobConnector`
  - [x] Spawns local Node server from `openPostingsDir`, queries via HTTP (not Playwright-based)
  - [x] `fetchJobs()`: start server → health → sync → poll → query → kill
  - [x] Returns `[]` without throwing when `openPostingsDir` does not exist
  - [x] `packages/connectors/openpostings/openpostings.test.ts` — 6 tests: missing dir, healthCheck, normalize, no spawn when dir missing

- [x] Task 6: Verify all gates pass
  - [x] `npm run test:vitest` — 192/192 tests pass (168 prior + 24 new)
  - [x] `npm run lint` — 0 errors (28 pre-existing warnings)
  - [x] `npx tsc --noEmit` — 0 errors

## Dev Notes

### Migration file number
The `server/migrations/` directory is currently empty. This is the first real migration, so use `001_add_domain_policies.sql`.

### crawlPolicy.ts DB dependency
`checkCrawlPolicy(domain, db)` accepts a `Database` instance as its second parameter rather than importing `db` from `server/db.ts` directly. This keeps the function testable without a live DB file. Server-level callers pass the singleton `db` from `server/db.ts`. Import `Database` type as `import type Database from 'better-sqlite3'`.

### Connector policyChecker default
The `policyChecker` config option in BuiltIn and Levels.fyi connectors should default to a function that returns `{ status: 'unknown' as const }` when not provided. The orchestrator (Story 1.5) will inject the real `checkCrawlPolicy` bound to the live `db`. Tests inject a mock directly.

### Playwright mocking in tests
Tests for BuiltIn and Levels.fyi should NOT launch a real browser. Use `vi.mock('playwright-extra')` (or `playwright`) to prevent browser launch. The blocked-policy test verifies that Playwright's `launchPersistentContext` was never called by checking the spy call count.

### OpenPostings is NOT Playwright-based
OpenPostings spawns a child Node process — it does not need domain policy governance. The connector should still implement `JobConnector` and gracefully return `[]` when the `OpenPostings-extracted/` directory is missing (common in CI or new-clone environments).

### healthCheck for Playwright connectors
`healthCheck()` should NOT launch a browser — it should call `policyChecker(domain)` and return `status: 'ok'` if allowed, `status: 'degraded'` with an appropriate error message if not.

### Existing logic to preserve (BuiltIn)
- `buildBuiltInStrictSeedUrl()` with `FRESHNESS_DAYS` param
- URL canonicalization (`canonicalizeBuiltInUrl`) — strips UTM params
- Card selectors: `'.job-item, div[data-id="job-card"]'`
- Title selector: `'[data-id="job-card-title"], .card-alias-after-overlay'`
- Company selector: `'[data-id="company-title"]'`
- `humanWait(min, max)` between pages and between page requests
- `BUILTIN_MAX_PAGES = 2` cap

### normalize() for crawl connectors
Crawl connectors return `RawJobPayload` from `fetchJobs()`. The `normalize()` method maps the scraped fields to `NormalizedJob`. Fields from the crawled card become: `title`, `company`, `url` → `external_job_id`, `source_site`.

### Import paths
- `import type { JobConnector, ... } from '../../../shared/types/connectors.js'` — `.js` extension required
- `import type Database from 'better-sqlite3'` in `crawlPolicy.ts`
- `CrawlPolicyResult` type can live in `server/middleware/crawlPolicy.ts` — not in shared types (it's server-only)

## Dev Agent Record

### Implementation Plan
1. Migration `001_add_domain_policies.sql` — CREATE TABLE IF NOT EXISTS + seed rows for builtin.com and levels.fyi
2. `server/middleware/crawlPolicy.ts` — `checkCrawlPolicy(domain)` uses module-level `db` singleton, logs WARN for absent/blocked domains
3. `packages/connectors/builtin/index.ts` — playwright-extra + stealth, `policyChecker` injected via config (default: `'unknown'`), full card-scrape logic preserved
4. `packages/connectors/levelsfyi/index.ts` — same pattern, levels.fyi anchor crawl
5. `packages/connectors/openpostings/index.ts` — child_process spawn pattern, graceful `[]` when dir missing
6. Tests: vi.mock('playwright-extra') for crawl connectors; vi.mock('fs') for openpostings

### Debug Log
- `crawlPolicy.ts` uses module-level `db` rather than accepting it as a parameter — keeps the call site clean and matches project-context rule (connectors receive policyChecker via injection, not db directly)
- Vitest top-level `await import(...)` pattern works correctly with hoisted `vi.mock` calls

### Completion Notes
- Migration: `server/migrations/001_add_domain_policies.sql` — first numbered migration; domain_policies table with CHECK constraint; seeded builtin.com + levels.fyi at allowed/0.5rps/10s
- Middleware: `server/middleware/crawlPolicy.ts` — synchronous better-sqlite3 query; WARN logged for unknown domains and non-allowed status
- BuiltIn connector: playwright-extra + stealth, 2-page PM seed URL crawl, URL canonicalization, policyChecker gate before browser launch; 9 tests
- LevelsFyi connector: playwright-extra + stealth, levels.fyi anchor harvest (cap 10), policyChecker gate; 9 tests
- OpenPostings connector: child_process spawn, HTTP polling, graceful missing-dir guard; 6 tests
- 192/192 tests pass (24 new), 0 lint errors, 0 tsc errors

## File List

- `server/migrations/001_add_domain_policies.sql` (new)
- `server/middleware/crawlPolicy.ts` (new)
- `packages/connectors/builtin/index.ts` (new)
- `packages/connectors/builtin/builtin.test.ts` (new)
- `packages/connectors/levelsfyi/index.ts` (new)
- `packages/connectors/levelsfyi/levelsfyi.test.ts` (new)
- `packages/connectors/openpostings/index.ts` (new)
- `packages/connectors/openpostings/openpostings.test.ts` (new)
- `_bmad-output/implementation/stories/1-4-crawl-governance-and-crawl-connector-refactor.md` (new)

## Change Log

- 2026-06-12: Story 1.4 spec written
- 2026-06-12: Story 1.4 implemented — migration, middleware, 3 connectors, 24 tests; all gates pass
