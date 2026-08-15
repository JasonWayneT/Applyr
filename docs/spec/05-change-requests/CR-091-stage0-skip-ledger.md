# CR-091: Stage 0 Skip Ledger and Folder Placement

## Metadata
- **Status**: Implemented (2026-08-14)
- **Date**: 2026-08-14
- **Source**: Live `data/submissions/` clutter after a CSV Stage 0 batch — 8 COMPLETE
  folders buried under 75 Skip/stub copies, including 16 that already existed in
  `data/archive/submissions/`
- **Related**: FR-252 (Stage 0), FR-030 (submission folder reconcile), CR-076
  (orchestrator)

## Problem
CSV import and Stage 0 both write into `data/submissions/`. A Skip still drops
`stage0_fit_gate.json` there. `reconcileActiveSubmissionFolders()` was later
taught never to delete a folder that has that file (after it wiped five real
PASS folders mid-batch). Skips became permanent clutter, and a later import
recreated thin copies of companies that were already archived.

Walking those folders on the next batch would not scale. Storage is not the
constraint. Lookup is.

## Decision
1. Incoming JDs (CSV import, same as Sync) land in `data/pending_review/`.
2. `stage0_skips` in `jobagent.sqlite` is the memory of a Skip. Lookup is exact
   URL (tracking-query stripped), then exact `company||title`. Never a folder
   crawl. Not a `jobs.status` — that table is application outcomes.
3. Production Skip: write the ledger, move the folder to `data/archive/skipped/`
   (audit only). Production PASS from `pending_review/`: promote into
   `data/submissions/`.
4. A new posting at a skipped *company* still gets a fresh Stage 0. Existing
   jobs-table cooldown / Self-Rejected rules are unchanged.
5. `--force` re-evaluates a ledger hit. PASS clears the ledger row.
6. Practice mode does not write the ledger. Placement only moves folders that
   actually live under `pending_review/` or `submissions/` (temp test dirs stay put).
7. Reconcile sweeps leftover SKIP gates out of `submissions/` the same way.
   PASS-with-no-PDFs stays protected.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-326 | URL hit (including `utm_*` / `gh_src` stripped) returns the prior Skip without re-extraction |
| AC-327 | Same company, different title does not hit the ledger |
| AC-328 | CSV import writes to `pending_review/` and does not create a folder for a ledger URL |
| AC-329 | Production Skip moves the folder to `data/archive/skipped/` and records the ledger; PASS from pending_review is promoted to `submissions/` |
| AC-330 | `--force` Stage 0 that PASSes deletes the ledger row |
| AC-331 | Reconcile no longer leaves SKIP fit-gate folders in `submissions/` |

## Out of Scope
- Changing jobs-table cooldown / Self-Rejected behavior
- UI for browsing or overriding skips
- Backfilling the ledger from historical `archive/submissions/`
