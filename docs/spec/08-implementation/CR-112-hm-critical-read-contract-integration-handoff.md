---
title: CR-112 HM Critical-Read Contract — Integration Handoff (Story 8.3 + 8.3.1)
created: 2026-09-16
author: Factory (Droid)
branch: cr112-hm-critical-read-contract
status: ACCEPTED — READY FOR INTEGRATION REVIEW (Factory implementation stopped)
commits:
  - 507855b — CR-112 Story 8.3: HM critical-read disposition substance contract
  - a9b5d99 — CR-112 Story 8.3.1: receipt-derived RESOLVED_EDIT edit proof
base: c254524
final_qa: PASS (worker subagent session f1ebb434-d2ca-4455-a87c-b4b7b498aa0b, bypass-focused, unqualified)
audience: Cursor (integrate both commits in order after its own closeout)
---

# CR-112 HM Critical-Read Contract — Integration Handoff

Factory stops implementation here. Integrate `507855b` then `a9b5d99` in order
(never `a9b5d99` alone — it depends on Story 8.3's validator and runner wiring).

## 1. Original defect (before Story 8.3)

`hm.critical_read` is a WARN finding confirming a hiring-manager read of
Resume.md + CoverLetter.md. It could be cleared with a bare `RESOLVED_EDIT`
string, a 10-char filler disposition, generic templated reasoning naming no
document content, no JD reference, no reviewer identity, a no-op edit, or a
fabricated location. The Stage 0/1 receipt hash chain already caught staleness;
the gap was **substance** — nothing proved a qualitative read occurred.

## 2. Story 8.3 — structured review contract (`507855b`)

Adds `scripts/hm_review_contract.py` (`validate_hm_review`): requires a
structured `hm_review` artifact per disposition — `reviewed_document_hashes`
matching on-disk Resume.md/CoverLetter.md/Original_JD.txt, declared
`reviewer_role` enum (`author`/`reviewer`/`human_reviewer`) with a
role-disposition matrix, ISO-8601 timezone-aware timestamp (rejects naive and
>1h-future), >= 2 observations with verbatim `document_span`/`jd_span`
substring checks, verdict-disposition consistency, >= 20-char reasoning, and
`resolution_summary` for RESOLVED_EDIT. `NOT_APPLICABLE`/`FALSE_POSITIVE` are
disallowed for `hm.critical_read` via `policy.py` (single source of truth
import). Runner wires the call in `_apply_subphase_verdict` (HM phase only,
after policy PASS). Design: `CR-112-hm-critical-read-contract-design.md`.
QA (round 2, pre-8.3.1): final QA PASS recorded in
`CR-112-hm-critical-read-contract-qa-review-final.md`, commit `5f30f2d`
(amended as `507855b`).

## 3. Post-QA discovery — self-reported priors not authoritative

`507855b`'s RESOLVED_EDIT proof required payload `prior_document_hashes` to
differ from `reviewed_document_hashes`. The round-2 QA flagged this as
non-blocking observation #3 ("self-reported... a reviewer who didn't edit
anything could fabricate a prior hash") and PASSed. Jason subsequently
confirmed it as a **material** gap: an agent can invent a prior hash with no
edit having occurred. The historical QA record stands (507855b initially passed
QA and was later found to have a material gap) — see the POST-QA CORRECTION
addendum in `CR-112-hm-critical-read-contract-qa-review-final.md`. Do not
rewrite that record.

## 4. Story 8.3.1 — receipt-derived correction (`a9b5d99`)

The edit proof now derives from **committed workflow state**, never the payload:

- `workflow/receipts.py::build_receipt` gains a conditional `prior_output_hashes`
  body field — absent when None, so pre-8.3.1 receipts stay byte-identical and
  `receipt_id` consumers need no changes.
- `workflow/runner.py::run_stage1_validate` preserves the prior COMPLETE
  receipt's output hashes as `prior_output_hashes` on re-validation
  (`prev.get("prior_output_hashes") or prev.get("output_hashes")`), carrying the
  ORIGINAL prior forward through multi-edit chains. First validation leaves it
  absent (RESOLVED_EDIT then fails closed — documented).
- `collect_hm_findings` stamps `implicated_documents` (Resume.md, CoverLetter.md)
  from code; `_apply_subphase_verdict` passes them into `validate_hm_review`.
- `validate_hm_review` RESOLVED_EDIT path (`_validate_resolved_edit_edit_proof`)
  fails closed on: missing/unreadable `stage_receipts/stage1.json`, `receipt_id`
  mismatch against the recomputed canonical body, `issued_by !=
  scripts/run_submission.py`, status != COMPLETE, stage != stage1, empty/missing
  `prior_output_hashes`, stale declared outputs vs disk, or no implicated doc
  differing prior→now. Payload `prior_document_hashes` are display-only and
  ignored.
- Tests: `scripts/test_hm_critical_read_contract.py` — 61 tests including
  12 adversarial controls (`TestResolvedEditAdversarial` + receipt-based
  `TestResolvedEditProof`).

## 5. Final QA

Bypass-focused independent QA over `a9b5d99`: **PASS (unqualified)**, worker
subagent session `f1ebb434-d2ca-4455-a87c-b4b7b498aa0b`. All 12 required
bypass attempts blocked (invented prior, unrelated-file edit, hand-edited
receipt without recomputing receipt_id, restored pre-edit receipt, missing
receipt, honest no-change receipt + fabricated payload, role relabeling,
no-op re-validation, wrong issued_by/status/stage, missing prior, missing
resolution_summary, multi-edit carry-forward). One LOW note: programmatic
`build_receipt` forgery is outside the contract's threat model (see below).

## 6. Remaining trust boundary

Any actor who can rewrite `stage_receipts/` after the fact can mint a new
canonical receipt. Receipts are workflow-owned (minted only via
`run_submission`/`workflow/runner.py` + `workflow/receipts.py`); there is no
external notary. This is the same trust boundary as every workflow receipt and
is documented in the design doc ("What This Contract Does Not Prove" item 7 and
"Story 8.3.1 — Remaining limitations"). The contract proves a correlated change
happened; it cannot prove the change fixed the finding (judgment lives in
`resolution_summary` + observations).

## 7. Exact commits and integration order

```
c254524  (base, integration target currently)
507855b  Story 8.3  (parent of a9b5d99)
a9b5d99  Story 8.3.1
```

Apply `507855b` first, then `a9b5d99`. Do not cherry-pick `a9b5d99` alone —
it assumes Story 8.3's `hm_review_contract.py` module, `validate_hm_review`
signature, `policy.py` import, and `_apply_subphase_verdict` wiring.

## 8. Files in the range and likely conflict areas

| File | Changed how | Conflict risk with Cursor's candidate |
|---|---|---|
| `scripts/workflow/runner.py` | 8.3: HM validation in `_apply_subphase_verdict`; 8.3.1: `prior_output_hashes` preservation in `run_stage1_validate`, `implicated_documents` stamp in `collect_hm_findings`, binding into validator | HIGH (shared runner; line movement) |
| `scripts/workflow/policy.py` | 8.3 only: import `HM_DISALLOWED_DISPOSITIONS`, disallow NOT_APPLICABLE/FALSE_POSITIVE for hm.critical_read | MEDIUM (shared policy) |
| `scripts/workflow/reviews.py` | 8.3 only: dispositions note text | LOW (note text) |
| `scripts/workflow/receipts.py` | 8.3.1 only: conditional `prior_output_hashes` kwarg | LOW-MEDIUM (workflow-owned, not Cursor-owned) |
| `scripts/hm_review_contract.py` | New module (8.3), extended (8.3.1) — imports nothing from `workflow/` | LOW (standalone) |
| `scripts/test_hm_critical_read_contract.py` | New test module (8.3), extended (8.3.1) | LOW |
| `scripts/test_workflow_authority.py` | 8.3: HM disposition in full-flow tests upgraded to a valid structured `hm_review` artifact | MEDIUM (shared test file) |
| `docs/spec/08-implementation/CR-112-hm-*` + any CR-112 requirements/traceability/handoff docs | Design, QA final, this handoff | LOW (docs; merge text) |

Also check: `docs/spec/02-requirements-registry.md` / `docs/spec/06-traceability/traceability-matrix.md`
if Cursor's candidate touched CR-112 rows.

## 9. Semantics that must survive conflict resolution

- **runner.py**: the HM artifact validation must fire only for `phase == "hm"`
  after policy PASS; `implicated_documents` must come from the finding
  (code-stamped), never the reviewer payload; `run_stage1_validate` must
  preserve prior COMPLETE output hashes as `prior_output_hashes` with the
  original-prior carry-forward fallback; freshness gates (`_require_stage1_fresh`,
  `reconcile`) must remain intact.
- **policy.py**: NOT_APPLICABLE/FALSE_POSITIVE must stay disallowed for
  `hm.critical_read` (returns FAIL), imported from `hm_review_contract`
  (single source of truth); Truth/ATS/Mech evaluation must be untouched.
- **reviews.py**: dispositions note text must keep the structured `hm_review`
  requirement and disallowed-disposition mention; `REASONING_MIN_CHARS = 10`
  for other subphases unchanged.
- **receipts.py**: `prior_output_hashes` must remain conditional (absent when
  None); verify `check_workflow_complete` and
  `reconcile_state_against_receipts` still recompute/read against the full body
  minus `receipt_id` with `sort_keys=True, separators=(",",":"),
  ensure_ascii=False` — any drift breaks every receipt_id.
- **test_workflow_authority.py**: any HM disposition in full-flow tests must be a
  valid structured artifact (verified spans/role/timestamp); a bare
  ACCEPTED_AS_CORRECT string now correctly fails HM.
- Do not re-enable payload `prior_document_hashes` as proof; do not drop the
  anti-forgery `receipt_id` check; do not change receipt_id canonicalization.

## 10. Required post-integration verification

Run from the repo root (worktree venvs are absent; system `python` 3.12 works):

- HM contract suite: `python -m unittest scripts.test_hm_critical_read_contract` (61 tests)
- Workflow authority: `python -m unittest scripts.test_workflow_authority`
- Contracts: `python -m unittest scripts.test_contracts` (76 tests)
- CR-112 adversarial: `python -m unittest scripts.test_cr112_adversarial` + `python scripts\run_adversarial_pressure_test.py`
- Receipt compatibility: no standalone receipts module — covered by
  `scripts.test_contracts` (check_workflow_complete receipt_id recompute),
  `scripts.test_hm_critical_read_contract` (build/load/write receipt +
  adversarial), `scripts.test_workflow_authority` (commit-stage chains);
  run all three
- Story 8.1 rubric-floor: `scripts.test_contracts` (check_rubric_floors cases) +
  `scripts.test_workflow_authority` (mech.rubric_floor.* BLOCK findings) +
  `scripts.test_check_finalize_ready`
- Story 8.2 identity: `python -m unittest scripts.test_practice_identity` (SEC-006/AC-416)
- Extraction-review restart: `python -m unittest scripts.test_cr112_stage0_extraction_review`
- Canonical runner: `python scripts/run_submission.py <folder> --status`
  (read-only) and one full `--resume` cycle against an archive/practice folder
  copy (never production `data/submissions/` live folders)

### Two KNOWN failures — not Story 8.3/8.3.1 regressions

1. `scripts.test_workflow_authority.Stage3FinalizeTests.test_mode_mismatch_rewrites_with_force`
   — `sqlite3.OperationalError: no such table: jobs`. The isolated SQLite
   fixture lacks the `jobs` schema. Reproduced identically at parent `507855b`.
2. `scripts/run_adversarial_pressure_test.py` `case_state_004_complete` —
   `WorkflowError: Cannot finalize: draft_manifest.json not found`. The
   finalize fixture omits `draft_manifest.json`. Reproduced identically at
   parent `507855b`.

Do not classify either as a Story 8.3 regression, and do not silently accept
them in the integrated candidate. Cursor must determine whether its newer
candidate work already fixed them or whether they need separate test-fixture
stories.

## 11. Factory closeout statement

Story 8.3 and Story 8.3.1 are accepted as ready for integration review.
Factory stops implementation now: no further HM controls, no fixes to the two
pre-existing failures, no rebase/squash/push/merge, no change to Cursor's
branch, no new story. Leave the branch untouched for Cursor's integration.
