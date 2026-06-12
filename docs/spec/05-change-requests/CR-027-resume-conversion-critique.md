# CR-027 — Resume Conversion Critique & PDF Header Fix

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `FR-220`–`FR-222`, `FR-215`, `FR-216`–`FR-219` |
| **Source** | CVS Health conversion loop feedback (2026-06) |

## Problem

External reviewers flagged three systemic issues the rubric did not catch:

1. **PDF experience headers inverted** — `compile_single.py` treated `Title | Company | Dates` as two segments; `float:right` pushed company/title to the page bottom while location lines read as section headers.
2. **Incomplete summary sentences** — proof clause truncation at 175 chars produced dangling clauses ("…that other internal platform teams.").
3. **Sterkly narrative gap** — metric enforcement produced macOS/certificate-only bullets with no PM-context bridge.

## Requirements

| ID | Requirement |
|---|---|
| `FR-220` | `evaluate_resume_conversion()` runs after PDF export; logs `conversion_critique` to manifest |
| `FR-221` | `compile_single.py` renders three-part experience headers with flex layout (no print float) |
| `FR-222` | `enforce_sterkly_context()` injects context claim when jargon ≥2 and no context signal |
| `FR-223` | One-proof summary: `build_summary_deterministic()` appends max one grounded proof; `check_summary_prose_quality()` flags CW-013 |
| `FR-224` | Experience-backed themes: `experience_theme_guard.py` filters summary focus phrases; transferable JD themes in cover `match_thesis`; CW-014 |

## Acceptance criteria

- `AC-244`: PDF text order shows company name before location and before section bullets
- `AC-245`: Summary proof rejects incomplete trailing clauses; CVS attribution proof completes with "sought to adopt it"
- `AC-246`: Sterkly section includes ≥1 context bullet when macOS jargon count ≥2
- `AC-247`: `draft_manifest.json` contains `conversion_critique.pass` boolean
- `AC-248`: summary contains exactly one proof sentence (no stacked participle fragments); CW-013 blocks multi-proof summaries
- `AC-249`: summary never claims JD-only themes (e.g. analytics) without bullet support; cover letter states transferable fit instead

## Files

- `scripts/compile_single.py`
- `scripts/resume_conversion_eval.py` (new)
- `scripts/local_draft_stages.py`
- `scripts/conversion_framing.py`
- `scripts/quality_checker.py`
- `scripts/draft_compiler.py`
- `scripts/test_resume_conversion_eval.py` (new)
