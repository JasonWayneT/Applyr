# Loop ledger

## HANDOFF

Phase F0, iteration 0. Branch `loop/2026-09-23` at `6c68377`. No pipeline code changed yet.
Uncommitted main WIP was reverted. It mixed allowlist additions and suppressions. Do not apply `docs/loop/evidence/00-preloop/uncommitted.patch`.
FINDINGS-2026-09-24-entailment-gap.md does not exist. Known-bad copies are in `data/review_evidence/2026-09-23-before-fix/` (17 slugs).
Stage 1 for `1uphealth` was marked STALE and re-verified. It FAILED on LR-045 and LR-047. Next: `python scripts/run_stage1_repair.py data/loop_runs/f0/1uphealth` after the repair prompt exists. Log: `data/loop_runs/f0/1uphealth-repair.log`.
Cap: 200 LLM calls or 8 hours. Agy is on PATH. Stage 1 author is `scripts/run_stage1_author.py` after `WAITING_FOR_LLM`.
Trap: a pause for requirement-extraction review or a human paste means F0 failed unattended. Record it. Do not shop for an easier JD.

## Iteration 0 — setup

1. OBSERVE: `docs/loop/` was missing. Working tree on main had 990 uncommitted lines in 12 pipeline files.
2. ROOT CAUSE: not a pipeline defect. Prior session left a mixed diff uncommitted.
3. EXPLORE: apply the diff, or revert and record it.
4. CHOOSE: revert. Several hunks add allowlist entries or suppressions. The mission forbids those. The patch stays as evidence.
5. IMPLEMENT: branch `loop/2026-09-23`, STATE/CHECKLIST/LEDGER, no product code.
6. EVALUATE: `git diff --stat` empty for scripts. Eligibility census printed 412.
7. CONFIRM: branch point is `6c68377`. Prior WIP is not in the tree.
8. Not a failed fix. No revert of product code.
