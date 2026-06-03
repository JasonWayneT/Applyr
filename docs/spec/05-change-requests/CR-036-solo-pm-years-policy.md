# CR-036: Solo PM Trap Gate + Years Policy Lock

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-036` |
| **Status** | Implemented |
| **Priority** | P1 |
| **Date** | 2026-06-02 |
| **Implements** | `FR-109` (extend), `FR-189` |

## Problem

1. **Years:** Deterministic gate allows 7 years when max=7, but local fit LLM re-penalizes (DailyPay 4–7 scored as "exceeds max").
2. **Solo vs mentorship:** `no_people_management` caused false rejects on squad PM roles with L1/L2 mentorship. Candidate wants to avoid **sole/founding PM** traps, not cross-functional or mentorship work.

## Decision

1. **Years lock** — inject `PRE-VERIFIED YEARS POLICY` in fit scoring context; strip false years penalties post-LLM when years gate passed.
2. **Solo PM gate** — new `solo_pm_gate.py` in zero-token pipeline; replace `no_people_management` with `avoid_solo_pm_trap`.
3. **Rubric** — update `job_fit_engine.md` §2.1 and §B seniority scoring.

## Acceptance

| ID | Criterion |
|----|-----------|
| `AC-119` | JD requires 7 years, max=7 → years gate passes |
| `AC-119b` | JD requires 8 years, max=7 → years gate rejects |
| `AC-194` | JD "only product manager" with no org signals → solo gate rejects |
| `AC-195` | Squad PM + product org + L1/L2 mentorship → solo gate passes |
| `AC-196` | DailyPay-class JD (4–7 years) → LLM must not cite years-over-max after years lock |

## Files

| File | Action |
|------|--------|
| `scripts/solo_pm_gate.py` | New |
| `scripts/fit_policy.py` | Years lock, strip false years penalty |
| `scripts/batch_pipeline.py` | Wire solo gate |
| `scripts/evaluate_jd_only.py` | Expose solo gate in diagnostics |
| `scripts/test_solo_pm_gate.py` | New |
| `scripts/test_seniority_years_gate.py` | New |
| `.agent/rules/job_fit_engine.md` | Rubric |
| `data/candidate_preferences.example.json` | Preference rename |
