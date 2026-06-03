# Feature Spec: FEAT-001 Scouting & Ingestion

## Metadata

- Feature ID: `FEAT-001`
- Status: implemented
- Source artifacts: `BMAD-SRC-001`, `BMAD-SRC-004`
- Related requirements: `FR-001`, `FR-002`, `FR-003`, `FR-004`, `FR-005`, `FR-109`, `FR-135`, `FR-147`, `FR-170`, `FR-173`, `FR-180`, `FR-181`, `FR-182`, `FR-183`, `FR-184`, `FR-185`, `FR-186`, `FR-187`, `FR-194`
- Related change requests: `CR-010`, `CR-019`, `CR-021`, `CR-027`, `CR-028`, `CR-033`, `CR-034`, `CR-041`
- **Runtime workflow:** [docs/ACTIVE_WORKFLOW.md](../../../ACTIVE_WORKFLOW.md)

## Problem statement

Finding relevant job postings across multiple siloed platforms is repetitive. The WebApp triggers automated scouting via `server/scout.ts` → `scripts/scout_local.ts`.

## Goals

- `GOAL-001`: Automatically extract job metadata (Title, Company, URL, Description).
- `GOAL-002`: Consolidate multi-source data into SQLite (`jobagent.sqlite`).
- `GOAL-003`: Prevent processing duplicate jobs across sync cycles.

## Users and stories

| Story ID | Priority | User story | Related requirements |
|---|---|---|---|
| `STORY-001` | P0 | As a job seeker, I want the system to scout BuiltIn, APIs, and optional OpenPostings so I do not scroll boards manually. | `FR-001` |
| `STORY-002` | P1 | As a developer, I want to pull from the OpenPostings database for bulk leads. | `FR-002` |

> **Note:** LinkedIn browser scouting was decommissioned in CR-010 (`FR-080`). Logs: `LinkedIn: Bypassed`.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-001` | Multi-source discovery | Playwright (Built In, Levels.fyi) + 10 API/RSS sources: OpenPostings, Remotive, RemoteOK, WWR, Himalayas, The Muse, Adzuna, Jobicy, Working Nomads, JobsCollider |
| `FR-002` | OpenPostings scraper | External SQLite |
| `FR-003` | Deduplication | URL hashing in SQLite |
| `FR-080` | LinkedIn decommission | No requests to linkedin.com in routine runs |
| `FR-135` | Scout-time seniority gate | Title blocklist + max-years (`CR-021`) |
| `FR-147` | ATS watchlist | Optional `data/ats_watchlist.json` or `config/ats_watchlist.json` (user-owned only) |
| `FR-194` | No example watchlist at runtime | `ats_watchlist.example.json` is template-only (`CR-041`) |
| `FR-170` | Industry blocklist gate | `passesIndustryGate()` (`CR-027`) |
| `FR-173` | Levels.fyi + Remote geo | `CR-028` |
| `FR-180` | Built In detail-page JD before gates | `CR-033` — `extract_job_page.ts`, `scoutBuiltIn()` |
| `FR-181` | Built In listing location signal carry-through | `CR-034` — strict geo policy retained, no source bypass |
| `FR-182` | Built In strict seed URL targeting | `CR-034` — single strict PM remote US mid-level target URL |
| `FR-183` | Built In card pre-fetch filters | `CR-034` — PM title scope + strict remote card before detail fetch |
| `FR-184` | Jobicy API source | Official free public JSON API (`jobicy.com/api/v2/remote-jobs`), `geo=usa` filter, per-term tag search |
| `FR-185` | Working Nomads JSON API source | Public endpoint (`workingnomads.com/api/exposed_jobs/`), client-side PM category + `passesBroadPmTitleScope` filter |
| `FR-186` | JobsCollider RSS source | Hourly RSS feed (`remotefirstjobs.com/remote-product-jobs.rss`), `passesBroadPmTitleScope` filter, "Title at Company" slug parse |
| `FR-187` | Broad PM title scope gate | `passesBroadPmTitleScope()` in `scout_local.ts` — blocks product marketing, design, analytics from general-category feeds |

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-001` | `FR-001` | Saved job-search prefs | Scout/sync runs | New jobs appear in SQLite with URLs and metadata |
| `AC-004` | `FR-003` | A job URL already exists in DB | Ingestion runs | The job is ignored/skipped |
| `AC-080` | `FR-080` | Routine scout | `scout_local.ts` runs | LinkedIn phase is skipped; no linkedin.com requests |

## Implementation tasks

| Task ID | Requirement IDs | Description | Status |
|---|---|---|---|
| `TASK-001` | `FR-001` | `scout_local.ts` multi-source scout | done |
| `TASK-002` | `FR-002` | OpenPostings connector | done |
| `TASK-003` | `FR-080` | LinkedIn bypass / decommission | done |
| `TASK-004` | `FR-184` | Jobicy API source — `scoutJobicy()` | done |
| `TASK-005` | `FR-185` | Working Nomads API source — `scoutWorkingNomads()` | done |
| `TASK-006` | `FR-186` | JobsCollider RSS source — `scoutJobsCollider()` | done |
| `TASK-007` | `FR-187` | `passesBroadPmTitleScope()` helper + `REMOTE_ONLY_SOURCES` update | done |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-001` | `FR-001` | manual | Scout log shows active sources (not LinkedIn) | verified |
| `TEST-080` | `FR-080` | manual | Log contains `LinkedIn: Bypassed` | verified |
