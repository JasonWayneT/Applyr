# CR-026 — Job Search Evaluate-Stage Visibility

| Field | Value |
|-------|-------|
| **Status** | implemented |
| **Implements** | `FR-035`, `FR-024` |
| **Layer** | Specs + `server/` + `src/` |

## Problem

During full sync Stage 4 (`evaluate_running`), Job Search did not highlight Step 2, show batch progress (`items_completed` / `items_total`), or keep the Run button disabled. Gate rejections (`[ZERO-TOKEN REJECT]`) were logged as `ERROR`, implying failures.

## Solution

| Area | Change |
|------|--------|
| `SyncActivityView.tsx` | Treat `evaluate_running` like drafting for stepper, spinner, progress bar, button state |
| `server/scout.ts` | Log `[ZERO-TOKEN REJECT]` stderr as `INFO` (extends BUG-010) |
| `server/middleware.ts` | Include `evaluate_running` in pipeline busy set |

## Acceptance

| ID | Criterion |
|----|-----------|
| `AC-175` | While `evaluate_running`, Step 2 is active and progress shows `N/M` when `items_total > 0` |
| `AC-176` | `[ZERO-TOKEN REJECT]` lines appear as INFO in activity log |
