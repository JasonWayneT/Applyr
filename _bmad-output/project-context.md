---
project_name: 'Applyr'
user_name: 'Jason'
date: '2026-06-11'
status: 'complete'
sections_completed: ['technology_stack', 'language_rules', 'framework_rules', 'database_rules', 'testing_rules', 'code_quality_rules', 'workflow_rules', 'critical_rules']
rule_count: 62
optimized_for_llm: true
---

# Project Context for AI Agents

_Critical rules and patterns for implementing code in this project. Focus on unobvious details agents might otherwise miss._

---

## Technology Stack & Versions

| Layer | Technology | Version |
|---|---|---|
| Language | TypeScript | ^6.0.2 |
| Runtime | Node.js | 18+ |
| Backend | Express | ^5.2.1 |
| Frontend | React | ^19.2.5 |
| Build tool | Vite | ^8.0.8 |
| CSS | Tailwind | ^4.2.2 |
| Database | better-sqlite3 | ^12.9.0 |
| Server runner | tsx | ^4.21.0 |
| Browser automation | Playwright | ^1.59.1 |
| Test runner | Vitest | ^3.2.4 |
| Scoring pipeline | Python | (batch_pipeline.py — version managed separately) |
| Module system | ESM | ("type": "module" in package.json) |

**Version-critical notes:**
- Express 5.x — not v4. Route handler signatures and error middleware differ from v4 examples.
- TypeScript 6.x — newer than most training data; `bundler` moduleResolution, not `node16`.
- React 19.x — concurrent features default; avoid legacy `ReactDOM.render`.
- Tailwind 4.x — config format changed; do not copy Tailwind v3 patterns.

---

## Language-Specific Rules

### TypeScript

- **Strict mode is on** — `"strict": true`. No implicit `any`, no loose nulls.
- **ESM imports require `.js` extension** — even when importing `.ts` source files.
  `import { db } from './db.js'` ✓  |  `import { db } from './db'` ✗
- **`moduleResolution: "bundler"`** — not `node16`. Do not use `node16`-style type imports.
- **`noEmit: true`** — TypeScript is type-check only; Vite/tsx handle transpilation.
- **`isolatedModules: true`** — every file must be a module. Type-only imports must use `import type { Foo }` syntax.
- **Server-side imports use `.js`; React component imports do not** — Vite handles frontend resolution without extensions; tsx/Node requires `.js` on the server.
- **`randomUUID`** comes from Node's built-in `crypto` — `import { randomUUID } from 'crypto'`. Do not import from `uuid` (not installed).

### Python Boundary

- Python layer (`scripts/batch_pipeline.py`) is a subprocess — never import or call Python functions from TypeScript directly.
- TypeScript spawns Python via `runStreamLines` / `spawnPython` in `server/pipeline/processRunner.ts`.
- Python writes to: `jobs`, `job_scores`, `job_tags`, `activity_log` only.
- TypeScript must never write to: `sources`, `domain_policies`, `job_ingest_raw`, `job_clusters`, `job_source_links`.

---

## Framework-Specific Rules

### Express (v5)

- **All routes use `Router()`** — one router per domain file, mounted in `server/index.ts`.
- **New route files follow the existing pattern** — named `Router` export, imported and mounted in `server/index.ts`.
- **API responses are direct JSON — no wrapper envelope.**
  `res.json({ id, title })` ✓  |  `res.json({ data: { id, title }, error: null })` ✗
- **API errors:** `res.status(4xx).json({ error: string, code?: string })` — always include HTTP status.
- **`requireApiToken` middleware** in `server/middleware.ts` — apply to any state-modifying route.
- **Express 5:** thrown errors propagate automatically from async handlers. Do not copy Express 4 `try/catch → next(err)` boilerplate.

### SSE (Server-Sent Events)

- **Typed event envelopes only** — never free-form strings for structured data.
  ```ts
  // ✓ correct
  res.write(`event: source_progress\ndata: ${JSON.stringify({ type: 'source_progress', source, fetched, filtered, passed })}\n\n`)
  // ✗ wrong
  res.write(`data: greenhouse: 14 fetched\n\n`)
  ```
- **Defined event types** (from `shared/types/connectors.ts`):
  `source_progress` | `stage_handoff` | `source_health` | `connector_error` | `run_complete`
- **SSE setup pattern** (match existing in `server/routes/pipeline.ts`):
  ```ts
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();
  ```

### React (v19)

- **All API calls go through `src/lib/apiClient.ts`** — no direct `fetch` from components. No direct DB access from frontend.
- **Component additions only** — `App.tsx`, `main.tsx`, routing structure unchanged. New components → `src/components/`; new pages → `src/pages/`.
- **`SyncActivityView.tsx`** is the SSE consumer — wire per-source metrics UI updates here.
- Do not use `ReactDOM.render` — React 19 uses `createRoot`.

---

## Database Rules

### Naming

- **All SQLite identifiers use `snake_case`** — tables, columns, indexes.
  `source_id`, `fetched_at`, `is_latest` ✓  |  `sourceId`, `fetchedAt`, `isLatest` ✗
- **Index naming:** `idx_{table}_{column}` — e.g. `idx_jobs_status`, `idx_job_scores_job_id`.
- **`camelCase` in TypeScript objects, `snake_case` in SQLite** — explicit mapping at the repository layer. SQLite column names must never leak into API responses.
- **Dates:** ISO 8601 strings — `2026-06-11T14:30:00Z`. Never Unix timestamps.

### Migration Pattern (Expansion Work)

- **New tables use the numbered migration runner** — `server/migrations/{NNN}_{description}.sql`. Runner in `server/db.ts` checks `schema_migrations` before applying each file at startup.
- **All migration SQL must be idempotent** — `CREATE TABLE IF NOT EXISTS`, never bare `CREATE TABLE`.
- **Do NOT use the old inline pattern** (`try { db.exec('ALTER TABLE...') } catch {}`) for any of the 7 new tables. That pattern exists in `server/db.ts` for legacy columns only.
- **Migration files are append-only** — never edit an already-applied migration. Add a new numbered file.

### FTS5 / Full-Text Search

- **All writes to `jobs` must go through `server/repository/jobRepository.ts`** — ensures FTS sync (`syncJobFts` / `deleteJobFts`) is never skipped. Never write to `jobs` directly from routes or connectors.

### SQLite Operational Rules

- **`better-sqlite3` is synchronous** — all DB operations are blocking. Do not wrap in `Promise` or `async/await`.
- **WAL mode and `busy_timeout = 30000`** are set at startup in `server/db.ts` — do not re-set these pragmas elsewhere.
- **`db` is a singleton** — import from `server/db.ts`, never instantiate a new `Database`.

### Data Territory

| Territory | Tables |
|---|---|
| TypeScript owns (read + write) | `sources`, `domain_policies`, `job_ingest_raw`, `job_clusters`, `job_source_links` |
| Handoff (TS writes `status='New'`, Python reads) | `jobs` |
| Shared (both layers write) | `job_scores`, `job_tags`, `activity_log` |

---

## Testing Rules

### Test Runner & Config

- **Vitest** — `npm run test:vitest`. Config in `vitest.config.ts`. Include paths: `src/**/*.test.ts` and `tests/**/*.test.ts`.
- **Import pattern in test files uses `.js` extension** — same ESM rule applies.

### Test Organization

- **Connector tests are co-located** — `packages/connectors/{name}/{name}.test.ts` alongside `index.ts`.
- **Integration tests go in `tests/`** — unit tests for domain logic in `tests/unit/`; fixtures in `tests/fixtures/`.
- **Connector fixture payloads** go in `packages/connectors/{name}/fixtures/` — example raw API responses for unit tests.

### Test Structure

- **Use `describe` / `it` / `expect`** from vitest explicitly.
- **Fixture factory pattern** — `baseJob(overrides)` rather than duplicating full objects. See `tests/unit/gates.test.ts`.
- **No live network calls or live DB in unit tests** — connector tests use fixture JSON only.

### What to Test for New Connectors

Each connector requires:
1. `fetchJobs()` against fixture data — assert normalized output shape.
2. Empty response fixture — connector returns `[]`, does not throw.
3. TheirStack only: credit guard aborts before fetching when cap is reached.

---

## Code Quality & Style Rules

### Naming Conventions

- **TypeScript:** `camelCase` variables/functions, `PascalCase` types/interfaces/classes, `camelCase.ts` filenames.
- **API endpoints:** `kebab-case` plural nouns — `/api/sources`, `/api/domain-policies`.

### Connector Module Shape

Every connector in `packages/connectors/{name}/` must follow this structure:
```ts
import type { JobConnector } from '../../../shared/types/connectors.js';

export const {name}Connector: JobConnector = {
  name: '{name}',
  async fetchJobs() { ... },
  async getHealth() { ... },
};
```
- **`JobConnector` always imported from `shared/types/connectors.ts`** — never redefined locally.
- **All shared types live in `shared/types/connectors.ts`** — no barrel re-exports.

### Linting & Formatting

- **ESLint 9 + `typescript-eslint` + Prettier** — `eslint.config.mjs` and `.prettierrc`.
- **`npm run lint`** must pass with zero errors before committing. `npm run format` for Prettier.
- **`@typescript-eslint/no-explicit-any`** is `warn` — address in new code, tolerated in existing.
- **Empty catch blocks:** use `catch {}` (not `catch (e) {}`); add a comment explaining intent.
- **Unused vars must be prefixed `_`** — `_unused`, `_e`.
- **JSX unescaped entities are errors** — use `&apos;`, `&quot;`, `&amp;` in JSX text nodes.

### Logging

- **`logActivity(level, source, message, meta?)`** from `server/db.ts` — always use in server production paths. Never `console.log` in connector or route code.
- **Levels:** `'INFO'` | `'WARN'` | `'ERROR'`

---

## Development Workflow Rules

### Running the Project

- **Dev:** `npm run dev` — Vite (port 5173) + Express (port 3000) concurrently.
- **Build:** `npm run build` — tsc type-check + Vite bundle.
- **Frontend proxies to backend** — all `/api/*` → `http://127.0.0.1:3000`.

### Before Committing

1. `npm run lint` — zero errors required.
2. `npm run test:vitest` — all tests pass.
3. `npx tsc --noEmit` — type-check clean.

### Git & Commit Conventions

- **Conventional Commits** — `type(scope): description`
  - Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
  - FR-scoped: `feat(FR-102): add greenhouse connector`
- **Primary branch: `main`**. `staging` for pre-release validation.
- **Two remotes:** `origin` (ApplyrPrivate — private), `jobhunt` (JobHuntAgent — public). Do not push to `jobhunt` during expansion.

### Scope Discipline for This Expansion

- **Additions only** in existing files unless architecture marks `← UPDATED`.
- **`scripts/scout_local.ts` is deleted** after Cluster 2 — do not extend it.
- **`server/db.ts` inline migration pattern is legacy** — new tables go through `server/migrations/`.
- **No new runtime dependencies** — zero new deps by architecture decision.
- **`shared/` and `packages/` are new directories** — create them; do not put connector code elsewhere.

---

## Critical Don't-Miss Rules

### The 8 Enforcement Rules

All implementation agents MUST:

1. **Use `snake_case` for all SQLite identifiers** — columns, tables, indexes.
2. **Import `JobConnector` from `shared/types/connectors.ts`** — never redefine locally.
3. **Run crawl policy check before any domain fetch** — `checkCrawlPolicy(domain)` fires before any connector with `source_type = 'crawl'`.
4. **Use typed SSE event envelopes** — never free-form strings for structured data.
5. **Write connector errors to both `sources` table and SSE stream** — catch → write `sources` → emit `connector_error`.
6. **Check URL existence before inserting to `job_ingest_raw`** — return existing `external_job_id` if found; never insert duplicates.
7. **Apply schema changes via migration runner** — never bare `CREATE TABLE` in application code.
8. **Respect the TypeScript/Python boundary** — `jobs` table is the only handoff point.

### Anti-Patterns

| Anti-pattern | Why it breaks |
|---|---|
| `import { JobConnector } from './types'` (local) | Breaks single-source-of-truth; drift across connectors |
| `db.exec('CREATE TABLE sources ...')` in app code | Bypasses version tracking; double-applies on restart |
| `res.json({ data: {...}, error: null })` | Breaks API contract; frontend expects flat JSON |
| `console.log(...)` in server production paths | Use `logActivity()` instead |
| `new Database(...)` outside `server/db.ts` | Second connection; WAL pragma not applied |
| `res.write(\`data: greenhouse fetched 14\n\n\`)` | SSE consumers cannot parse untyped strings |
| Importing `server/db.ts` in `packages/connectors/` | Circular dependency; connectors receive `db` via injection |
| `await db.prepare(...)` | `better-sqlite3` is synchronous — no async API |

### TheirStack Credit Guard

- Must read `credits_used_this_month` from `sources` table **before every fetch** and abort if cap (200) would be exceeded.
- Log `WARN` within 20% of cap; log `ERROR` and return `[]` when cap is hit. Never silently skip.

### job_scores `is_latest` Flag

- When writing a new score row: (1) set `is_latest = false` on all existing rows for that `job_id`, then (2) insert new row with `is_latest = true`.
- Both steps must be in a single transaction.
- Normal UI queries filter `WHERE is_latest = true`.

---

## Usage Guidelines

**For AI Agents:** Read this file before implementing any code. Follow all rules exactly. When in doubt, prefer the more restrictive option. If a new pattern emerges that contradicts a rule here, surface it — do not silently deviate.

**For Humans:** Keep this file lean. Update when the stack changes. Remove rules that become obvious over time.

_Last Updated: 2026-06-11_
