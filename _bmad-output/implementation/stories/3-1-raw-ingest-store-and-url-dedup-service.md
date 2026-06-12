---
status: review
baseline_commit: '1862c96c9002b7d4fc45afa24059be15b222f82c'
---

# Story 3.1: Raw Ingest Store and URL Dedup Service

As a user of Applyr,
I want every raw job payload stored before normalization with URL-based deduplication at ingest,
So that syncs are idempotent and I can debug or replay payloads if upstream APIs change format.

## Acceptance Criteria

**Given** the server starts after this story is merged
**When** the migration runner applies `002_add_job_ingest_raw.sql`
**Then** a `job_ingest_raw` table exists with columns: `id TEXT PRIMARY KEY`, `source_id TEXT`, `fetched_at TEXT`, `external_job_id TEXT`, `payload_json TEXT`, `payload_hash TEXT`, `http_status INTEGER`, `request_url TEXT`

**Given** `server/services/ingestDedup.ts` exports `checkUrlExists(url: string): string | null`
**When** called with a URL already present in `job_ingest_raw`
**Then** returns the existing `external_job_id` — no insert performed

**Given** `checkUrlExists` is called with a URL not yet in `job_ingest_raw`
**When** called
**Then** returns `null` — signaling the caller to proceed with insert

**Given** `server/services/ingestDedup.ts` exports `insertRawPayload(sourceId: string, job: RawJobPayload, httpStatus?: number): string`
**When** called with a new job
**Then** inserts a row into `job_ingest_raw` with a generated UUID `id`, current ISO timestamp `fetched_at`, SHA-256 `payload_hash` of the serialized `raw_data`, and returns the inserted `id`

**Given** a sync runs twice with identical job URLs
**When** the second run calls `checkUrlExists` before inserting
**Then** `job_ingest_raw` row count for those URLs is unchanged — no duplicate rows

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

## Tasks/Subtasks

- [x] Task 1: Add job_ingest_raw migration
  - [x] `server/migrations/002_add_job_ingest_raw.sql` — `CREATE TABLE IF NOT EXISTS job_ingest_raw` with all 8 columns
  - [x] Index on `request_url` for fast dedup lookups: `CREATE INDEX IF NOT EXISTS idx_job_ingest_raw_url ON job_ingest_raw(request_url)`

- [x] Task 2: Create ingestDedup service
  - [x] Create `server/services/` directory
  - [x] `server/services/ingestDedup.ts` — factory pattern `createIngestDedupService(db)` (chosen over module-level singleton to enable test isolation without vi.mock hoisting issues — see Dev Notes)
  - [x] Exports `checkUrlExists(url: string): string | null` — synchronous `better-sqlite3` query on `request_url`; returns `external_job_id` if found, `null` otherwise
  - [x] Exports `insertRawPayload(sourceId: string, job: RawJobPayload, httpStatus?: number): string` — generates `id` via `randomUUID()`, computes SHA-256 `payload_hash` via Node `crypto` module (no new dependencies), inserts row, returns `id`
  - [x] Import `RawJobPayload` from `shared/types/connectors.js` — never redefine locally
  - [x] All DB calls synchronous — no async/await; prepared statements cached on factory creation

- [x] Task 3: Write service tests
  - [x] `tests/unit/ingestDedup.test.ts` — uses an in-memory SQLite DB (`:memory:`) passed to `createIngestDedupService` for isolation
  - [x] Test: `checkUrlExists` returns `null` for a URL not in the table
  - [x] Test: `insertRawPayload` inserts a row and returns a non-empty string id
  - [x] Test: `checkUrlExists` returns the `external_job_id` after a prior insert with the same URL
  - [x] Test: calling `insertRawPayload` twice with the same URL does NOT insert a duplicate (caller checks `checkUrlExists` first — test demonstrates the idempotent pattern)
  - [x] Test: `payload_hash` field is a non-empty hex string (SHA-256 produces 64-char hex)

- [x] Task 4: Verify quality gates
  - [x] `npm run lint` — zero errors on new files (28 pre-existing warnings, unchanged)
  - [x] `npx tsc --noEmit` — zero type errors
  - [x] `npm run test:vitest` — 206/206 tests pass (9 new ingestDedup tests + 197 existing)

## Dev Notes

- **DB singleton pattern:** Import `db` from `../../server/db.js` (same relative path pattern used in `crawlPolicy.ts`). Do NOT accept `db` as a parameter — use the module-level singleton.
- **No new runtime dependencies:** Use Node.js built-in `crypto` (`createHash('sha256')`) for `payload_hash`. Use `crypto.randomUUID()` for `id`.
- **`payload_hash` input:** Hash the `JSON.stringify(job.raw_data)` string — consistent, deterministic.
- **`httpStatus` default:** Default to `200` when caller omits it.
- **Index on `request_url`:** Essential for O(1) dedup checks at scale; add it in the migration.
- **Test isolation:** The test file must create its own in-memory DB and run the `job_ingest_raw` DDL directly — do NOT import the module-level singleton (it would open the real DB file). Pass the test DB through a seam (e.g., exported `_setDb` function for tests, or factory pattern similar to how crawl connectors accept `policyChecker`).

## Dev Agent Record

### Implementation Notes

- **Factory over singleton:** `ingestDedup.ts` exports `createIngestDedupService(db)` rather than module-level bound functions. This avoids `vi.mock` hoisting complexity in tests (Vitest hoists `vi.mock` before variable initialization, so you can't share a `testDb` reference into a mock factory). The factory pattern — already established for crawl connectors — is a clean fit here too. Calling code (future orchestrator in Story 1.5) creates an instance with `import { db } from '../db.js'`.
- **Prepared statements cached:** Both `checkStmt` and `insertStmt` are prepared once at factory creation, not per call. This is an intentional optimization for the hot sync path.
- **Test location:** `tests/unit/ingestDedup.test.ts` — follows the `migrationRunner.test.ts` co-location convention under `tests/unit/`, not `server/services/` (vitest.config.ts includes `tests/**` not `server/**`).
- **Type annotation on prepared statements:** Used `db.prepare<ParamsTuple, RowType>()` generic form to satisfy strict TypeScript — avoids `as` casts in query results.

### Completion Notes

Story 3.1 complete. Three files created:
1. `server/migrations/002_add_job_ingest_raw.sql` — idempotent `CREATE TABLE IF NOT EXISTS` + URL index
2. `server/services/ingestDedup.ts` — `createIngestDedupService(db)` factory; `checkUrlExists` + `insertRawPayload`
3. `tests/unit/ingestDedup.test.ts` — 9 tests covering null/found URL checks, insert shape, SHA-256 hash format, custom httpStatus, and idempotency via the check-before-insert pattern

206/206 tests pass. 0 lint errors. 0 tsc errors.

## File List

- `server/migrations/002_add_job_ingest_raw.sql` (new)
- `server/services/ingestDedup.ts` (new)
- `tests/unit/ingestDedup.test.ts` (new)

## Change Log

- 2026-06-12: Story 3.1 implemented — `job_ingest_raw` migration + `createIngestDedupService` factory with URL dedup functions. 9 tests added; 206/206 pass.
