# Loop ledger

## HANDOFF

affinity_co verify FAILED. Two drafting-time lines are missing the estimate hedge (LR-047). Status FAILED, so repair can run.
Next is build_stage1_repair_prompt.py then run_stage1_repair.py on `data/loop_runs/i1/affinity_co`.
Definition of done is not met. Cumulative Agy calls 32. Do not open holdout job text. Do not loosen a gate. Do not stage the parallel CR-128/CR-129 edits.

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

## Iteration 0 — F2 split

1. OBSERVE: DEV and HOLDOUT were empty. Eligible folders are now 426, up from 412 on 2026-09-23.
2. ROOT CAUSE: not a defect. The split had not been frozen.
3. EXPLORE: a pure shuffle of all 426, or hold the already-read slugs in DEV.
4. CHOOSE: seed 20260923, holdout 60 from the unread pool. `1uphealth` and the before-fix review slugs that still exist as archive folders stay in DEV. Seven review names are not archive folders.
5. IMPLEMENT: slugs in STATE.json. Draw check in `scripts/check_loop_split.py`. No pipeline edit. No job text opened.
6. EVALUATE: `python scripts/check_loop_split.py` printed MATCH, dev 366, holdout 60.
7. CONFIRM: overlap 0. Evidence: `docs/loop/evidence/f2/split.txt`.
8. Not a failed fix.


