# Feature Spec: FEAT-001 Scouting & Ingestion

## Metadata

- Feature ID: `FEAT-001`
- Status: implemented
- Source artifacts: `BMAD-SRC-001`, `BMAD-SRC-004`
- Related requirements: `FR-001`, `FR-002`, `FR-003`, `FR-004`, `FR-005`, `FR-109`, `FR-135`, `FR-147`, `FR-170`, `FR-173`
- Related change requests: `CR-010`, `CR-019`, `CR-021`, `CR-027`, `CR-028`
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
| `FR-001` | Multi-source discovery | Playwright (BuiltIn, Levels.fyi) + public APIs |
| `FR-002` | OpenPostings scraper | External SQLite |
| `FR-003` | Deduplication | URL hashing in SQLite |
| `FR-080` | LinkedIn decommission | No requests to linkedin.com in routine runs |
| `FR-135` | Scout-time seniority gate | Title blocklist + max-years (`CR-021`) |
| `FR-147` | ATS watchlist | Optional `config/ats_watchlist.json` |
| `FR-170` | Industry blocklist gate | `passesIndustryGate()` (`CR-027`) |
| `FR-173` | Levels.fyi + Remote geo | `CR-028` |

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

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-001` | `FR-001` | manual | Scout log shows active sources (not LinkedIn) | verified |
| `TEST-080` | `FR-080` | manual | Log contains `LinkedIn: Bypassed` | verified |
