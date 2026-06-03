# IMP-CR-035: Fit Scoring Hardening

**CR:** `CR-035-fit-scoring-hardening.md`  
**Requirements:** `FR-188`, `FR-070`, `FR-172`

## Tasks
- [x] `resolve_location_verdict` + location lock prompt (`zero_shot_classifier.py`)
- [x] `fit_policy.py` — optional domain, anchor floor, gates-passed rubric
- [x] `evaluate_job_fit` — scoring-only primary, anchor floor post-process
- [x] `job_fit_engine.md` — multi-city remote, co-lead, startup exception
- [x] Regression tests REG-16–REG-19

## Verification
```bash
python scripts/test_fit_policy.py
python scripts/test_smoke_regression.py  # REG-16+
python scripts/evaluate_jd_only.py jobs/_eval_ophelia_pm.txt Ophelia
```
