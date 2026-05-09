# Feature Spec: FEAT-009 Unified Job Search Settings

## Metadata

- Feature ID: `FEAT-009`
- Status: implemented
- Source artifacts: User Request
- Related requirements: `FR-046`, `FR-047`, `FR-048`, `FR-049`
- Supersedes: `FR-042` (partial), `FR-044` (partial)
- Change request: `CR-003`

## Problem statement

Scout criteria and candidate preferences were fragmented across four disconnected data islands:
`profiles/scouter_preferences` (SQLite), `profiles/preferences` (SQLite), `data/candidate_preferences.json`
(static file read by Python), and hardcoded values in `server/config.ts` and `scripts/scout_local.ts`.
Changes made in the UI had no effect on actual scouting or pipeline evaluation because no write path
connected the UI to the file the pipeline reads. The scouter parameters panel also contained controls
(experience level, job type, location) that saved to the database but were never consumed by any scout.

## Goals

- `GOAL-001`: Establish a single source of truth for all scout and pipeline parameters.
- `GOAL-002`: Make every UI-visible setting functionally effective on the next scout run.
- `GOAL-003`: Replace hardcoded search terms, URLs, and thresholds in scripts with runtime reads from preferences.
- `GOAL-004`: Make the ACC-ID codification engine generic enough for any user's work history.

## Users and stories

| Story ID | Priority | User story | Related requirements |
|---|---|---|---|
| `STORY-009-01` | P0 | As a job seeker, I want to change my target role in the UI and have the next scout run search for that role, not "Product Manager" forever. | `FR-046`, `FR-048` |
| `STORY-009-02` | P0 | As a job seeker, I want to set my experience level filter once and have it apply across all scout sources. | `FR-048` |
| `STORY-009-03` | P0 | As a job seeker, I want my blocklists in the UI to actually reject jobs, not just sit in a field that nothing reads. | `FR-046`, `FR-047` |
| `STORY-009-04` | P1 | As a new user, I want my work experience sections to get correctly numbered IDs regardless of how many employers I've had. | `FR-049` |

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-046` | Unified Job Search Settings Panel | Replaces `profiles/scouter_preferences` + `profiles/preferences` with single `profiles/job_search` key |
| `FR-047` | Preference Materialization to JSON | Server writes `candidate_preferences.json` on every `POST /api/profile/job_search` |
| `FR-048` | Dynamic Scout URL Construction | All source URLs and search terms built at runtime from preferences |
| `FR-049` | Generic ACC-ID Codification | Employer sections 5.N receive range N×100+1 dynamically, no hardcoded seeds |

## Architecture

### Data flow

```
User changes setting in Job Search tab
    → POST /api/profile/job_search
    → server saves to profiles table (key = 'job_search')
    → server calls materializeJobSearchPrefs()
    → writes data/candidate_preferences.json
    → next scout run reads candidate_preferences.json
    → next pipeline run reads candidate_preferences.json
```

### Retired keys

The following SQLite profile keys are retired and no longer written or read:
- `profiles/scouter_preferences` — replaced by `profiles/job_search`
- `profiles/preferences` — replaced by `profiles/job_search`

### Materialization mapping

| UI field (camelCase) | JSON field (snake_case) | Transformation |
|---|---|---|
| `targetRole` | `target_role` | Direct |
| `targetRole` | `search_terms` | Array; "Product Owner" added if role contains "product manager" |
| `workSetting` | `work_setting` | Direct |
| `location` | `location_preference` | Direct |
| `experienceLevels` | `experience_levels` | Direct (array) |
| `datePosted` | `date_posted` | Direct |
| `datePosted` | `freshness_days` | Mapped: "Past 24 hours"→1, "Past 3 days"→3, "Past week"→7, "Past month"→30 |
| `titleBlocklist` | `blocked_titles` | Split on comma, trim, filter empty |
| `industryBlocklist` | `blocked_industries` | Split on comma, trim, filter empty |
| `minSalary` | `min_salary` | Direct |
| *(not in UI)* | `min_fit_score` | Preserved from existing JSON; default 72 |
| *(not in UI)* | `jd_required_keywords` | Preserved from existing JSON; default list |
| *(not in UI)* | `experience_range` | Preserved from existing JSON |
| *(not in UI)* | `preferences` | Preserved from existing JSON |

### Scout source dynamic parameters

| Source | What is now dynamic |
|---|---|
| LinkedIn | Search terms, geo ID (from location), f_WT (from workSetting), f_E (from experienceLevels), f_TPR (from freshness_days) |
| BuiltIn | URL path prefix (remote/hybrid/on-site), experience[] params (from experienceLevels), days_since_posted (from freshness_days) |
| OpenPostings | Search term (from search_terms), remote param (from workSetting) |
| RemoteOK | Tags param (from target_role) |
| Remotive | Category (product — static for now, expandable) |
| WWR | RSS category (static for now, expandable) |

## UI layout

### Primary card — Search Targeting

4-column grid (responsive to 1-col on mobile):
- **Target Role** — text input with helper text
- **Work Setting** — 3-chip selector (Remote / Hybrid / On-site)
- **Location** — dropdown select (5 pre-mapped options)
- **Date Posted** — 2×2 chip grid (Past 24h / Past 3d / Past week / Past month)

Full-width row below:
- **Experience Level** — multi-select dropdown with checkboxes; "Any level" default

### Secondary card — Gate Filters

3-column grid:
- **Title Blocklist** — textarea, comma-separated
- **Industry Blocklist** — textarea, comma-separated
- **Minimum Salary** — number input with $ prefix

### Removed from Profile tab

The "Preferences" sub-tab (`minSalary`, `environment`, `titleBlocklist`, `industryBlocklist`) is removed entirely. All these fields now live in the Job Search tab's Gate Filters card.

## ACC-ID codification — generic algorithm

For a document with employer subsections `### 5.1` through `### 5.N`:
- Section `5.N` receives ACC IDs in the range `[N×100+1, (N+1)×100]`
- A `Map<string, number>` tracks the next available ID per section
- A pre-scan reads existing ACC-NNN patterns to seed counters above existing maxima (collision prevention)
- No hardcoded company names, employer counts, or starting offsets

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-047` | `FR-047` | User sets targetRole to "Technical Program Manager" and saves | Server receives POST /api/profile/job_search | `data/candidate_preferences.json` is rewritten with `target_role: "Technical Program Manager"` within 1 second |
| `AC-048` | `FR-048` | `candidate_preferences.json` has `experience_levels: ["Mid Level (2-5 Years)"]` | Scout runs | LinkedIn URL includes `f_E=4` and BuiltIn URL includes `experience%5B%5D=mid-level` |
| `AC-049` | `FR-049` | `workExperience.md` contains subsections `### 5.1` through `### 5.4` | User saves experience | Each section receives IDs in its own 100-number range; no collisions |
| `AC-050` | `FR-046` | No `job_search` profile record exists in SQLite | Job Search tab loads | Default values are shown matching current `candidate_preferences.json` |
| `AC-051` | `FR-046` | User sets Title Blocklist to "Senior, VP, Director" and saves | Next scout run triggers | `blocked_titles` in `candidate_preferences.json` is `["Senior", "VP", "Director"]` and those titles are rejected in pre-filter |

## Implementation tasks

| Task ID | Requirement IDs | Description | Status |
|---|---|---|---|
| `TASK-009-01` | `FR-047` | Add `materializeJobSearchPrefs()` to `server/index.ts` | done |
| `TASK-009-02` | `FR-047` | Add `POST /api/profile/job_search` specific route before generic `:key` route | done |
| `TASK-009-03` | `FR-046` | Rewrite `SyncActivityView.tsx` with unified `JobSearchSettings` state, primary + secondary cards | done |
| `TASK-009-04` | `FR-046` | Remove Preferences sub-tab from `ProfileView.tsx` | done |
| `TASK-009-05` | `FR-046` | Rename "Scout" → "Job Search" in sidebar and App.tsx routing | done |
| `TASK-009-06` | `FR-048` | Add preference-loading block to `scout_local.ts`; add `buildLinkedInUrl()` and `buildBuiltInUrl()` | done |
| `TASK-009-07` | `FR-048` | Update all scout source calls to use dynamic terms and URLs | done |
| `TASK-009-08` | `FR-048` | Add `MIN_FIT_SCORE` and `JD_REQUIRED_KEYWORDS` bootstrap from prefs in `utils.py` | done |
| `TASK-009-09` | `FR-048` | Replace hardcoded `score < 72` with `score < MIN_FIT_SCORE` in `batch_pipeline.py` | done |
| `TASK-009-10` | `FR-049` | Rewrite `codifyExperienceAndAssignIDs()` with dynamic section Map | done |
| `TASK-009-11` | `FR-046` | Update `data/candidate_preferences.json` to unified schema | done |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-009-01` | `AC-047` | manual | Change targetRole in UI, save, open `data/candidate_preferences.json`, confirm `target_role` matches | accepted |
| `TEST-009-02` | `AC-048` | manual | Set experience level to Mid Level, run scout, check log for BuiltIn URL with `experience%5B%5D=mid-level` | accepted |
| `TEST-009-03` | `AC-049` | manual | Add a `### 5.4` section to workExperience, save, confirm new bullets receive `ACC-401+` IDs | accepted |
| `TEST-009-04` | `AC-051` | manual | Set title blocklist to "CTO, Staff", run scout, confirm those titles appear as `[REJECT]` in log | accepted |
