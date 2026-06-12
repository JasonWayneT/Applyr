---
status: review
baseline_commit: ''
---

# Story 1.1: Migration Runner and Connector Contract

As a developer implementing the Applyr expansion,
I want a versioned migration runner and the `JobConnector` shared type contract in place,
So that all downstream stories have a consistent interface to implement and a safe, idempotent mechanism for applying schema changes.

## Acceptance Criteria

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

## Tasks/Subtasks

- [x] Task 1: Write failing tests for migration runner
  - [x] Test: `schema_migrations` table created on first run
  - [x] Test: pending SQL files applied in ascending order
  - [x] Test: applied migrations recorded in `schema_migrations`
  - [x] Test: already-applied migrations skipped on re-run
  - [x] Test: missing migrations directory handled gracefully
- [x] Task 2: Implement `server/migrationRunner.ts`
  - [x] Export `runMigrations(db, migrationsDir)` function
  - [x] Bootstrap `schema_migrations` table with `CREATE TABLE IF NOT EXISTS`
  - [x] Read and sort `.sql` files from migrations dir
  - [x] Apply unapplied migrations, record each with ISO timestamp
  - [x] Skip gracefully when directory doesn't exist
- [x] Task 3: Wire migration runner into `server/db.ts`
  - [x] Import `runMigrations` from `./migrationRunner.js`
  - [x] Call after existing db setup with `server/migrations/` path
  - [x] Create `server/migrations/` directory (empty — files added in subsequent stories)
- [x] Task 4: Create `shared/types/connectors.ts`
  - [x] Export `JobConnector` interface (sourceId, fetchJobs, healthCheck, normalize)
  - [x] Export `RawJobPayload`, `NormalizedJob`, `ConnectorHealth`, `SourceStatus`, `SSEEvent`
- [x] Task 5: Update project config
  - [x] Update `tsconfig.json`: add `shared` and `packages` to include, add `paths` alias
  - [x] Update `package.json`: add `shared` to lint script (packages added in Story 1.2 when dir exists)
  - [x] Update `vitest.config.ts`: add `packages/**/*.test.ts` include
- [x] Task 6: Verify all tests pass and zero lint/tsc errors

## Dev Notes

- `server/db.ts` uses `__dirname` via `fileURLToPath(import.meta.url)` — use same pattern in migrationRunner for `server/migrations/` path resolution
- Migration runner is extracted to `server/migrationRunner.ts` (not inlined in db.ts) for independent testability
- Tests use `better-sqlite3` in-memory (`:memory:`) to avoid touching `jobagent.sqlite`
- Existing legacy schema version tracking in `server/db.ts` (via `profiles` table) stays untouched — new runner is additive
- ESM imports require `.js` extension even for `.ts` source files (project-wide rule)
- `tsconfig.json` currently only includes `src` and `server` — add `shared` and `packages`
- Architecture flags `tsconfig.json` path aliases for `shared/*` as a nice-to-have — include in this story
- `server/migrations/` directory created empty; migration SQL files are added in subsequent stories (001–007)

## Dev Agent Record

### Implementation Plan
Extract `runMigrations` to a standalone `server/migrationRunner.ts` that accepts `(db: Database, migrationsDir: string)`. Wire it into `server/db.ts` after existing initialization. Create `shared/types/connectors.ts` with all required exports. Update tsconfig, package.json lint, and vitest config to cover new directories.

### Debug Log
_empty_

### Completion Notes
- Migration runner extracted to `server/migrationRunner.ts` for independent testability
- 7 tests cover full runner behavior (bootstrap, apply, record, skip, missing dir, ordering)
- `shared/types/connectors.ts` defines all 6 exports; 4 tests verify runtime shape and discriminated union coverage
- `tsconfig.json` now includes `shared` and `packages`, with `paths` alias for `shared/*`
- `vitest.config.ts` now includes `packages/**/*.test.ts` for future connector tests
- `npm run lint` (0 errors), `npx tsc --noEmit` (0 errors), 96/96 tests pass, 0 regressions

## File List

- `server/migrationRunner.ts` (new)
- `server/db.ts` (updated — import + runMigrations call)
- `server/migrations/` (new directory, empty)
- `shared/types/connectors.ts` (new)
- `tests/unit/migrationRunner.test.ts` (new)
- `tests/unit/connectorTypes.test.ts` (new)
- `tsconfig.json` (updated — include, paths)
- `package.json` (updated — lint script)
- `vitest.config.ts` (updated — packages include)
- `_bmad-output/implementation/stories/1-1-migration-runner-and-connector-contract.md` (new)

## Change Log

- 2026-06-11: Story 1.1 complete — migration runner and connector contract in place
