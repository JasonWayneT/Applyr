# Loop checklist

An item is checked only when the evidence file exists and the verify command was run.

- [x] Inspect uncommitted work on main, do not apply it, start from branch point 6c68377 | evidence: docs/loop/evidence/00-preloop/classification.md | verify: git diff --stat (scripts clean) and Test-Path docs/loop/evidence/00-preloop/uncommitted.patch
- [x] Record eligibility rule and census (412) | evidence: docs/loop/evidence/00-preloop/eligibility.txt | verify: python -c "from pathlib import Path; root=Path('data/archive/submissions'); n=sum(1 for p in root.iterdir() if p.is_dir() and '_backup_' not in p.name and (p/'Original_JD.txt').is_file() and (p/'Original_JD.txt').stat().st_size>=1500); print(n)"
- [ ] F0: one eligible JD, Stage 0 through Stage 3, practice mode, unattended-or-not recorded | evidence: docs/loop/evidence/00-f0/ | verify: python scripts/run_submission.py data/loop_runs/f0/1uphealth --status
