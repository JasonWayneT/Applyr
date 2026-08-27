# IMP-CR-095: Story-Class Claim Index

**CR:** [CR-095-story-class-claim-index.md](../05-change-requests/CR-095-story-class-claim-index.md)
**Status:** Implemented 2026-08-24

## Stories

- [x] Confirm the current `we_acc_index` classification and audit error set.
- [x] Add tags-only metadata rows for every remaining indexable ACC.
- [x] Preserve the disabled ACC-114 cost claim and classify Docker personal
      use as nonclaimable.
- [x] Regenerate `master_claims_tags_only.json`.
- [x] Isolate the authoring-packet budget test from the live example bank.
- [x] Run focused tests and `audit_claims_coverage.py --strict`.
- [x] Run the complete test suite and record the result.

## Verification result

2026-08-24: strict claims audit clean. Focused integrity tests passed
(94 tests). Full unified suite passed (35 groups, 0 failures).

## Implementation note

The source of truth is `data/workExperience.md`. The catalog rows must point
back to that source through `project_id` and retrieval metadata. Do not copy
WorkExperience prose into new `text` or `cover_story` fields.
