# IMP-CR-039: Transferable Skills Over Domain Gate

**CR:** `CR-039-transferable-skills-over-domain-gate.md`  
**Requirements:** `FR-192` (supersedes FR-190 gate behavior)

## Tasks
- [x] Remove zero-token domain reject and fit cap
- [x] `transferable_skills_prompt_block` + default policy injection
- [x] `domain_gaps` informational in evaluate tooling
- [x] Rubric + prefs `score_on_transferable_skills: true`

## Verification
```bash
python scripts/test_domain_gate.py
python scripts/test_fit_policy.py
python scripts/evaluate_jd_only.py jobs/_eval_cotiviti_pm.txt "Cotiviti Healthcare"
```

Expected: Cotiviti passes zero-token gates; `domain_gaps` lists healthcare; fit scored on transferable skills.
