# IMP-CR-053 / 054 / 055: Fit, Pipeline & Collection Gate Overhaul

**Specs:** `CR-053-fit-rubric-overhaul.md`, `CR-054-pipeline-integrity.md`, `CR-055-collection-gate-accuracy.md`  
**Epics tracker:** [CR-053-fit-rubric-overhaul-epics.md](./CR-053-fit-rubric-overhaul-epics.md)  
**Requirements:** `FR-242`–`FR-248`, `AC-264`–`AC-271`

## Implemented

### CR-053
- [x] `scripts/structured_fit.py` — FitReport, equivalence LLM, deterministic score, confidence routing
- [x] `scripts/batch_pipeline.py` — structured path default (`STRUCTURED_FIT=1`)
- [x] `scripts/zero_shot_classifier.py` — location gate extensions
- [x] `scripts/fit_policy.py` — anchor floor demoted to risk flags
- [x] `scripts/calibration_harness.py`, `scripts/rescore_location_gates.py`
- [x] Tests: `test_structured_fit.py`, `test_location_gate.py`

### CR-054
- [x] `scripts/audit_and_improve.py` — AuditImproveResult + snapshot restore
- [x] `scripts/drafting_engine.py` — raise on audit failure
- [x] `scripts/batch_pipeline.py` — `blocked_companies` gate
- [x] Tests: `test_audit_convergence.py`, `test_blocked_companies.py`, `test_template_lint_sources.py`

### CR-055
- [x] `scripts/seniority_gate.py` — years anchoring + title split
- [x] `data/candidate_preferences.example.json` — split lists + blocked_companies
- [x] `scripts/prefs_rollout.py`, `scripts/apply_gate_rollout.py`
- [x] `server/domain/jobSearchPrefs.ts` — `PRESERVE_PIPELINE_PREF_KEYS` (FR-248)
- [x] Tests: `test_seniority_years_gate.py`, `test_title_blocklist.py`, `test_prefs_rollout.py`, `tests/unit/jobSearchPrefs.test.ts`

- [x] `job_fit_engine.md` v5.0 — structured fit, gates, anchor risk-only (SDD closeout)
- [x] Registry `FR-242`–`FR-248`, traceability matrix, formal CR-053/054/055 specs

## Open
- [ ] Epic 4.2–4.3 calibration disagreements (DB `jd_text` gaps)
- [ ] Epic 5 rollout sanity batch on live backlog
- [ ] CR-054 Epic 5 — wire `clusterDedup` into scout ingest
- [ ] CR-055 Epic 3 — freshness window validation

## Verification
```bash
npm test
npm run gate-rollout
python scripts/calibration_harness.py --limit 30
```

## Rollout
```bash
npm run gate-rollout        # merge prefs + location dry-run
npm run gate-rollout:apply  # merge prefs + apply location rejects
```
