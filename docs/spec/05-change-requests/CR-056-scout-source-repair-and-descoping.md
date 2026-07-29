# CR-056: Scout Source Repair, Ban-Risk Descoping, and Years-Gate Correction

## Metadata
- **Status**: Implemented
- **Date**: 2026-07-06
- **Related requirements**: None formally registered — this was a diagnostic/operational session, not a planned epic. No new FR/AC codes were minted; see acceptance criteria below for what was actually verified.
- **Tracker**: none (single-session fix, not tracked as a multi-epic implementation)

## Problem
A day-over-day audit of actual scout runs found the connector layer was producing far less than it appeared to:
1. **Ashby, Workable, and OpenPostings connectors were silently returning 0 jobs on every run**, indefinitely, with no error surfaced anywhere — each had a distinct root cause (wrong/private endpoint, deprecated endpoint, wrong local path + wrong response parsing).
2. **Working Nomads connector's category filter could never match** — it filtered on a `category_name` value ("product"/"management") that doesn't exist anywhere in Working Nomads' real category taxonomy.
3. **BuiltIn and Levels.fyi connectors used Playwright + a stealth plugin** to scrape live sites directly — the same ban-risk pattern the rest of the connector stack was explicitly designed to avoid. Levels.fyi had been dead for 10+ days with no visible error.
4. **Greenhouse/Lever/Ashby/Workable per-company connectors required a hand-curated company watchlist**, which no longer matches the actual job-search approach (broad PM search by location, not fixed companies) and duplicated coverage OpenPostings already provides more broadly.
5. **Geographic gate silently rejected San-Diego-titled jobs** with thin descriptions, because the short-description fast path checked only work-setting and source, never the job title.
6. **Settings page used one shared debounce timer for every field**, so saving the Adzuna API key could be silently cancelled by editing any other field within 1 second of it.
7. **`experience_range.max` was set to 7**, one year below actual (8) years of experience, silently rejecting "Senior Product Manager" roles that require 8 years.

## Decision
1. Fixed Ashby (correct public endpoint, correct response shape, correct field name), Workable (correct endpoint), and Working Nomads (title-text match instead of category match) connectors. All three verified live against real APIs post-fix.
2. Located the OpenPostings project already present at `data/archive/OpenPostings-extracted/OpenPostings-main/` (moved there during a prior data-consolidation pass, never reconnected), installed its 4 real server dependencies only, repointed the connector's `DEFAULT_DIR`, and fixed the `{items:[...]}` response-parsing bug. Verified live through the full spawn → sync → search flow.
3. Removed BuiltIn and Levels.fyi connectors entirely (browser automation / ban risk).
4. Removed the per-company Greenhouse, Lever, Ashby, and Workable connectors and the `atsBoards.ts` loader that fed them; OpenPostings now serves as the broad ATS-coverage layer with no watchlist required.
5. `passesGeographicGate` (`shared/domain/gates.ts`) now checks the job title against `localAreaTerms` before falling back to the work-setting/remote-only-source check, so local-market jobs aren't rejected purely for lacking a scraped description yet.
6. `SettingsView.tsx`'s single `debounceTimer` ref replaced with a per-settings-key `debounceTimers` map, so unrelated fields no longer cancel each other's pending saves.
7. `experience_range.max` raised 7 → 8, applied through the real `job_search` settings API (not a direct file edit) so it survives the next Settings save.

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| — | Ashby connector returns real jobs against the live API (verified: 0 → 15 on existing watchlist, via `runConnectorOrchestration()`) |
| — | OpenPostings connector completes a full spawn → sync → search cycle and returns real jobs (verified: 0 → 3, including a company not on any watchlist) |
| — | Working Nomads and Workable connectors no longer error or silently no-op against their real APIs (verified live; both returned 0 on the specific run tested only because no matching listings existed that day, not because of a code fault) |
| — | `passesGeographicGate` passes a San-Diego-titled job with a thin description from a non-remote-only source, and still rejects a generic-titled job in the same conditions (unit-verified) |
| — | Adzuna API key persists in `profiles.api_connections` after being entered alongside edits to other Settings fields (verified against the live database, both before-fix failure and after-fix success) |
| — | Full vitest suite passes after all connector removals/fixes (262 tests / 29 files) |
| — | `npx tsc --noEmit` clean after all removals (no dangling imports) |

## Out of scope
- Adzuna (needs real API credentials — resolved separately, not part of this CR's code changes) and any further location-based search connector work.
- Rebuilding a curated Greenhouse/Lever/Ashby/Workable watchlist — deliberately not replaced, since the underlying need (broad search, no watchlist) is now met by OpenPostings.
- R5 PM-craft resume-content gaps and the Guidehealth/Ottimate role-fit questions surfaced during the same session's resume review — tracked separately, not a scout-pipeline change.
