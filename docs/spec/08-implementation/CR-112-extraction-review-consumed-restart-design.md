---
status: accepted_with_changes
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
related: CR-112, FR-320, AC-418
design_review: 221eed13-6cf1-45e0-ba82-14c298ba0877
verdict: ACCEPT WITH CHANGES
---

# Story: durable consumed extraction-review on Stage 0 restart

## Recurring defect (Vanta JD 2, confirmed)

`data/authored_drafts/vanta_cr112_proof/observability/run_events.jsonl`:

1. `18:44:44` `pause_kind=requirement_extraction_review` (queue_size 18)
2. Live import answered; consume renamed live → `.consumed.json`
3. `18:45:39` `pause_kind=cost_authorization`
4. `18:46:31` Stage 0 restart for the cost pause **re-asked extraction review**
5. Restoring the consumed file onto the live import name unblocked it
6. `18:47:31` Stage 0 complete

Root cause, not a guess: `try_load_review_import` reads only
`stage0_requirement_extraction_review.json`. `consume_review_import`
renames that file to `.consumed.json`. A later `build_stage0_fit_gate`
call (cost-authorization `--resume` re-enters Stage 0 from the start)
sees no live file, treats the review as unanswered, and re-pauses.

The canonical stage0 receipt / consumed file / checkpoint is not
sufficient on restart because load never consults consumed.

## Locked contract

- A valid consumed extraction review is durable and idempotent.
- `--resume` with unchanged JD + unchanged qualification-risk queue must
  apply the consumed buckets and must not request the same review again.
- The consumed file must not need to be copied back to the live name.
- Stale JD (`jd_sha256` mismatch), changed queued item text/count/keys,
  or a new live import (deliberate correction) may require a new review.
- Repeated resume without changed inputs must not fork receipts or
  duplicate the consumed payload.
- Corrupt or unreadable consumed JSON fails closed with
  `RequirementExtractionReviewValidationError` (actionable), not a
  silent first-time pause.
- A mismatched consumed file must not apply old buckets. Re-pause is
  allowed when the message/template makes clear the prior review is
  stale. Do not auto-apply.
- Live import, when present and valid, wins over consumed (correction).

## Smallest correction

`try_load_review_import`:

1. If live exists, validate it (current rules). Invalid live keeps
   today's re-pause behavior (do not crash a bad in-progress answer).
2. If live is absent and consumed exists, validate consumed with the
   same slug / jd_sha256 / exact-text / full-index rules.
   - Valid → return the bucket map. Do not require restoring live.
   - Corrupt → raise `RequirementExtractionReviewValidationError`.
   - Binding mismatch → return `None` so the existing pause/template
     path fires (new review). Do not apply stale buckets.
3. If neither exists → `None` (first pause), unchanged.

`consume_review_import` stays a live→consumed rename. A restart that
only has consumed must not delete or rewrite consumed.

Do not load consumed for a different slug. Do not weaken exact-text
binding. Do not skip the qualification-risk gate. No ranking/digest
change. No cascade-import change in this story unless the reviewer
finds the same live-only load is in scope; cascade already requires a
new live file on cost resume by design (the cost pause's next input).

## Tests (red before the fix)

`scripts/test_cr112_stage0_extraction_review.py`
`TestConsumedReviewDurableOnRestart`

- Third `build_stage0_fit_gate` after consume, no live file, same JD/queue
  → applies consumed buckets, does not raise
  `Stage0RequirementExtractionReviewNeeded`
- New live after consume can change the bucket (correction)
- Consumed `jd_sha256` mismatch → re-pause, does not apply
- Changed queued text → re-pause, does not apply
- Corrupt consumed JSON → `RequirementExtractionReviewValidationError`

## Out of scope

Ranking formula. Digest restatement instruction. Cascade consumed
load (cost import is the next pause's input, not a prior consumed
review). Production sqlite. Paid calls.
