# CR-080: ATS / AI Review (Stage 2B)

## Metadata
- **Status**: Vertical slice landed — 2026-08-09 (awaiting Claude Code spot-check)
- **Date**: 2026-08-09
- **Source**: session-006; follows CR-079
- **Related**: CR-079 (Truth), precedes CR-081 (HM + mech + Stage 2 receipt)
- **Requirement IDs**: `FR-261`, `AC-312`–`AC-315`

## Problem
After Truth COMPLETE, Stage 2 has no orchestrator-owned ATS/AI subphase. JD-term gaps remain a side script; nothing unlocks HM or waits for human disposition under workflow authority.

## Decision
1. After Truth COMPLETE, orchestrator runs `jd_term_extractor.check_folder`, writes `reviews/ats_findings.json`.
2. Same disposition model as Truth (`reviews/dispositions.json` shared stub).
3. ATS PASS → `subphases.ats=COMPLETE`, `hm=READY`; still no `stage_receipts/stage2.json`.
4. CLI `--stop-after-truth` skips ATS; default path runs Truth then ATS.

## Acceptance Criteria
| ID | Criterion |
|----|-----------|
| AC-312 | Truth COMPLETE → ATS collectors run; `reviews/ats_findings.json` written |
| AC-313 | Open ATS findings → WAITING_FOR_HUMAN; no Stage 2 receipt |
| AC-314 | CLEAN dispositions → ats COMPLETE + hm READY |
| AC-315 | ATS blocked until Truth COMPLETE |

## Out of Scope
- HM review, final mech, Stage 2 policy receipt (CR-081)
- LLM ATS narrative reviewer (mechanical jd_term only)
- PDF/reading-order (belongs with 2D mech)
