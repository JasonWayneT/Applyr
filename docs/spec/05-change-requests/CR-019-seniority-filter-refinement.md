# CR-019: Seniority Filter Refinement

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-019` |
| **Status** | Implemented |
| **Priority** | P1 |
| **Date** | 2026-05-26 |
| **Implements** | `FR-109`, `FR-110` |

## Decision

Replace blunt "Senior" title blocking with years-first gating. Keep hard rejects for Lead/Director/entry/0-to-1 titles. Add deterministic years parser and word-boundary title matching.

## Acceptance

- **AC-115:** "Senior Product Manager" title with ≤7 years required passes zero-token title gate
- **AC-116:** "Lead Product Manager" fails title gate
- **AC-117:** JD requiring 10+ years fails years gate when max=7
- **AC-118:** JD mentioning AI tools as plus does not auto-reject (LLM rubric)

## Files

| File | Action |
|------|--------|
| `scripts/seniority_gate.py` | New |
| `scripts/batch_pipeline.py` | Wire gates |
| `scripts/scout_local.ts` | Word-boundary title gate |
| `data/job_fit_engine.md` | Rubric |
| `src/pages/SyncActivityView.tsx` | Defaults + max years UI |
