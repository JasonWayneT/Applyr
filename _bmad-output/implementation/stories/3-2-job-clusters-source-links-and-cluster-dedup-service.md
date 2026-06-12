---
status: review
baseline_commit: '1862c96c9002b7d4fc45afa24059be15b222f82c'
---

# Story 3.2: Job Clusters, Source Links, and Cross-Source Dedup Service

As a user of Applyr,
I want duplicate jobs appearing across multiple sources merged into single canonical records with source attribution tracked,
So that the same role doesn't clutter the job list just because it was posted on multiple platforms.

## Acceptance Criteria

**Given** the migration runner applies `004_add_job_clusters.sql` and `005_add_job_source_links.sql`
**When** the server starts
**Then** a `job_clusters` table exists with columns `id TEXT PRIMARY KEY`, `canonical_job_id TEXT`, `created_at TEXT`
**And** a `job_source_links` table exists with columns `id TEXT PRIMARY KEY`, `cluster_id TEXT`, `source_id TEXT`, `external_job_id TEXT`, `raw_ingest_id TEXT`

**Given** `server/services/clusterDedup.ts` exports `createClusterDedupService(db)`
**When** `runClusterDedup()` is called
**Then** it processes `job_ingest_raw` entries without a `job_source_links` entry, identifies duplicates using URL normalization and Company+Title matching (via `jobs` table), and writes results to `job_clusters` and `job_source_links`

**Given** two `job_ingest_raw` entries with URLs that normalize to the same value (e.g. `http://` vs `https://`, trailing slash difference)
**When** `runClusterDedup()` runs
**Then** both entries are linked to the same `job_clusters` row via `job_source_links`

**Given** two `job_ingest_raw` entries from different sources with different URLs but the same normalized Company+Title in the `jobs` table
**When** `runClusterDedup()` runs
**Then** both entries are linked to the same `job_clusters` row — the canonical_job_id resolves to the first-seen job for that Company+Title pair

**Given** `runClusterDedup()` is called on entries already processed
**When** it runs again
**Then** no duplicate `job_clusters` or `job_source_links` rows are created (idempotent)

**Given** `npm run lint` and `npx tsc --noEmit`
**When** both run
**Then** zero errors

## Tasks/Subtasks

- [x] Task 1: Add job_clusters and job_source_links migrations
  - [x] `server/migrations/004_add_job_clusters.sql` — `CREATE TABLE IF NOT EXISTS job_clusters (id TEXT PRIMARY KEY, canonical_job_id TEXT, created_at TEXT)`; index on `canonical_job_id`
  - [x] `server/migrations/005_add_job_source_links.sql` — `CREATE TABLE IF NOT EXISTS job_source_links (id TEXT PRIMARY KEY, cluster_id TEXT, source_id TEXT, external_job_id TEXT, raw_ingest_id TEXT)`; index on `cluster_id`; index on `raw_ingest_id` (used in LEFT JOIN for unprocessed check)

- [x] Task 2: Create clusterDedup service
  - [x] `server/services/clusterDedup.ts` — factory pattern `createClusterDedupService(db)`, same pattern as `ingestDedup.ts`
  - [x] `normalizeUrl(url)`: strips protocol, lowercases host + path, strips query/hash/trailing slash; falls back to `url.toLowerCase().trim()` on parse failure
  - [x] `normalizeText(s)`: lowercase, trim, collapse whitespace
  - [x] `runClusterDedup()`: fetches unprocessed rows (LEFT JOIN job_source_links WHERE sl.id IS NULL), builds URL→job and companyTitle→canonicalJobId lookup maps from `jobs` table, assigns each raw entry a canonical_job_id via URL then Company+Title resolution, finds-or-creates cluster, inserts source link
  - [x] All DB calls synchronous (better-sqlite3). No async/await. Prepared statements cached at factory creation.
  - [x] No imports from `server/db.js` — factory accepts db parameter

- [x] Task 3: Write service tests
  - [x] `tests/unit/clusterDedup.test.ts` — in-memory SQLite with `job_ingest_raw`, `jobs`, `job_clusters`, `job_source_links` tables
  - [x] Test: empty `job_ingest_raw` → `runClusterDedup()` no-ops (no clusters created)
  - [x] Test: one raw entry → one cluster + one source link created
  - [x] Tests: http vs https, trailing slash, query string stripped → same cluster (3 URL normalization tests)
  - [x] Tests: same company+title different sources → same cluster; case-insensitive match (2 Company+Title tests)
  - [x] Test: idempotent — calling `runClusterDedup()` twice → same count (no duplicates)
  - [x] Test: raw entry with no matching `jobs` entry → cluster created with `external_job_id` as `canonical_job_id`
  - [x] Test: distinct jobs with different company+title produce separate clusters

- [x] Task 4: Verify quality gates
  - [x] `npm run lint` — zero errors (28 pre-existing warnings)
  - [x] `npx tsc --noEmit` — zero type errors (fixed pre-existing `searchTerms` error in scoutOrchestrator.ts from Story 2.1)
  - [x] `npm run test:vitest` — 220/220 tests pass (10 new clusterDedup tests)

## Dev Notes

- **Factory pattern:** Same as `ingestDedup.ts` — `createClusterDedupService(db)`. No module-level `db` import. This keeps the service testable without vi.mock complications.
- **URL normalization algorithm:** Strip protocol entirely, lowercase hostname, lowercase path, strip query string, strip fragment, strip trailing slashes. `new URL()` for parsing. Fallback: `url.toLowerCase().trim()` if parsing fails.
- **Company+Title canonical resolution:** Build `companyTitleToCanonical: Map<string, string>` from ALL `jobs` rows before processing. Key = `normalizeText(company) + '::' + normalizeText(title)`. Value = FIRST job.id seen for that key. When a raw entry maps to a `candidateJob` via URL, resolve to `companyTitleToCanonical.get(ctKey) ?? candidateJob.id` — this is what merges cross-source duplicates with the same role title at the same company.
- **URL→Job lookup:** `Map<string, {id, company, title}>` built from `jobs.url` column. Primary lookup key = `normalizeUrl(jobs.url)`. Also try `normalizeUrl(row.external_job_id)` as secondary lookup (most connectors use URL as external_job_id).
- **Cluster find-or-create:** In-memory `Map<canonicalJobId, clusterId>` seeded from existing `job_clusters` rows before the loop. This avoids N+1 queries and handles idempotency.
- **`INSERT OR IGNORE` on source links:** Prevent duplicate source links on re-run.
- **Migration numbers:** 004 for clusters, 005 for source links. Story 2.1 (Sources Registry) used 003, so these are next in sequence.
- **Test schema:** Both migrations AND the `job_ingest_raw` + `jobs` table schema are needed in test setup. `jobs` needs at minimum: `id TEXT PRIMARY KEY, company TEXT, title TEXT, url TEXT UNIQUE`.

## Dev Agent Record

### Implementation Notes

- **URL normalization strips protocol:** `normalizeUrl` returns `hostname + path` (no scheme). This is intentional — http vs https for the same host/path normalize identically. The trade-off: two genuinely different HTTP/HTTPS services on the same hostname would collapse, but that scenario doesn't occur in practice for job board URLs.
- **Company+Title resolution via `jobs` table:** The `clusterDedup` service does NOT parse `payload_json` to extract company/title — field names vary by connector. Instead it joins through the `jobs` table (which has normalized fields after orchestrator processing). Secondary URL lookup via `external_job_id` handles the common case where connectors use URL as their external ID.
- **Pre-existing tsc error fixed:** `scoutOrchestrator.ts` line 108 passed `{ searchTerms }` to `createThemuseConnector`, but `ThemuseConfig` only accepts `{ category? }`. Fixed by passing no config (uses default `'Product'` category). This was introduced in Story 2.1 and blocked the `npx tsc --noEmit` quality gate.
- **In-memory cluster map:** `clusterByCanonical` is seeded from existing `job_clusters` rows before the loop. New clusters added during the loop are also added to the map, so a second raw entry with the same canonical job finds the cluster in memory without a DB round-trip.

### Completion Notes

Story 3.2 complete. Five files created/modified:
1. `server/migrations/004_add_job_clusters.sql` (new)
2. `server/migrations/005_add_job_source_links.sql` (new)
3. `server/services/clusterDedup.ts` (new) — `createClusterDedupService(db)` factory
4. `tests/unit/clusterDedup.test.ts` (new) — 10 tests
5. `server/services/scoutOrchestrator.ts` (fix) — removed invalid `searchTerms` from `createThemuseConnector` call

220/220 tests pass. 0 lint errors. 0 tsc errors.

## File List

- `server/migrations/004_add_job_clusters.sql` (new)
- `server/migrations/005_add_job_source_links.sql` (new)
- `server/services/clusterDedup.ts` (new)
- `tests/unit/clusterDedup.test.ts` (new)
- `server/services/scoutOrchestrator.ts` (modified — tsc fix)

## Change Log

- 2026-06-12: Story 3.2 implemented — `job_clusters` + `job_source_links` migrations; `createClusterDedupService` factory with URL normalization + Company+Title dedup; 10 tests; pre-existing tsc error in scoutOrchestrator fixed. 220/220 pass.
