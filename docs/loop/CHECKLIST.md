# Loop checklist

An item is checked only when the evidence file exists and the verify command was run.

- [x] Inspect uncommitted work on main, do not apply it, start from branch point 6c68377 | evidence: docs/loop/evidence/00-preloop/classification.md | verify: git diff --stat (scripts clean) and Test-Path docs/loop/evidence/00-preloop/uncommitted.patch
- [x] Record eligibility rule and census (412) | evidence: docs/loop/evidence/00-preloop/eligibility.txt | verify: python -c "from pathlib import Path; root=Path('data/archive/submissions'); n=sum(1 for p in root.iterdir() if p.is_dir() and '_backup_' not in p.name and (p/'Original_JD.txt').is_file() and (p/'Original_JD.txt').stat().st_size>=1500); print(n)"
- [x] F0: one eligible JD, Stage 0 through Stage 3, practice mode, unattended-or-not recorded | evidence: docs/loop/evidence/00-f0/stage3.txt | verify: python -c "import json; print(json.load(open('data/loop_runs/f0/1uphealth/workflow_state.json',encoding='utf-8'))['status'])"
- [x] F1: independent evaluator validated on the before-fix set (recall >= 0.90, false positives < 0.10) | evidence: docs/loop/evidence/f1/validation.txt | verify: python scripts/validate_loop_eval.py
- [x] F2: DEV and HOLDOUT frozen, holdout 60, seed 20260923 | evidence: docs/loop/evidence/f2/split.txt | verify: python scripts/check_loop_split.py
