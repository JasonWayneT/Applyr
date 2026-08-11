# CR-081: HM Review + Final Mech + Stage 2 Policy Receipt

## Metadata
- **Status**: Vertical slice landed — 2026-08-09 (awaiting Claude Code spot-check)
- **Date**: 2026-08-09
- **Source**: session-006; follows CR-080
- **Related**: CR-079/080; enables Claude's deferred CR-078 finalize/`check_workflow_complete` cutover once Stage 3 exists
- **Requirement IDs**: `FR-262`, `AC-316`–`AC-320`

## Problem
Stage 2 unlocked ATS but had no HM review, final mechanical verify under the orchestrator, or Stage 2 receipt — so `check_workflow_complete` stayed permanently False for real folders.

## Decision
1. **2C HM:** lint WARNs/BLOCKs + mandatory `hm.critical_read` finding → dispositions → hm COMPLETE → mech READY.
2. **2D Mech:** wrap `compile_single` + `verify_one`; BLOCK if not `mechanically_verified`; WARN if rubric missing → dispositions → mech COMPLETE → policy READY.
3. **2E Policy:** `contracts.check_stage2_ready` must pass (no disposition workaround). Then write `stage_receipts/stage2.json` COMPLETE (sole writer), unlock Stage 3 READY. Preserve Stage 2 subphases on the stage record.
4. CLI: `--stop-after-ats` / `--stop-after-hm` / `--no-compile`.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-316 | ATS COMPLETE → HM collectors + `hm.critical_read`; WAITING_FOR_HUMAN until disposed |
| AC-317 | HM COMPLETE → mech compile+verify_one; mech findings/dispositions |
| AC-318 | Mech COMPLETE + `check_stage2_ready` PASS → Stage 2 COMPLETE receipt + Stage 3 READY |
| AC-319 | `check_stage2_ready` FAIL → WAITING_FOR_HUMAN on policy (fix rubric/receipt; re-check on --resume) |
| AC-320 | Workers still do not write stage_receipts; integrity OVERRIDDEN carries from earlier HUMAN_ACCEPTED_RISK |

## Out of Scope
- Stage 3 finalize DB upsert under orchestrator (follow-on)
- Full qualitative HM LLM reviewer (mechanical + critical_read gate only)
