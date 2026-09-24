# Loop ledger

## HANDOFF

Stopped on a red line. Phase is still F0. Branch `loop/2026-09-23`. Do not merge.
`1uphealth` practice run is FAILED at Stage 1. The letter does not name a past employer (LR-045). Do not launch another repair on `data/loop_runs/f0/1uphealth`.
Stage 0 and the Stage 1 author ran unattended on Agy (11 calls total). Stage 3 was not reached. No evaluator, no DEV/HOLDOUT split.
Two tightenings stay in the branch: Stage 1 verify fails the Stage 2 fidelity blocks (702d2e6), and a drop that would create a new hard block is refused (330115b). The repair model then deleted the employer sentence on its own.
Next reader: read `docs/loop/evidence/00-f0/stop.txt`. Cap was 200 calls or 8 hours. Used 11 calls. Definition of done was not met.
Trap: do not apply `docs/loop/evidence/00-preloop/uncommitted.patch`. It loosens gates.

## Iteration 0 — setup

1. OBSERVE: `docs/loop/` was missing. Working tree on main had 990 uncommitted lines in 12 pipeline files.
2. ROOT CAUSE: not a pipeline defect. Prior session left a mixed diff uncommitted.
3. EXPLORE: apply the diff, or revert and record it.
4. CHOOSE: revert. Several hunks add allowlist entries or suppressions. The mission forbids those. The patch stays as evidence.
5. IMPLEMENT: branch `loop/2026-09-23`, STATE/CHECKLIST/LEDGER, no product code.
6. EVALUATE: `git diff --stat` empty for scripts. Eligibility census printed 412.
7. CONFIRM: branch point is `6c68377`. Prior WIP is not in the tree.
8. Not a failed fix. No revert of product code.

## Iteration 0 — F0 feasibility, stopped

1. OBSERVE: `1uphealth` Stage 0 COMPLETE via Agy. Author wrote files. First resume parked at HM with BLOCK LR-045 and LR-047. Evidence: `docs/loop/evidence/00-f0/`.
2. ROOT CAUSE: CONFIRMED. Those hard blocks run in `lint_folder` after Stage 1 is COMPLETE. `needs_stage1_repair` requires status FAILED, so nothing rewrites the draft.
3. EXPLORE: leave the park, dispose the blocks, or fail Stage 1 on the same checks. Disposing is forbidden.
4. CHOOSE: fail Stage 1 on `collect_fidelity_hard_blocks`. Then a second confirmed cause: `drop_uncited_units` deleted the repaired employer sentence. Refuse a drop that creates a new hard block.
5. IMPLEMENT: commits `702d2e6` and `330115b`. Tests named in the evidence file.
6. EVALUATE: re-verify failed LR-045 and LR-047. After the guard, resume kept the Cision sentence and failed provenance. Repair 3 removed the sentence. Resume failed LR-045 again.
7. CONFIRM: the local checks behave as tested. The live draft does not. Stage 3 was not reached.
8. Stop. Same defect after two fixes. Do not run another repair on this folder.
