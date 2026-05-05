# Feature Spec: FEAT-001 Scouting & Ingestion

## Metadata

- Feature ID: `FEAT-001`
- Status: implemented
- Source artifacts: `BMAD-SRC-001`, `BMAD-SRC-004`
- Related requirements: `FR-001`, `FR-002`, `FR-003`, `FR-004`, `FR-005`

## Problem statement

Finding relevant job postings across multiple siloed platforms (LinkedIn, BuiltIn, company career pages) is a repetitive, manual task that is difficult to scale without automation.

## Goals

- `GOAL-001`: Automatically extract job metadata (Title, Company, URL, Description).
- `GOAL-002`: Consolidate multi-source data into a single local ingestion queue.
- `GOAL-003`: Prevent processing duplicate jobs across different sync cycles.

## Users and stories

| Story ID | Priority | User story | Related requirements |
|---|---|---|---|
| `STORY-001` | P0 | As a job seeker, I want the system to check LinkedIn for me so I don't have to scroll manually. | `FR-001` |
| `STORY-002` | P1 | As a developer, I want to pull from the OpenPostings database to get a massive head start on leads. | `FR-002` |

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-001` | Multi-source discovery | Uses Playwright/Chromium |
| `FR-002` | OpenPostings scraper | Reads from external SQLite |
| `FR-003` | Deduplication | Uses URL hashing |

## Acceptance criteria

| AC ID | Requirement ID | Given | When | Then |
|---|---|---|---|---|
| `AC-001` | `FR-001` | Valid session cookies | Scout is triggered | 20+ new job leads are pulled from LinkedIn |
| `AC-004` | `FR-003` | A job URL already exists in DB | Ingestion runs | The job is ignored/skipped |

## Implementation tasks

| Task ID | Requirement IDs | Description | Status |
|---|---|---|---|
| `TASK-001` | `FR-001` | Implement LinkedIn Playwright script | done |
| `TASK-002` | `FR-002` | Implement OpenPostings SQLite connector | done |

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-001` | `FR-001` | manual | CLI logs show "Found 25 jobs on LinkedIn" | verified |
