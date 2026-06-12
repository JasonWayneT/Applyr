---
status: review
baseline_commit: ''
---

# Story 1.3: Refactor Remaining API Connectors — Batch 2

As a developer implementing the Applyr expansion,
I want the remaining non-crawl API connectors (workingnomads, jobscollider, adzuna) extracted into `packages/connectors/{name}/index.ts` implementing `JobConnector`,
So that all non-crawl sources are consistently structured before the orchestrator refactor in Story 1.5.

## Acceptance Criteria

**Given** `packages/connectors/{name}/index.ts` exists for each of the 3 connectors
**When** imported
**Then** a factory function is exported that returns an object satisfying `JobConnector` from `shared/types/connectors.js`

**Given** `workingnomads.fetchJobs()` is called
**When** the API returns a mixed-category payload
**Then** only records whose `category_name` contains `product` or `management` are included

**Given** `adzuna.fetchJobs()` is called when `appId` or `appKey` is empty
**When** invoked
**Then** an empty array is returned without making any HTTP requests

**Given** `connector.fetchJobs(since)` is called with an ISO date string
**When** the API returns jobs older than `since`
**Then** those stale jobs are excluded

**Given** `connector.normalize(rawPayload)` is called
**When** `raw_data` contains source-specific fields
**Then** a valid `NormalizedJob` is returned with all required fields populated

**Given** `connector.healthCheck()` is called
**When** the upstream API responds with HTTP 200
**Then** `ConnectorHealth` with `status: 'ok'` is returned

**Given** `npm run lint` and `npx tsc --noEmit` run
**When** both complete
**Then** zero errors

## Tasks/Subtasks

- [x] Task 1: Create workingnomads connector
  - [x] `packages/connectors/workingnomads/index.ts` — implements JobConnector
  - [x] `packages/connectors/workingnomads/workingnomads.test.ts` — vitest unit tests
- [x] Task 2: Create jobscollider connector
  - [x] `packages/connectors/jobscollider/index.ts`
  - [x] `packages/connectors/jobscollider/jobscollider.test.ts`
- [x] Task 3: Create adzuna connector
  - [x] `packages/connectors/adzuna/index.ts`
  - [x] `packages/connectors/adzuna/adzuna.test.ts`
- [x] Task 4: Verify all tests pass and zero lint/tsc errors

## Dev Notes

- Import: `import type { JobConnector, ... } from '../../../shared/types/connectors.js'` — `.js` extension required
- Factory pattern: matches Story 1.2 — `createXxxConnector(config?)` returns a `JobConnector` object literal
- Inline test fixtures, co-located tests — matches Story 1.2 (no `fixtures/` subdirectory)
- Working Nomads: pulls all jobs from one endpoint, filters client-side by `category_name`; use URL as `external_job_id` (no stable ID field in response)
- JobsCollider: RSS feed (`https://remotefirstjobs.com/remote-product-jobs.rss`); title format is `"Job Title at Company Name"` — split on last `" at "`; use URL as `external_job_id`
- Adzuna: requires `appId` and `appKey` in config; return `[]` from `fetchJobs` if either is missing; use `max_days_old` query param when `since` is provided (more efficient than post-filtering); enforce `maxCallsPerRun` cap with 3s gap between calls

## Dev Agent Record

### Implementation Plan
Create 3 connector packages following Story 1.2 patterns. Verify 0 lint errors, 0 tsc errors, all tests pass.

### Debug Log
_empty_

### Completion Notes
- 3 connectors created: `workingnomads` (JSON, client-side category filter), `jobscollider` (RSS, "Title at Company" format), `adzuna` (paid API, credentials-optional, rate-limited)
- 27 new tests across 3 test files (8–9 per connector); 168/168 total tests pass
- Adzuna `callGapMs` config param added (default 3000) so tests can pass `callGapMs: 0` to avoid real sleeps; test suite runs in ~1.5s
- Working Nomads and JobsCollider use URL as `external_job_id` (no stable ID in responses)
- 0 lint errors, 0 tsc errors

## File List

- `packages/connectors/workingnomads/index.ts` (new)
- `packages/connectors/workingnomads/workingnomads.test.ts` (new)
- `packages/connectors/jobscollider/index.ts` (new)
- `packages/connectors/jobscollider/jobscollider.test.ts` (new)
- `packages/connectors/adzuna/index.ts` (new)
- `packages/connectors/adzuna/adzuna.test.ts` (new)
- `_bmad-output/implementation/stories/1-3-remaining-api-connectors.md` (new)

## Change Log

- 2026-06-11: Story 1.3 started
