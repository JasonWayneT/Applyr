# CR-033 — Built In Detail-Page JD Before Ingest Gates

## Status

accepted

## Problem

Built In listing cards only expose title, company, and URL. Scout stored `description: ''` and geographic/seniority gates ran on title-only stubs. Remote-only seekers hit `remote_only_no_location_signal` (FR-173) before `scrape_new_jobs.ts` could open the job page.

## Goal

For each new Built In candidate, open the **job detail URL**, extract the full job description, then run industry, geographic, and seniority gates on that text. Persist `jd_text` and staging `jobs/*.txt` when ingest succeeds.

## Requirements

| ID | Summary |
|---|---|
| `FR-180` | Built In detail-page JD fetch before ingest gates |
| `AC-183` | Given a new Built In URL, when scout runs, then JD length ≥ 200 chars is required before save; geo/seniority use full text |

## Implementation

| File | Change |
|---|---|
| `scripts/extract_job_page.ts` | Shared Playwright JD extraction (Built In selectors + fallbacks) |
| `scripts/scout_local.ts` | `scoutBuiltIn` calls detail fetch; insert `jd_text`; write staging file → `Drafted` |
| `scripts/scrape_new_jobs.ts` | Reuse shared extractor |

## Out of scope

- Levels.fyi detail fetch (separate CR if needed)
- Keyword/anchor gates at scout (remain in `batch_pipeline.py`)
