# CR-049 — Resume Summary Hardening & Fleet QA Fixes

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `FR-223`, `FR-241`, `FR-242`, `FR-243`, `FR-244` |
| **Source** | Fleet resume document QA audit (2026-06) |

## Problem

Fleet audit found submission-blocking resume defects that passed legacy QA:

1. **Truncated summary proofs** — comma-clause extraction and char-cap fallback produced clauses ending at “…platform teams.”
2. **Stacked summary proofs** — MIN_SENTENCES padding appended a second proof sentence (dignifi: 4 sentences).
3. **Near-duplicate metric bullets** — two Cision bullets both describing 40% data failure.
4. **Missing experience dates** — catalog fallback headers lacked dates/locations.
5. **Summary/bullet verbatim duplication** — proof sentence copied capacity bullet at 65%+ overlap.

## Requirements

| ID | Requirement |
|---|---|
| `FR-241` | `dedupe_metric_collision_bullets()` drops lower-scored duplicate metric stories |
| `FR-242` | `CANONICAL_EMPLOYER_HEADERS` + `ensure_experience_skeleton_headers()` restore dates/locations |
| `FR-243` | `_coalesce_summary_parts()` enforces max one proof; `_pad_summary_template_parts()` hits R-010 min without second proof |
| `FR-244` | `check_resume()` surfaces CW-011/CW-013 as R-012 FAIL; `SKIP_PDF_EXPORT` for resume-only regen |
| `FR-245` | `sanitize_em_dashes()` on retry assembly path (education style ref) |

## Acceptance criteria

- `AC-257`: dignifi-style truncated attribution clauses never ship from `_summary_proof_from_bullet`
- `AC-258`: summary has at most 3 sentences with at most 1 proof
- `AC-259`: duplicate 40% data bullets reduced to one per resume
- `AC-260`: experience headers include dates on regen
- `AC-261`: fleet sample (dignifi, cvs_health, allstate) passes `evaluate_resume_conversion()` without CW-011/CW-013

## Files

- `scripts/local_draft_stages.py`
- `scripts/candidate_context.py`
- `scripts/draft_compiler.py`
- `scripts/drafting_engine.py`
- `scripts/quality_checker.py`
- `scripts/regenerate_all_resumes.py`
- `scripts/test_summary_builder.py`
