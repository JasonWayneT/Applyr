# IMP-CR-037: Required Domain Experience Gate

**CR:** `CR-037-required-domain-gate.md`  
**Requirements:** `FR-190`, `FR-188` (optional-domain fix)

## Tasks
- [x] `domain_gate.py` — canonical vertical aliases, years+industry extraction, `check_domain_gate`
- [x] `fit_policy.py` — suppress optional note when required domain detected; skip anchor floor; `enforce_required_domain_cap`
- [x] `batch_pipeline.py` — domain gate in `passes_jd_keyword_gate`
- [x] `evaluate_jd_only.py` — expose domain gate in diagnostics
- [x] `test_domain_gate.py` — unit tests
- [x] `test_fit_policy.py` — preferably false-positive regression
- [x] `test_smoke_regression.py` — REG-20, REG-21

## Verification
```bash
python scripts/test_domain_gate.py
python scripts/test_fit_policy.py
python scripts/evaluate_jd_only.py jobs/_eval_cotiviti_pm.txt "Cotiviti Healthcare"
python scripts/evaluate_jd_only.py jobs/_eval_ophelia_pm.txt "Ophelia"
```

Expected: Cotiviti → `GATE_REJECT` / `required_domain_missing:healthcare`; Ophelia → passes gates and fit.
