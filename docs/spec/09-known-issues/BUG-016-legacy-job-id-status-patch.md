# BUG-016: Mark as Applied Fails for Legacy Job IDs

## Metadata

- Bug ID: `BUG-016`
- Status: fixed
- Severity: high
- Component: `server/middleware.ts`, `server/routes/jobs.ts`
- Related requirements: `FR-030`, `SEC-001` (CR-025 regression)

## Description

Marking a job as Applied (or any `PATCH /api/jobs/:id/status` transition) fails in the UI with "Failed to update status" when the job row uses a legacy id (e.g. `a9a2f050`, `linq_product_manager`) instead of a UUID.

## Root cause

CR-025 added `isValidJobId()` restricted to UUID format only. Most existing rows in `jobagent.sqlite` use legacy scout/pipeline ids. The status route returned HTTP 400 `Invalid job id` before reading the database.

## Fix

Allow alphanumeric legacy ids (with `_` and `-`), max 128 chars, while still rejecting `..`, `/`, and `\` for path safety.

## Verification

`PATCH /api/jobs/a9a2f050/status` with body `{ "status": "Applied" }` succeeds for Velera Backlog row; submission folder archives under `archive/submissions/velera`.
