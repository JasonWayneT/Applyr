# CR-011: Pipeline Status Vocabulary and Auto-Requeue

## Metadata

- **Status**: Approved
- **Date**: May 19, 2026
- **Related Requirements**: `FR-035`, `FR-045`, `FR-034`

## Problem

1. DB status `Failed` reads like a system outage; most rows are retryable eval/draft errors, not user-facing "bad fit."
2. Gatekeeper rejects are removed from `jobs` into `stale_jobs` only — users cannot see "Not a fit" history in Opportunities.
3. `Needs Retry` jobs are not automatically returned to the pipeline on the next sync.

## Decision

| DB status | UI label | Meaning |
|-----------|----------|---------|
| `Rejected` | Not a fit | Keyword gate or score below threshold |
| `Needs Retry` | Needs retry | LLM/draft/PDF error; auto-requeued on sync (max 3 attempts) |
| `Failed` | *(deprecated)* | Migrated to `Needs Retry` on server boot |

### Auto-requeue (before scrape each sync)

For each `Needs Retry` job with `retry_count < 3`:

1. If `submissions/<company>/Original_JD.txt` exists → write `jobs/<Company>_<id8>.txt`, set `Drafted`.
2. Else if `url` present → set `New` for `scrape_new_jobs.ts`.
3. Else skip (log).

Exhausted retries remain `Needs Retry` and are not requeued.

## Implementation

- `scripts/requeue_needs_retry.ts` — requeue script
- `server/scout.ts` — run requeue at start of scrape stage
- `scripts/batch_pipeline.py` — `Rejected` / `Needs Retry`, `retry_count`
- `server/db.ts` — `retry_count` column + `Failed` → `Needs Retry` migration
- UI: `StatusChip`, `AllJobsView`, `job.ts`
