# CR-077: Receipt Chaining + Hash Invalidation

## Metadata
- **Status**: Vertical slice landed — 2026-08-09 (awaiting Claude Code spot-check)
- **Date**: 2026-08-09
- **Source**: session-006 frozen architecture; follows CR-076
- **Related**: CR-076 (authority foundation), precedes CR-078 (DONE oracle / UI)
- **Requirement IDs**: `FR-258`, `AC-294`–`AC-298`

## Problem
CR-076 stops at `WAITING_FOR_LLM`. Nothing yet writes a Stage 1 COMPLETE receipt after docs land, Stage 2 has no machine chain from Stage 1, and post-receipt edits do not flip workflow to `STALE`.

## Decision
1. When Resume.md + CoverLetter.md (+ provenance as required by verify-only) exist, orchestrator runs existing `author_from_packet.run_verify_only` + `contracts.check_stage1_ready`, then writes Stage 1 receipt `status=COMPLETE`.
2. Stage 2 becomes `READY` only after Stage 1 COMPLETE with fresh hashes — no Stage 2 work in this CR.
3. `workflow/invalidate.py` reconciles receipt `output_hashes` vs disk; mismatches mark that stage `STALE` and lock/stale downstream.
4. `run_submission --resume` re-enters from earliest READY/STALE/WAITING action.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-294 | Docs present after WAITING_FOR_LLM → verify-only + Stage 1 COMPLETE receipt with prior_receipt_id chain |
| AC-295 | Stage 2 stage record READY only when Stage 1 receipt COMPLETE and hashes fresh |
| AC-296 | Edit Resume/CL after Stage 1 COMPLETE → reconcile marks Stage 1 STALE (and Stage 2 LOCKED) |
| AC-297 | `--resume` continues WAITING→validate or rebuilds from STALE without inventing COMPLETE |
| AC-298 | CR-075 `check_stage1_ready` still enforced (no force for packet_status) |

## Out of Scope
- Stage 2 reviews / final mech (CR-079–081)
- Demoting `verification_passed` (CR-078)
- Full adversarial suite (CR-083)
