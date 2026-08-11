# CR-076: Workflow Authority Foundation

## Metadata
- **Status**: In progress — 2026-08-09
- **Date**: 2026-08-09
- **Source**: harness-bridge `session-006-applyr-workflow-authority.md` (frozen architecture; Claude Code R2/R3 ack)
- **Related**: Extends CR-075 (gates stay live underneath). Does not replace CR-074 authoring path. Precedes CR-077 (chaining) and CR-078 (DONE oracle / UI).
- **Requirement IDs**: `FR-257`, `AC-289`–`AC-293` (registry)

## Problem
CR-075 enforces per-stage readiness inside producing scripts, but agents still own *sequencing* and can report completion without an authoritative workflow controller. There is no `run_submission` owner of progression, no sole writer of workflow receipts, and no single mid-state (`WAITING_FOR_LLM`) the system can resume from.

## Decision
1. Add thin `scripts/run_submission.py` + `scripts/workflow/` that **wraps** existing workers (`build_stage0_fit_gate`, `build_authoring_packet`, `author_from_packet`) — does not reimplement them.
2. Only `workflow/receipts.py` writes `workflow_state.json` and `stage_receipts/*.json`. Workers never write those.
3. CR-075 `contracts` / `stage_gate` checks remain live as a safety net under the new layer.
4. First slice: Stage 0 → packet/prompt → `WAITING_FOR_LLM` → stop. No Stage 2 reviews, no finalize cutover, no demotion of `verification_passed`.
5. Existing folders: adopt valid on-disk artifacts into receipts via hash-valid adopt (no force-restart from Stage 0).

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-289 | `run_submission.py` runs Stage 0 via existing builder, validates with `check_stage0_fit_gate`, writes Stage 0 receipt; Skip → workflow `SKIPPED` (non-zero or explicit status, not silent Pass) |
| AC-290 | On Pass: builds packet + prompt via existing APIs, sets `WAITING_FOR_LLM`, writes Stage 1 intermediate receipt; does not call cloud compose |
| AC-291 | Workers / tests prove no module other than `workflow.receipts` writes `stage_receipts/` |
| AC-292 | `contracts.check_workflow_complete()` returns False until later CRs land full COMPLETE; progress helpers report `WAITING_FOR_LLM` / `SKIPPED` correctly |
| AC-293 | Adopt path: folder with valid `stage0_fit_gate.json` (and optional packet/prompt) gets receipts without rebuilding from scratch when hashes match |

## Out of Scope
- Stage 1 `--verify-only` receipt / Stage 2 chaining (CR-077)
- Demoting `verification_passed` / `files.ts` export (CR-078)
- Truth/ATS/HM reviews (CR-079–081)
- Legacy containment (CR-082)
- Full failure-injection suite (CR-083)
