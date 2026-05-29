# IMP-CR-024 — Cover Letter Conversion Engine

| Field | Value |
|-------|-------|
| **CR** | CR-024 |
| **Status** | completed |
| **Date** | 2026-05-28 |

## Summary

Implemented independent cover letter pipeline (`COVER_ENGINE=v1`), theme prose helper for resume summaries, application-first openers, batch regen of 11 submission folders, wired into `draft_compiler.py` with `PIPELINE_VERSION=CR-024-cover-engine`.

## Files added

- `scripts/cover_letter_plan.py`
- `scripts/cover_jd_needs.py`
- `scripts/cover_claim_picker.py`
- `scripts/cover_plan_builder.py`
- `scripts/cover_narrative_templates.py`
- `scripts/cover_letter_renderer.py`
- `scripts/cover_letter_audit.py`
- `scripts/cover_letter_compiler.py`
- `scripts/cover_prose.py`
- `scripts/match_thesis_builder.py`
- `scripts/pilot_cover_forbes.py`

## Files modified

- `scripts/draft_compiler.py` — `COVER_ENGINE=v1`, manifest `cover_letter_plan`, claim corpus for cover verify
- `scripts/local_draft_stages.py` — summary themes via `cover_prose`; legacy hook uses `format_themes_for_prose`
- `scripts/regenerate_all_cover_letters.py` — `COVER_ENGINE=v1`
- `scripts/regenerate_all_resumes.py` — doc note for theme prose
- `scripts/quality_checker.py` — CL-006 limit 2400 chars for Match Brief format
- `scripts/smoke_draft_compiler.py` — `test_summary_no_chained_theme_ands`

## Verification results

- `regenerate_all_resumes.py`: 11/11 OK
- `regenerate_all_cover_letters.py`: 11/11 OK (after claim-corpus verify + salary-line filter)
- Forbes cover: audit Pass, application-first opener

## Unresolved / v1.1

- Word count often ~290 vs 300–350 target (audit warns, still Pass)
- `cover_lens_frames.json` externalized templates (optional)
- Dual-plan winner archetype (deferred)
