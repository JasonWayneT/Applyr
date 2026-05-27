# BUG-014: Stale and Duplicate Folders in submissions/

## Metadata
- **Status**: Fixed
- **Severity**: P2
- **Component**: `server/routes/jobs.ts`, `server/submissionFolders.ts`, `scripts/reconcile_submissions.py`
- **Related requirements**: `FR-030`, `FR-034`

## Description
Applied and Closed jobs often left folders in `submissions/` after status changes. When an archive folder already existed, `renameSync` was skipped silently, producing duplicates (e.g. `roadie`, `zumper`, `vikar`). Partial pipeline stubs (JD + research only) also accumulated with no matching Backlog row. `has_assets` only checked `submissions/`, so archived PDFs were invisible to the UI.

## Fix
- `archiveActiveSubmission()` merges active → archive when both exist, then deletes the active folder.
- `restoreArchivedSubmission()` mirrors merge behavior when moving back to Backlog/Drafted.
- `reconcileActiveSubmissionFolders()` runs on server startup and via `POST /api/jobs/reconcile-submissions`.
- `jobHasPdfAssets()` resolves PDFs from archive for non-active statuses.
- `scripts/reconcile_submissions.py` provides a manual one-shot cleanup.
