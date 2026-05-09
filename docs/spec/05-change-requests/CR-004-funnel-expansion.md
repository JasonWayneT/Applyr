# Change Request: CR-004 Funnel Expansion & Source Hardening

## Metadata

- CR ID: `CR-004`
- Status: implemented
- Date: 2026-05-09
- Requested by: User
- Implements: `FR-052`, `FR-053`, `FR-054`, `FR-055`, `FR-056`, `NFR-004`, `SEC-002`
- Feature spec: `FEAT-001`

## Problem

The job ingestion pipeline had six weaknesses limiting funnel volume and generalizability:

1. **Narrow source coverage** — Only 4 API sources + 2 browser sources. Major boards (Himalayas, The Muse, Adzuna) were absent.
2. **Narrow search terms** — `materializeJobSearchPrefs()` generated only `["Product Manager", "Product Owner"]` for PM roles; no role-generic expansion logic for other roles.
3. **No Adzuna integration** — Adzuna aggregates thousands of boards; no connection existed. Keys had no UI entry point and were expected to live only in `.env`.
4. **No Adzuna rate guard** — Free tier is 250 hits/day. Without a cap, iterating all SEARCH_TERMS across multiple runs could exhaust the daily quota.
5. **Hardcoded PM-specific sources** — `scoutTheMuse()` used `category=Product` and `scoutWWR()` fetched product-specific RSS feeds with no dynamic routing based on TARGET_ROLE.
6. **Hardcoded `Product Owner` fallback** — `SEARCH_TERMS` emergency fallback in `scout_local.ts` hardcoded `"Product Owner"` regardless of the user's configured role.

## Solution

### FR-052 — Three new Phase 1 API sources
Add `scoutHimalayas()`, `scoutTheMuse()`, and `scoutAdzuna()` to the Phase 1 parallel batch in `scout_local.ts`. All run alongside existing sources with no browser dependency.

### FR-053 — Role-generic search term expansion
Update `materializeJobSearchPrefs()` in `server/index.ts` to expand search terms based on `targetRole`. PM-role expansion adds "Technical Product Manager", "Platform Product Manager", "Digital Product Manager". Other roles receive the target role as-is.

### FR-054 — Optional Adzuna connection via Settings UI
Add an "Adzuna Job Search API" section to `SettingsView.tsx` under Settings > API or Connections > Data Sources. Stores `adzunaAppId` + `adzunaAppKey` under `profiles/api_connections` in SQLite (gitignored). `server/scout.ts` reads this record and injects the keys as env vars when spawning `scout_local.ts`.

### FR-055 — Adzuna free-tier rate guard
Add `MAX_ADZUNA_CALLS_PER_RUN = 10` constant and per-run call counter in `scoutAdzuna()`. Calls are spaced 3 seconds apart to respect the 25 req/min limit. Hard break when cap is reached with a log warning.

### FR-056 — Role-aware source routing
Add `getTheMuseCategory(targetRole: string)` helper that maps the target role to a Muse API category string. Remove hardcoded `"Product Owner"` from the `SEARCH_TERMS` emergency fallback.

### SEC-002 — API key isolation
Adzuna keys are stored only in SQLite `profiles` table (excluded from git via `.gitignore`). Keys are injected at spawn time via env vars, never written to any tracked file.

## Files Changed

| File | Change |
|------|--------|
| `scripts/scout_local.ts` | New sources, rate guard, role-aware routing, fallback fix, Implements comments |
| `server/index.ts` | Expanded search term generation in `materializeJobSearchPrefs()` |
| `server/scout.ts` | Inject `api_connections` env vars at spawn time |
| `src/components/SettingsView.tsx` | Adzuna connection fields in API or Connections tab |
| `docs/spec/02-requirements-registry.md` | FR-052–FR-056, NFR-004, SEC-002 |
