---
status: reconciliation
created: 2026-09-14
from: Claude (deep-dive + doc audit, requested by Jason)
supersedes_stale_status_in: CR-112-reconciliation-2026-09-11.md, CR-112-stage0-3-reliability-quality-tokens-epics.md, CR-112-cost-pause-state-design.md (working-tree copy), 02-requirements-registry.md, 06-traceability/traceability-matrix.md
---

# CR-112 reconciliation — 2026-09-14 doc-staleness correction

Documentation-only. No code changed. No branch merged. No push.

## What was found

A deep-dive requested against Applyr (for a separate Metis planning task)
found that three tracker documents on `cr112-selection-closed-world-design`
had gone stale relative to work already completed on the isolated
`cr112-story71-72` branch:

1. **`CR-112-stage0-3-reliability-quality-tokens-epics.md`** still said
   Story 7.1/7.2's independent review "was FAIL" and the follow-up was
   "uncommitted."
2. **`CR-112-cost-pause-state-design.md`** — the untracked working-tree
   copy on this branch was missing the `follow_up_review: PASS` line
   that exists in the same file on `cr112-story71-72`.
3. **`02-requirements-registry.md`** and **`06-traceability-matrix.md`**
   still marked FR-312–FR-317 / AC-409–AC-414 (Stories 3.1, 3.5, 3.6, 7.1,
   7.2) as `draft` / `planned`, even though 3.1/3.5/3.6 are complete and
   independently reviewed on *this very branch* at `706504a`, and 7.1/7.2
   are complete and independently reviewed on `cr112-story71-72`.

## What actually happened on `cr112-story71-72`

Follow-up commit `7bf6829` (child of the reviewed-FAIL `b7f7197`)
implements `CR-112-cost-pause-state-design.md` end to end: cost
eligibility, `WAITING_FOR_INPUT`/`pause_kind=cost_authorization` receipt,
bound manual cascade import, consumed-import rename, paid-budget ledger
persistence, and the cost-telemetry confidence table (Decision 7).

Per `SESSION-HANDOFF-2026-09-11-cr112-story71-72-followup.md` (only on
that branch): independent re-review **PASSed**
(`97887893-381a-47fa-b521-e5c1d5d2af78`), after a first pass on the same
follow-up FAILed on `expected_item_ids`/`created_at` optionality and was
corrected. Branch marked "integration-ready" for 7.1/7.2.

## Independent verification (2026-09-14, this session)

Re-ran the cited test suites in a throwaway detached worktree off
`cr112-story71-72` (removed after):

- `python -m unittest scripts.test_cr112_story71 -v` → **41 passed**
- `python -m unittest scripts.test_stage0_evidence_cascade -v` → **27 passed**

At the time of this reconciliation, one should-fix from the handoff
remained open: `created_at` in the cascade-import schema was required
to be *present*
(`scripts/stage0_evidence_cascade.py`, `_REQUIRED_IMPORT_FIELDS` /
`created_at is required for audit`) but was not type-checked as a non-empty
string. Confirmed by reading the code; audit-only field, not an
identity/authorization gap.

Update 2026-09-15: this should-fix was closed on
`codex/cr112-consolidation`. `scripts/stage0_evidence_cascade.py` and
`scripts/stage0_requirement_extraction_review.py` now require
`created_at` to be a non-empty string. Regressions cover null, blank,
whitespace, and numeric values.

## What this reconciliation does NOT do

- Does not merge `cr112-story71-72` onto `cr112-selection-closed-world-design`.
- Does not merge Epic 3 (`706504a`) onto `cr112-integration` / `main` —
  still pending Jason's explicit ask, per the 2026-09-10/11 record.
- Did not fix the `created_at` type-check should-fix in this docs-only
  reconciliation; later closed 2026-09-15 on `codex/cr112-consolidation`.
- Does not touch `data/submissions`, push, or call any provider.

## Updated docs

- `CR-112-stage0-3-reliability-quality-tokens-epics.md` — added a
  2026-09-14 correction note; updated Story 7.1/7.2 status lines.
- `CR-112-cost-pause-state-design.md` — added the missing
  `follow_up_review: PASS` frontmatter line.
- `02-requirements-registry.md` — FR-312–FR-317 / AC-409–AC-414: `draft` → `in_progress`.
- `06-traceability/traceability-matrix.md` — same rows: `draft`/`planned` → `in_progress`, with real file paths.

## Maintenance update (2026-09-15)

The current `codex/cr112-consolidation` working tree now contains and locally
verifies the next bounded CR-112 slice:

- Story 8.6, `FR-322` / `AC-420`: hash-bound, role-tagged score provenance
  with boundary-band blind-read and fail-closed disagreement checks.
- Story 8.7, `FR-325` / `AC-423`: unbracketed placeholder replacement and
  stacked-header cleanup.
- Story 8.8, `FR-323` / `AC-421`: bounded distributed/event-driven
  requirement semantics correction with cost and ARR/reliability controls.
- Story 8.9, `FR-324` / `AC-422`: CR-094 claims-index validator alignment
  with grounded metric validation.

Fresh local evidence:

- `python -m unittest scripts.test_contracts scripts.test_workflow_authority scripts.test_practice_identity scripts.test_cr112_ranking_characterization scripts.test_catalog_validator`
  completed 167 tests successfully.
- `python scripts/verify_master_claims.py` printed `Validation Passed.`

No provider/model/API call was made, no paid provider was authorized, and no
production SQLite or submission data was modified. The supervised real-JD dry
run remains future product proof. Current readiness is
`SUPERVISED_SMALL_BATCH_READY`, not `DAILY_USE_READY`.
