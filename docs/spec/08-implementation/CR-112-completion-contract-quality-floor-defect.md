---
status: implemented_pending_independent_qa
created: 2026-09-12
updated: 2026-09-12
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
related: CR-112, FR-318, AC-415
scope: Stage 2 / Stage 3 completion vs conversion-rubric floors
review_v1: independent design reviewer 793d7f71 — REVISE (folded into v2)
review_v2: same reviewer, resumed — ACCEPT WITH CHANGES (folded below)
implementation: landed on candidate after v2 ACCEPT WITH CHANGES; independent QA not yet recorded
---

# CR-112 completion contract — quality floors are not enforced

Bounded defect. Design v2 was independently reviewed before code.
Code is landed pending a fresh independent QA reviewer. Do not
recalibrate Resume 70 / Cover Letter 65. Do not bundle
practice-identity or first-draft digest work. Do not self-mark
CR-112 complete.

## Proven Camunda path (artifacts, not recollection)

Practice folder (gitignored): `data/authored_drafts/camunda_cr112_proof/`

| Artifact | What it records |
|---|---|
| `draft_manifest.json` | Canonical rubric object. Resume `total` **68**, Cover Letter `total` **69**, `verification_passed: true`. Notes state 68 is under the 70 floor and were recorded honestly. |
| `reviews/mech_findings.json` | `findings: []`. `checks.rubric_present: true`. No floor finding. |
| `reviews/dispositions.json` | Leftover `mech.rubric_score_required` → `ACCEPTED_AS_CORRECT`. That finding is **not** in the current `mech_findings.json`. It did not waive the 68. |
| `stage_receipts/stage2.json` | `COMPLETE`. `checks["contracts.check_stage2_ready"]: true`. No override. |
| `stage_receipts/stage3.json` | `COMPLETE`. `checks.practice_no_db: true`. |
| `workflow_state.json` | `mode=practice`, `status=PRACTICE_COMPLETE`, `active_stage=stage3`. |

Untouched first-draft scores (64 / 57) live in the Camunda product-proof
handoff and in `%TEMP%\camunda_baseline_*.md` (hashes
`466a7150…` / `970fa377…`). They are **not** what Stage 2 policy consumed.
`stage1_first_draft/` hashes on disk (`3b282028…` / `4aecb5a2…`) do **not**
match those baseline hashes — do not treat that folder as the immutable
baseline.

## Code path

1. `workflow/runner.py` `collect_mech_findings` sets `mech.rubric_score_required`
   (WARN) only when `draft_manifest.json` is missing or `rubric_score.resume`
   is not a dict. It does not read `.total` against 70/65.
2. That WARN is disposable. Camunda disposed it `ACCEPTED_AS_CORRECT` once
   *any* numeric totals existed.
3. `contracts.check_stage2_ready` requires `_check_rubric_score_shape`:
   both sides have a numeric `total`. No minimum. No contradiction check.
4. `run_stage2_policy` mints Stage 2 COMPLETE when `check_stage2_ready`
   returns true.
5. `run_stage3` / `--finalize` in `mode=practice` sets `PRACTICE_COMPLETE`
   without a second floor check. Production uses the same Stage 2 gate,
   then `COMPLETE` / `COMPLETE_WITH_OVERRIDE`.
6. `contracts.check_workflow_complete` returns **false** for
   `PRACTICE_COMPLETE` (`"PRACTICE_COMPLETE is not production workflow complete"`).
   Console copy already says practice finalize is not production DONE.

Existing `test_contracts.py` fixtures use Resume 78 / Cover Letter 70.
Nothing asserts a below-floor total must fail.

## Decision (investigator, corrected after review v1)

This is **both**:

- a **naming fact**: `PRACTICE_COMPLETE` already means workflow execution
  finished, not application readiness. `check_workflow_complete` is false.
- a **defect**: conversion floors are not a completion gate. Stage 2
  COMPLETE, production `check_finalize_ready`, and practice Stage 3 all
  fail open at Resume 68. Integrity stayed **CLEAN**. A production run
  would mint `COMPLETE`, not `COMPLETE_WITH_OVERRIDE`.

It is not a stale-artifact bug. The 68 is in the canonical
`draft_manifest.json`. Disposing `mech.rubric_score_required` did **not**
cause the pass: that WARN disappears as soon as `rubric_score.resume` is
a dict, even `{}`. Cover-letter totals are never read. The floor was
never a finding.

`collect_mech_findings` is weaker than `check_stage2_ready` shape: a
resume object with no `total` can clear the WARN while Stage 2 policy
still fails on shape. Camunda had a real numeric 68, so both gates
passed.

## Expected product behavior (Jason, this session)

- A document below its applicable floor cannot be called ready silently.
- Stronger grounded evidence unused → return to selection or authoring
  (out of scope for this story).
- Adequate evidence, weak expression → bounded revision (out of scope
  for this story's first patch; Stage 2 should still refuse COMPLETE).
- Truthful evidence cannot reach the floor → explicit reviewed exception.
- Never pad, exaggerate, widen attribution, or force a large metric.
- Missing, unreadable, stale, or contradictory quality results fail closed.

Keep floors provisional: Resume 70, Cover Letter 65. They are gates, not
targets.

## Smallest recovery contract (v2 — after REVISE)

Independent review v1 (`793d7f71`): **REVISE**. Putting floors *and* a
disposition read into `check_stage2_ready` fights a locked CR-075
predicate (policy already says that function is not disposition-gated).
Agent-writable `HUMAN_ACCEPTED_RISK` would recreate a silent pass.
Practice Stage 3 never calls `check_finalize_ready`. Floor-only in Stage 2
leaves `finalize_submission_job` fail-open.

**This story has no exception path.** Fail closed. `--force` / HAR /
`COMPLETE_WITH_OVERRIDE` are a later story. Do not describe an
agent-writable ledger as Jason review.

**Chosen gates (explicit):**

1. Shared numeric floor helper next to `_check_rubric_score_shape` in
   `contracts.py`: Resume 70, Cover Letter 65. Call it only after shape
   is valid. Name the side and the floor in the error. Do not parse notes.
2. Use that helper from `_check_rubric_score_shape`'s callers that already
   mean "this score is the completion score": `check_draft_manifest`,
   `check_finalize_ready`, and `check_stage2_ready`. One helper, same
   numbers, no disposition I/O in `contracts.py`.
3. Practice `run_stage3_finalize` must call the same helper (or
   `check_finalize_ready` minus the production DB-write extras that
   practice is allowed to skip). Camunda's proven path cannot remain
   exempt because it skips `check_finalize_ready` today.
4. `collect_mech_findings` emits BLOCK `mech.rubric_floor.resume` /
   `mech.rubric_floor.cover_letter` when a numeric total is below floor,
   so a below-floor run cannot stay integrity CLEAN through Mech. Presence
   WARN `mech.rubric_score_required` stays as-is (missing object only).
   A leftover `ACCEPTED_AS_CORRECT` on that WARN must never satisfy a
   floor BLOCK.
5. Do not read `dispositions.json` from `check_stage2_ready`. Policy
   stays: `check_stage2_ready` must pass; no disposing `policy.stage2_ready.*`.
6. Do not change `PRACTICE_COMPLETE` naming. Practice still must not
   write the production jobs DB. `check_workflow_complete` stays false
   for practice.

### Negative controls (must exist before the patch is called done)

- Resume 68 / Cover Letter 69, otherwise Stage-2-ready →
  `check_stage2_ready` false.
- Same fixture → `check_finalize_ready` false; practice Stage 3 must not
  mint `PRACTICE_COMPLETE`.
- Resume 70 / Cover Letter 65 → both ready predicates true.
- Resume 69.9 / Cover Letter 65 → false (resume).
- Resume 70 / Cover Letter 64 → false (cover letter).
- Missing `rubric_score` still fails on shape, not on floor.
- `ACCEPTED_AS_CORRECT` on leftover `mech.rubric_score_required` does
  not clear a floor BLOCK.
- CLEAN complete at Resume 68 is impossible in either mode.

### Exception (explicitly deferred)

None in this story. A later story may add `--force` that cannot mint
CLEAN `COMPLETE` / CLEAN `PRACTICE_COMPLETE`. Do not add HAR-as-Jason-review.

## Out of scope

- Recalibrating 70/65.
- Auto-looping into authoring or evidence selection.
- Practice-identity / placeholder header.
- Digest completeness / LW-009-PAIR prompt line.
- Rebuilding Camunda or SupplyHouse.
- Treating `PRACTICE_COMPLETE` as production `COMPLETE`.

## Do not fix by

Lowering the resume floor to 68 because Camunda landed there; treating
practice as exempt; stuffing the floor into `--audit` history matching
only; parsing rubric notes; requiring Jason to click a UI; using
`--force` finalize as the silent exception.
