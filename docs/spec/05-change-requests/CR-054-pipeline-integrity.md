# CR-054: Pipeline Integrity & Failure Transparency

## Metadata
- **Status**: Partially implemented (Epic 1 + Epic 3–4 partial; Epic 2 triage abbreviated; Epic 5 open)
- **Date**: 2026-06-30
- **Related requirements**: `FR-246`, `FR-247`
- **Tracker**: [IMP-CR-053-055-fit-gate-overhaul.md](../08-implementation/IMP-CR-053-055-fit-gate-overhaul.md)

## Problem
`audit_and_improve_company` could fail to converge yet `run_drafting_engine` printed unconditional success; `batch_pipeline.process_single` emitted `passed: true`. Bad enhanced drafts could remain on disk under normal filenames.

## Decision
1. **`AuditImproveResult` contract** — `converged`, `attempts`, `final_issues`, `skipped`.
2. **`run_drafting_engine` raises** on `converged=False`; `process_single` emits `passed: false`.
3. **Pre-audit snapshot restore** on non-convergence for `Resume.md`, `CoverLetter.md`, PDFs.
4. **`blocked_companies`** in `candidate_preferences.json`, checked in `passes_jd_keyword_gate` before title gate.
5. **Template lint test** for `summary_builder` output templates (`test_template_lint_sources.py`).

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-269` | Forced audit non-convergence → `passed: false` and files restored (`test_audit_convergence.py`) |
| `AC-270` | JD from `blocked_companies` entry rejected at zero-token gate (`test_blocked_companies.py`) |

## Out of scope
- Full triage of 120 `except Exception` blocks (abbreviated in epics doc)
- Lint rejection JSONL instrumentation (Epic 4.1)
