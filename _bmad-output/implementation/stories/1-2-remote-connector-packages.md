---
status: review
baseline_commit: ''
---

# Story 1.2: Remote-First API Connector Packages

As a developer implementing the Applyr expansion,
I want the 6 remote-first API connectors (remotive, remoteok, weworkremotely, himalayas, themuse, jobicy) extracted into `packages/connectors/{name}/index.ts` implementing `JobConnector`,
So that each connector is independently testable, typed, and ready for wiring into the Phase 4 pipeline.

## Acceptance Criteria

**Given** `packages/connectors/{name}/index.ts` exists for each of the 6 connectors
**When** imported from any file inside the repo
**Then** a factory function is exported that returns an object satisfying the `JobConnector` interface from `shared/types/connectors.js`

**Given** `connector.fetchJobs()` is called with no argument
**When** the upstream API responds with a valid payload
**Then** the returned array contains `RawJobPayload` objects with `external_job_id`, `url`, `source_id`, and `raw_data` populated

**Given** `connector.fetchJobs(since)` is called with an ISO date string
**When** the API returns jobs older than `since`
**Then** those stale jobs are excluded from the returned array

**Given** `connector.normalize(rawPayload)` is called
**When** `raw_data` contains the source-specific API fields
**Then** a valid `NormalizedJob` is returned with all required fields populated

**Given** `connector.healthCheck()` is called
**When** the upstream API responds with HTTP 200
**Then** `ConnectorHealth` with `status: 'ok'` is returned

**Given** `connector.healthCheck()` is called
**When** fetch throws a network error
**Then** `ConnectorHealth` with `status: 'error'` and an `error` string is returned

**Given** `npm run lint` and `npx tsc --noEmit` run
**When** both complete
**Then** zero errors

## Tasks/Subtasks

- [x] Task 1: Create remotive connector
  - [x] `packages/connectors/remotive/index.ts` — implements JobConnector
  - [x] `packages/connectors/remotive/remotive.test.ts` — vitest unit tests with fixtures
- [x] Task 2: Create remoteok connector
  - [x] `packages/connectors/remoteok/index.ts`
  - [x] `packages/connectors/remoteok/remoteok.test.ts`
- [x] Task 3: Create weworkremotely connector
  - [x] `packages/connectors/weworkremotely/index.ts`
  - [x] `packages/connectors/weworkremotely/weworkremotely.test.ts`
- [x] Task 4: Create himalayas connector
  - [x] `packages/connectors/himalayas/index.ts`
  - [x] `packages/connectors/himalayas/himalayas.test.ts`
- [x] Task 5: Create themuse connector
  - [x] `packages/connectors/themuse/index.ts`
  - [x] `packages/connectors/themuse/themuse.test.ts`
- [x] Task 6: Create jobicy connector
  - [x] `packages/connectors/jobicy/index.ts`
  - [x] `packages/connectors/jobicy/jobicy.test.ts`
- [x] Task 7: Update package.json lint script
  - [x] Add `packages` to `eslint src server shared packages`
- [x] Task 8: Verify all tests pass and zero lint/tsc errors

## Dev Notes

- Import: `import type { JobConnector, ... } from '../../../shared/types/connectors.js'` — `.js` extension required
- Factory pattern: each file exports `createXxxConnector(config?)` returning a `JobConnector`; config holds `searchTerms` for search-driven sources
- `fetchJobs(since?: string)`: ISO date string; skip API records where the date field is before `since`; include items with null/missing dates
- `normalize(raw)`: maps `raw.raw_data` fields to `NormalizedJob`; strip HTML from description fields; return `undefined` for empty/missing optional fields
- WWR (We Work Remotely): RSS-based; use URL as `external_job_id`; extract XML fields with regex (same pattern as `scripts/scout_local.ts`)
- RemoteOK: first element of the API response array is a legal notice — skip records missing `id` or `position`
- Tests mock `globalThis.fetch` via `vi.stubGlobal`; fixtures are inline objects/strings at top of each test file
- `packages` is already in tsconfig `include` and vitest config (added in Story 1.1)
- ESLint `no-explicit-any: warn` — use `unknown` with explicit casts, not `any`

## Dev Agent Record

### Implementation Plan
Create `packages/connectors/` with 6 subdirectories. Each exports a factory function returning a `JobConnector` object literal. Update package.json lint script. Verify zero lint/tsc errors.

### Debug Log
_empty_

### Completion Notes
- 6 connectors created as factory functions in `packages/connectors/{name}/index.ts`, each implementing `JobConnector`
- 45 tests across 6 test files (7–8 tests per connector): fetchJobs shape, since-filtering, dedup, normalize field mapping, healthCheck ok/degraded/error
- The Muse connector tests pagination stop-early behavior (empty page 1 → 1 fetch call)
- WWR connector (RSS-based) uses URL as `external_job_id`; XML parsed with regex matching scout_local.ts pattern
- `package.json` lint script updated: `eslint src server shared packages`
- `npm run lint` (0 errors, 28 pre-existing warnings in server/src), `npx tsc --noEmit` (0 errors), 141/141 tests pass, 0 regressions

## File List

- `packages/connectors/remotive/index.ts` (new)
- `packages/connectors/remotive/remotive.test.ts` (new)
- `packages/connectors/remoteok/index.ts` (new)
- `packages/connectors/remoteok/remoteok.test.ts` (new)
- `packages/connectors/weworkremotely/index.ts` (new)
- `packages/connectors/weworkremotely/weworkremotely.test.ts` (new)
- `packages/connectors/himalayas/index.ts` (new)
- `packages/connectors/himalayas/himalayas.test.ts` (new)
- `packages/connectors/themuse/index.ts` (new)
- `packages/connectors/themuse/themuse.test.ts` (new)
- `packages/connectors/jobicy/index.ts` (new)
- `packages/connectors/jobicy/jobicy.test.ts` (new)
- `package.json` (updated — lint script adds `packages`)
- `_bmad-output/implementation/stories/1-2-remote-connector-packages.md` (new)

## Change Log

- 2026-06-11: Story 1.2 started
