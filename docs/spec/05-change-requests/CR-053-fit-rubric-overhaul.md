# CR-053: Fit Rubric Overhaul (Evidence-Tiered Scoring)

## Metadata
- **Status**: Partially implemented (Epics 1–3 complete; Epic 4–5 open)
- **Date**: 2026-06-30
- **Supersedes**: Holistic LLM 0–100 scoring as primary path; **partially supersedes** `FR-188` anchor-floor score promotion (now risk-only)
- **Related requirements**: `FR-242`, `FR-243`, `FR-248`
- **Tracker**: [IMP-CR-053-055-fit-gate-overhaul.md](../08-implementation/IMP-CR-053-055-fit-gate-overhaul.md), [CR-053-fit-rubric-overhaul-epics.md](../08-implementation/CR-053-fit-rubric-overhaul-epics.md)

## Problem
Fit score was a single opaque LLM call returning `Score: 0–100` with no per-criterion breakdown. Location leaks dominated real self-rejects. Domain mismatch was excluded entirely (`CR-039`). `apply_anchor_floor` promoted borderline scores using generic anchor keywords.

## Decision
1. **Structured fit primary path** (`scripts/structured_fit.py`, `STRUCTURED_FIT=1` default): extract must-haves → narrow LLM equivalence judgments (yes/partial/no, no numbers) → deterministic weighted score + confidence routing.
2. **Location gate hardening** (`zero_shot_classifier.py`): reject non-SD onsite/hybrid, Canada in-person, EST/CST-only remote before scoring.
3. **Domain as bounded penalty** (max −10), not a separate weighted column or zero-token gate.
4. **Anchor hits** append `RiskFlags` only; no score overwrite (`fit_policy.apply_anchor_floor`).
5. **Legacy LLM scoring** remains fallback when `STRUCTURED_FIT=0` or structured path returns nothing.

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-264` | `evaluate_job_fit` uses structured path by default; score computed in code not taken from LLM integer |
| `AC-265` | Hybrid NYC / onsite Chicago fixtures reject at location gate (`test_location_gate.py`) |
| `AC-266` | IAM-required JD scores lower than equivalent JD without required domain gap (`test_structured_fit.py`) |
| `AC-271` | `materializeJobSearchPrefs` preserves `blocked_role_titles`, `blocked_focus_area_words`, `blocked_companies` |

## Out of scope (this CR)
- Full 10-case calibration matrix (Epic 4.3)
- `job_fit_engine.md` aspirational Stage B rubric weights as LLM-only path
- Scout-side `clusterDedup` wiring (see CR-054 Epic 5)
