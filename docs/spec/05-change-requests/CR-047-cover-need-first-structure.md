# CR-047 — Cover Letter Block Structure (Universal + Marketplace Variant)

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `CR-044`, `CR-043`, `CR-024`, `FR-237`–`FR-239` |
| **Source** | Splash Financial cover iteration (v1→v7); pipeline critique |

## Problem

All covers shared the same weaknesses Splash exposed: thin proof transitions, redundant story sentences, generic closes, and no work-history bridge. Marketplace/fintech JDs additionally needed a need-first opener and proof reordering.

## Requirements

| ID | Requirement |
|---|---|
| `FR-240` | **All** letters render via `build_cover_blocks()` (single path in `cover_letter_renderer.py`) |
| `FR-241` | Universal: work-history bridge on first proof, proof ladders, phrase polish, legacy short graf, `render_structured_close()` |
| `FR-242` | `marketplace_fintech` variant: need-first opener, proof reorder, Splash-tuned proof bodies |
| `FR-243` | `application_first` variant: CR-044 value-first opener retained; same bridge/ladder/close machinery |
| `FR-244` | Audit accepts need-first intent; word band 250–400 for `need_first`, 300–400 otherwise |

## Acceptance

- Splash `Original_JD.txt` regen: need-first opener, Cision bridge, lender onboarding ladder, 40% + 7% metrics, borrower offer experience close
- `test_cover_splash_golden.py` green
- `test_cover_voice.py` + `test_cover_claim_picker.py` green
- Analytics/platform regen: application-first opener + bridge + adoption ladder + structured close
- `test_cover_structure_universal.py` green

## Files

- `scripts/cover_letter_structure.py` (new)
- `scripts/cover_plan_builder.py`
- `scripts/cover_letter_renderer.py`
- `scripts/cover_phrasing.py`
- `scripts/cover_jd_needs.py`
- `scripts/cover_letter_audit.py`
- `scripts/test_cover_splash_golden.py`
