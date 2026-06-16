# CR-050 — Deterministic Resume Conversion Loop

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `FR-246`, `FR-247`, `FR-248`, `FR-249`, `FR-250` |
| **Source** | Iterative fleet conversion loop (2026-06) |

## Problem

Post CR-049, blocking conversion failures are rare but shared template defects remain:

1. **CW-012** — Sterkly sections with certificate/macOS jargon and no PM-context bullet (stripe).
2. **Summary/bullet verbatim overlap** — proof sentence copies capacity-model or other experience bullets (dignifi archetype).
3. **CW-001 fleet-wide** — activity-only Sterkly “Translated…” bullets in most folders.
4. **Low rubric scores** — senior-role coordination bullets selected over quantified outcomes.

## Requirements

| ID | Requirement |
|---|---|
| `FR-246` | `fleet_document_qa.py` ranks fleet by blocking codes, CW-016, CW-001, rubric |
| `FR-247` | `check_summary_bullet_overlap()` emits CW-016 for verbatim summary/bullet dup |
| `FR-248` | Hardened `enforce_sterkly_context()` + pre-write CW-012 guard in draft_compiler |
| `FR-249` | `enforce_activity_cap()` swaps activity bullets for metric claims when available |
| `FR-250` | Summary proof ranking penalizes body-bullet overlap; `_proof_allowed()` rejects substring dup |

## Balanced exit bar

- 26/26 conversion critique pass (CW-009–CW-015)
- CW-001 ≤ 5 folders (manifest warnings)
- Zero CW-016 fleet-wide
- Rubric overall ≥ 65 every folder

## Acceptance criteria

- `AC-262`: stripe regen passes `evaluate_resume_conversion()` without CW-012
- `AC-263`: dignifi summary proof does not verbatim-match any experience bullet
- `AC-264`: `fleet_document_qa.py` reports balanced bar status
- `AC-265`: fleet regen 26/26 with balanced exit bar met

## Files

- `scripts/fleet_document_qa.py`
- `scripts/resume_conversion_eval.py`
- `scripts/conversion_framing.py`
- `scripts/local_draft_stages.py`
- `scripts/draft_compiler.py`
- `scripts/quality_checker.py`
- `scripts/test_resume_conversion_eval.py`
- `scripts/test_summary_builder.py`
