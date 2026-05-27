# BUG-012: Sync Shows "Stage Error" While Pipeline Log Shows Progress / Done

## Metadata

- Bug ID: `BUG-012`
- Status: fixed
- Severity: high
- Component: `server/scout.ts`, `scripts/batch_pipeline.py`
- Related requirements: `FR-035`, `FR-045`

## Description

The Scout activity log continues to show per-job pipeline progress (including JSON `"status": "done"` lines from fit/gate steps) while the UI displays **"Sync stopped due to stage error."** Users interpret this as a successful run with a broken status indicator.

## Root cause

1. `runScoutSync` treats **any non-zero exit code** from Stage 4 (`batch_pipeline.py`) as a fatal stage failure and sets a generic idle message.
2. `batch_pipeline.py` had **no per-job try/except** around `run_drafting_engine()`. A single `ValueError` from resume QA (e.g. local model output missing `PROFESSIONAL SUMMARY` after Gemini 429) crashed the entire Python process with exit code `1`.
3. `handleStderr` in `scout.ts` classified benign lines (e.g. `[LLM Notice]`, `[QA AUDIT PASS]`, `Successfully audited`) as `ERROR`, cluttering the log.

## Fix

1. Wrap drafting in per-job try/except; mark job `Failed` and continue the batch.
2. Set `Backlog` only when required PDFs exist on disk.
3. Exit batch with code `0` after the queue is drained (partial per-job failures are logged, not fatal).
4. Surface the actual stage error in `system_status.current_item` (e.g. `Sync stopped: Evaluation stage exited with non-zero code 1`).
5. Improve stderr routing for notices and success lines.

## Verification

- Trigger a resume QA failure on one job; confirm remaining `jobs/*.txt` files continue processing.
- Confirm `system_status` shows completed when the batch finishes with only per-job failures.
- Confirm UI message includes the specific stage error when the process still aborts catastrophically.
