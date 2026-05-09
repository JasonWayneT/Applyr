# Change Request: CR-003 Unified Job Search Settings

## Metadata

- CR ID: `CR-003`
- Status: implemented
- Date: 2026-05-08
- Requested by: User
- Implements: `FR-046`, `FR-047`, `FR-048`, `FR-049`
- Feature spec: `FEAT-009`

## Problem

The application had four completely disconnected data islands for search and pipeline criteria:

1. `profiles/scouter_preferences` (SQLite) — written by the Scout tab UI, never consumed by scouts
2. `profiles/preferences` (SQLite) — written by the Profile Preferences tab, never read by the pipeline
3. `data/candidate_preferences.json` (static file) — actually read by Python pipeline, but never written by any UI action
4. Hardcoded values in `server/config.ts` and `scripts/scout_local.ts` — title blocklist, search terms, LinkedIn geo ID, BuiltIn URL, freshness window, RemoteOK tags

Net effect: every UI preference change was inert. Every scout run searched for "Product Manager" in the US, Remote, with a 7-day window, regardless of any setting the user had ever changed.

Additionally, the `codifyExperienceAndAssignIDs()` function contained hardcoded employer-specific ACC-ID starting values (`nextAccCision = 106`, `nextAccSterkly = 203`, `nextAccZero = 303`), making the application non-functional for any new user.

## Solution

### Architecture change

Introduce a single canonical write path: UI → `profiles/job_search` (SQLite) → `data/candidate_preferences.json` (materialized). Python scripts read only the JSON file (unchanged read path). The server materializes the JSON on every `POST /api/profile/job_search`.

### UI changes

- Renamed sidebar navigation item "Scout" → "Job Search"
- Replaced the split Scouter Parameters + Profile Preferences panels with a unified two-card layout on the Job Search tab:
  - **Primary card**: Target Role, Work Setting, Location (dropdown), Date Posted (chips), Experience Level (multi-select)
  - **Secondary card**: Title Blocklist, Industry Blocklist, Minimum Salary
- Removed "Preferences" sub-tab from Profile page entirely

### Backend changes

- Added `materializeJobSearchPrefs()` function to `server/index.ts`
- Added `POST /api/profile/job_search` specific route (before generic `:key` route) that saves + materializes
- Rewrote `codifyExperienceAndAssignIDs()` to use a dynamic `Map<string, number>` keyed by section identifier, supporting any number of employer sections

### Script changes

- `scripts/scout_local.ts`: reads `candidate_preferences.json` at startup; all URLs built dynamically (LinkedIn, BuiltIn, OpenPostings, RemoteOK)
- `scripts/utils.py`: `JD_REQUIRED_KEYWORDS` and `MIN_FIT_SCORE` bootstrapped from prefs at import time with fallback defaults
- `scripts/batch_pipeline.py`: hardcoded `score < 72` replaced with `score < MIN_FIT_SCORE`

## Files changed

| File | Change type | Summary |
|---|---|---|
| `data/candidate_preferences.json` | modified | Updated to unified schema with `work_setting`, `experience_levels`, `date_posted`, `freshness_days` |
| `server/index.ts` | modified | Added materialization function, job_search route, generic codification engine |
| `server/config.ts` | modified | Relabeled as fallback defaults only |
| `src/components/Sidebar.tsx` | modified | "Scout" → "Job Search" |
| `src/App.tsx` | modified | Route case updated to match |
| `src/pages/SyncActivityView.tsx` | rewritten | Unified JobSearchSettings state; primary + secondary filter cards; saves to profiles/job_search |
| `src/pages/ProfileView.tsx` | modified | Removed Preferences tab, PreferenceData interface, and all preferences state |
| `scripts/scout_local.ts` | modified | Runtime prefs loading; dynamic URL builders for LinkedIn and BuiltIn; dynamic search terms |
| `scripts/utils.py` | modified | JD_REQUIRED_KEYWORDS and MIN_FIT_SCORE read from prefs at import time |
| `scripts/batch_pipeline.py` | modified | score < MIN_FIT_SCORE replaces hardcoded 72 in two places |

## Retired

| Item | Reason |
|---|---|
| `profiles/scouter_preferences` SQLite key | Replaced by `profiles/job_search` |
| `profiles/preferences` SQLite key | Replaced by `profiles/job_search` |
| Hardcoded `TITLE_BLOCKLIST` in `scout_local.ts` | Now read from `candidate_preferences.json` |
| Hardcoded `SCOUT_FRESHNESS_DAYS = 7` in `scout_local.ts` | Now read from `freshness_days` in prefs |
| Hardcoded `score < 72` in `batch_pipeline.py` | Now `score < MIN_FIT_SCORE` from prefs |
| Hardcoded `JD_REQUIRED_KEYWORDS` in `utils.py` | Now bootstrapped from prefs with fallback |
| Hardcoded LinkedIn/BuiltIn/RemoteOK search URLs | Now built dynamically from prefs |
| Company-specific ACC-ID seeds in `server/index.ts` | Replaced with generic dynamic Map |
