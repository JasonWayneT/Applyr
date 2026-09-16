# CR-113 Rubric Scorecard Metadata Gate

Status: implemented
Created: 2026-09-16
Related: CR-112, FR-322, AC-420

## Problem

CR-112 Story 8.6 made rubric scores hash-bound and fail-closed on boundary-band disagreement. The remaining readiness gap is that `reviews/rubric_scorecard.json` rows can still satisfy completion with weak metadata: missing or stale rubric hash, missing timestamp, empty per-criterion breakdown, or no reviewer-run identity.

That is not strong enough for `DAILY_USE_READY`, because a future operator cannot tell whether a score was actually produced against the current rubric, when it was scored, or what reviewer run produced it.

## Scope

Implement the smallest safe completion-gate improvement:

- require `schema_version: 1`;
- require `rubric_sha256` to match the current `data/conversion_rubric.md`;
- require timezone-qualified `scored_at`;
- require reviewer-run metadata through `reviewer_run_id` or `spawned_by`;
- require complete numeric per-criterion breakdowns:
  - Resume: `R1` through `R8`;
  - Cover letter: `C1` through `C5`;
- reject unknown criterion keys, booleans, non-finite values, negative values, and values above the current rubric maximum;
- require each breakdown sum to match its document total.

## Non-goals

- No PDF lineage changes.
- No new scoring model or provider call.
- No lowered score floors.
- No averaging, majority vote, or higher-score selection.
- No production SQLite or submission mutation.

## Acceptance

- Current-hash scorecard rows missing any required metadata fail Stage 2 completion.
- Existing hash, floor, boundary-band, and disagreement behavior remains unchanged.
- Focused offline tests cover missing schema version, stale rubric hash, bad timestamp, missing reviewer-run metadata, incomplete breakdown, boolean criterion values, over-maximum criterion values, and breakdown totals that do not match document totals.

## Verification

Implemented by:

- `scripts/contracts.py`
- `scripts/test_contracts.py`
- `scripts/test_workflow_authority.py`

Verified by local unittest suites (`scripts.test_contracts` and `scripts.test_workflow_authority`) and the CR-113 readiness integration run.
