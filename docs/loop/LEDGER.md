# Loop ledger

## HANDOFF

Paused 2026-09-23 at Jason's request. Continue tomorrow. Definition of done is not met.
F0 is done for one job. `1uphealth` is PRACTICE_COMPLETE under `data/loop_runs/f0/1uphealth`.
F1 passed. Evaluator recall 0.939 (31/33) and false-positive rate 0.028 (6/215) on the before-fix bak files. Evidence: `docs/loop/evidence/f1/validation.txt`. Two classlink Sterkly bullets stay unflagged.
Next action is F2. Freeze DEV and HOLDOUT from eligible slugs. Holdout at least 60. Record slugs and the seed in STATE.json. Do not open holdout job text.
11 Agy calls. Do not loosen a gate. Do not apply the preloop patch. Do not stage the parallel CR-128/CR-129 working-tree edits.

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

## Iteration 0 — F1 evaluator

1. OBSERVE: pipeline gates are not the judge. The before-fix bak files still contain the sentences in `docs/loop/evidence/f1/gold.json`.
2. ROOT CAUSE: not a pipeline fix. This step only measures. A model judge was not called. The check is deterministic against the cited id and a small phrase list.
3. EXPLORE: call a second model per sentence, or score locally from the findings' contradiction patterns. A per-sentence model call would spend the remaining Agy budget before any holdout run.
4. CHOOSE: local checks in `scripts/loop_eval.py`. No pipeline edit.
5. IMPLEMENT: evaluator, gold quotes, `scripts/validate_loop_eval.py`, `scripts/test_loop_eval.py`.
6. EVALUATE: `python scripts/validate_loop_eval.py` printed recall 0.939 and false-positive rate 0.028. Unit tests passed.
7. CONFIRM: both bars hold. Two classlink Sterkly bullets stay unflagged on purpose. Evidence: `docs/loop/evidence/f1/validation.txt`.
8. Not a failed fix. No pipeline revert.

