# CR-079: Truth / Evidence Review (Stage 2A)

## Metadata
- **Status**: Vertical slice landed — 2026-08-09 (awaiting Claude Code spot-check)
- **Date**: 2026-08-09
- **Source**: session-006 frozen architecture; follows CR-077/078 handoff (R9/R10)
- **Related**: CR-077 (Stage 2 READY), CR-078 (UI gate), precedes CR-080 (ATS)
- **Requirement IDs**: `FR-260`, `AC-307`–`AC-311`

## Problem
Stage 2 is unlocked after Stage 1 COMPLETE, but nothing models Truth/Evidence as an orchestrator-owned subphase. Coverage and provenance remain agent-scheduled side scripts; findings have no disposition path; Stage 2 cannot wait for Jason without inventing COMPLETE.

## Decision
1. After Stage 1 COMPLETE + fresh hashes, orchestrator runs mechanical Truth collectors (`claim_provenance.check_claim_provenance`, `check_ground_truth_coverage.check_folder`) and writes `reviews/truth_findings.json` (not a stage receipt).
2. Open findings → `reviews/dispositions.json` stub → workflow `WAITING_FOR_HUMAN`. Jason fills dispositions; `--resume` re-runs policy.
3. Dispositions: `RESOLVED_EDIT` | `ACCEPTED_AS_CORRECT` | `NOT_APPLICABLE` | `FALSE_POSITIVE` (CLEAN); `HUMAN_ACCEPTED_RISK` (OVERRIDDEN). BLOCK findings may only use `RESOLVED_EDIT` or `HUMAN_ACCEPTED_RISK`.
4. Truth PASS → `stages.stage2.subphases.truth=COMPLETE`, `ats=READY`, Stage 2 stays `RUNNING` — **no** `stage_receipts/stage2.json` until CR-081.
5. Stage 1 STALE cascade resets Stage 2 subphases (restart from Truth).

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-307 | Stage1 COMPLETE → Truth collectors run; `reviews/truth_findings.json` written by orchestrator |
| AC-308 | Open findings → WAITING_FOR_HUMAN + dispositions stub; no Stage 2 COMPLETE receipt |
| AC-309 | Valid CLEAN dispositions → truth COMPLETE + ats READY; integrity CLEAN |
| AC-310 | HUMAN_ACCEPTED_RISK → truth PASS with integrity OVERRIDDEN on stage2 |
| AC-311 | BLOCK + FALSE_POSITIVE → policy FAIL; Stage1 STALE resets truth subphase |

## Out of Scope
- ATS / HM / final mech / Stage 2 receipt (CR-080/081)
- LLM narrative Truth reviewer (mechanical collectors only in this CR)
- finalize/status cutover to `check_workflow_complete` (Claude CR-078 remainder)
