# CR-001: Pipeline Paradigm Redesign

## Metadata
- **Status**: Approved
- **Date**: May 6, 2026
- **Author**: JobAgent (via SDD enforcement)
- **Related Requirements**: `FR-034`

## Problem
The dashboard mixes pipeline jobs (jobs pending application generation or review) with active applications (jobs formally submitted). Specifically, jobs with statuses like `Drafted`, `New`, and `Backlog` were listed under "Active Applications", cluttering the view and inflating the application metrics. Additionally, the label "Ready to Apply" was being shown for `Drafted` jobs even when PDF assets were not yet generated.

## Decision
Split the job lifecycle into distinct buckets and refine status visibility to accurately reflect the job state:

1. **Hide `Drafted`**: This status represents the system generating assets. It is not actionable for the user and should be hidden from main views, displaying only as `"Drafting…"` in the full list.
2. **"Ready to Apply" Split**: 
   - `New`: Assets are fully generated, but the user has not viewed the job yet. Display as `"Ready to Apply"` with a `New` badge.
   - `Backlog`: Assets are fully generated and the user has viewed the job, but hasn't applied. Display as `"Ready to Apply"` (no badge).
3. **Distinct Dashboard Sections**:
   - **Ready to Apply**: Shows only `New` and `Backlog` jobs.
   - **Active Applications**: Shows only `Applied`, `Recruiter Screen`, `Core Interviews`, and `Offer and Negotiation`.
4. **All Jobs View Tabs**: Update to `All | Backlog | Active | Interviewing | Closed` with filters accurately reflecting the buckets above.
5. **Dynamic Asset Checking**: Introduce a `has_assets` flag so `Drafted` or `New`/`Backlog` jobs without generated PDFs correctly show as pending instead of ready.

## Implementation Impact
- `TodayView.tsx`: Split into two lists.
- `AllJobsView.tsx`: Tab logic updated.
- `StatusChip.tsx`: Label and badge logic updated.
- `server/index.ts`: API endpoint modified to check for existing PDF files.
