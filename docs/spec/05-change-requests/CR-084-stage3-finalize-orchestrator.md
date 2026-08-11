# CR-084: Stage 3 Finalize Under Orchestrator

## Metadata
- **Status**: Vertical slice landed — 2026-08-09 (awaiting Claude Code spot-check)
- **Date**: 2026-08-09
- **Source**: session-006 R21 ownership; follows CR-081
- **Related**: Enables Claude CR-078 AC-302/303 cutover; CR-082 remains Claude (legacy)
- **Requirement IDs**: `FR-263`, `AC-321`–`AC-325`

## Problem
Stage 2 COMPLETE unlocked Stage 3 READY, but nothing wrapped `finalize_submission_job`, minted `stage_receipts/stage3.json`, or set terminal `COMPLETE` / `COMPLETE_WITH_OVERRIDE` / `PRACTICE_COMPLETE`. `check_workflow_complete` stayed False forever.

## Decision
1. Explicit `--finalize` (does not auto-run on every `--resume` after Stage 2).
2. Wrap existing `finalize_submission_job.finalize` (still enforces `check_finalize_ready` unless `--force-finalize`).
3. Company/title/reach_out from `stage0_fit_gate.json`, overridable via CLI.
4. Practice mode: no DB write → `PRACTICE_COMPLETE` (not production DONE).
5. Production: Stage 3 COMPLETE receipt → `COMPLETE` or `COMPLETE_WITH_OVERRIDE` if any stage integrity OVERRIDDEN.
6. Sole writer remains `workflow.receipts`.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-321 | Stage 2 COMPLETE + `--finalize` → wraps finalize worker (mocked in tests) |
| AC-322 | Production success → stage3 COMPLETE receipt + workflow COMPLETE |
| AC-323 | Practice `--finalize` → PRACTICE_COMPLETE, finalize_job not called |
| AC-324 | OVERRIDDEN integrity → COMPLETE_WITH_OVERRIDE; check_workflow_complete True |
| AC-325 | Without `--finalize`, Stage 2 COMPLETE stops with Stage 3 READY message |

## Out of Scope
- CR-078 finalize/status cutover to `check_workflow_complete` (Claude)
- CR-082 legacy containment (Claude)
- CR-083 failure-injection suite
