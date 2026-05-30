# CR-ARCH-001 — Phase 0 Baseline Tests and Guards

**Status:** Implemented  
**Date:** 2026-05-30  
**Implements:** Architecture refactor PR-01

## Summary

- REG-15 title gate parity tests in `test_smoke_regression.py`
- VERIFY-01 Tier A tests in `test_verify_chain.py`
- VERIFY-02 `process_single` gate-reject test in `test_batch_gate.py`
- Spawn path CI guard in `check_spawn_paths.py`
- Fix `re_score_jobs.py` to use `get_min_fit_score()` from `utils`

## Verification

```bash
python scripts/test_verify_chain.py
python scripts/test_batch_gate.py
python scripts/check_spawn_paths.py
python scripts/test_smoke_regression.py
```

## Traceability

| Test ID | Requirement |
|---------|-------------|
| REG-15 | Gate parity (batch title) |
| VERIFY-01 | Verification chain unit |
| VERIFY-02 | Batch orchestrator gate path |
