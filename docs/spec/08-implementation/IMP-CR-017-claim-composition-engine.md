# IMP-CR-017: Claim Composition Engine

## Metadata

| Field | Value |
|---|---|
| **Task ID** | `IMP-CR-017` |
| **CR** | `CR-017` |
| **Status** | completed |
| **Date** | 2026-05-21 |

## Requirements implemented

| ID | Implementation |
|---|---|
| `FR-100` | `scripts/claim_catalog.py` — `load_catalog()`, `apply_voc_map()`, `sanitize_claim_text()` |
| `FR-101` | `scripts/claim_composer.py` — default compose path; `DRAFT_MODE=legacy_llm` → `bullet_generation` |
| `FR-102` | `scripts/verification_chain.py` — `verify_document_bundle()` fail-closed |
| `FR-103` | `batch_pipeline._resolve_display_company()` → `draft_compiler.run(display_name=)` |
| `FR-104` | `scripts/recruiter_qa.py` — invoked from verification chain |

## Tasks

- [x] Parse ACC inventory from `workExperience.md` Section 5
- [x] Wire compose mode as default in `bullet_generation` / `claim_composer`
- [x] Extend `strip_ids` for pipe and bare token formats
- [x] Fix resume education header (`## EDUCATION` only on resumes)
- [x] Summary v2 and cover v2 templates in `local_draft_stages`
- [x] Local-first / `LOCAL_ONLY_MODE` in `llm_stages` and fit eval
- [x] `draft_manifest.json`: `verification_passed`, `display_company`, `draft_mode`
- [x] Smoke tests in `scripts/smoke_draft_compiler.py`

## Verification

| AC | Result |
|---|---|
| `AC-100` | `strip_ids` + `recruiter_qa` token scan; smoke `test_strip_ids_pipe_tokens` |
| `AC-101` | Manifest fields written in `draft_compiler.run()` |
| `AC-102` | `verify_content` raises `DraftingPipelineError` on failure |
| `AC-103` | `_resolve_display_company` + cover `assemble_cover_letter_deterministic(display)` |
| `AC-104` | `build_summary_deterministic` uses `_first_metric_clause` |
| `AC-105` | `verification_passed: true` only after full chain |

Command: `python scripts/smoke_draft_compiler.py` — passed 2026-05-21.

## Deferred

- `IMP-CR-017-b` Symphony-style `draft_orchestrator` (reconcile-dispatch tick) — Phase 1b per plan.
