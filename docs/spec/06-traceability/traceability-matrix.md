# Traceability Matrix

Use this matrix to prove that each requirement has a spec, task, implementation, and verification path.

## Matrix

| Requirement ID | Source | Feature spec | Code/modules | Status |
|---|---|---|---|---|
| `FR-001` | `BMAD-SRC-001` | `FEAT-001` | `server/scout.ts` | implemented |
| `FR-002` | `BMAD-SRC-001` | `FEAT-001` | `scripts/openpostings.py` | implemented |
| `FR-006` | `BMAD-SRC-005` | `FEAT-002` | `scripts/batch_pipeline.py` | implemented |
| `FR-007` | `BMAD-SRC-005` | `FEAT-002` | `scripts/batch_pipeline.py` | implemented |
| `FR-011` | `BMAD-SRC-007` | `FEAT-003` | `scripts/research-engine.py` | implemented |
| `FR-014` | `BMAD-SRC-004` | `FEAT-004` | `scripts/drafting_engine.py` | implemented |
| `FR-019` | `BMAD-SRC-006` | `FEAT-005` | `scripts/drafting_engine.py` | implemented |
| `FR-023` | `BMAD-SRC-003` | `FEAT-006` | `server/index.ts` | implemented |
| `FR-024` | `BMAD-SRC-003` | `FEAT-006` | `src/pages/SyncActivityView.tsx` | implemented |

## Coverage checklist

- [x] Every P0 requirement has acceptance criteria.
- [x] Every accepted requirement maps to at least one spec.
- [x] Every accepted requirement maps to implementation tasks.
- [x] Every accepted requirement maps to tests or an explicit manual verification method.
- [x] Every bug fix has a regression test or documented exception.
- [x] Every ADR maps to affected requirements or constraints.
