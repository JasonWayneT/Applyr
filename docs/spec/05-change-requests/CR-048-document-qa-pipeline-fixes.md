# CR-048 — Document QA Pipeline Fixes

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `FR-103`, `FR-105`, `FR-233`, `CLW-005` |
| **Source** | Fleet document QA audit (2026-06) |

## Problem

Submission fleet audit found pipeline defects that passed existing gates:

1. **Cover grammar seam** — `cover_phrasing.py` replaced `no surviving documentation` → `no documentation remained` inside `had no surviving documentation`, producing ungrammatical text (CVS, DAT).
2. **Company display casing** — slug `.title()` produced `Cvs Health` instead of JD header `CVS Health`.
3. **Redundant close targets** — `render_structured_close` could emit `improve analytics product adoption, strengthen product adoption`.
4. **Bullet length drift** — validation failure returned full catalog lines (>28 words); 51 CW-003 warnings across fleet.

## Requirements

| ID | Requirement |
|---|---|
| `FR-237` | `check_cover_grammar_defects()` flags CLW-005 phrase-polish seams; cover audit penalizes |
| `FR-238` | `resolve_company_display_name()` prefers Original_JD.txt / JD header over slug title |
| `FR-239` | `enforce_bullet_word_budget()` fits bullets when validation allows without dropping metrics |
| `FR-240` | Cover close dedupes overlapping JD targets (analytics product adoption vs product adoption) |

## Acceptance criteria

- `AC-253`: `apply_voice_polish("had no surviving documentation")` never contains `documentation remained`
- `AC-254`: `resolve_company_display_name("cvs_health", company_folder=...)` returns `CVS Health` when Original_JD.txt starts with that line
- `AC-255`: CVS-style JD close does not repeat overlapping adoption targets
- `AC-256`: Fleet bullets from catalog sources fit ≤28 words without incomplete endings

## Files

- `scripts/cover_phrasing.py`
- `scripts/cover_letter_audit.py`
- `scripts/company_slug.py`
- `scripts/draft_compiler.py`
- `scripts/bullet_fit.py`
- `scripts/claim_composer.py`
- `scripts/batch_pipeline.py`
- `scripts/test_cover_voice.py`
- `scripts/test_company_slug.py`
- `scripts/test_bullet_fit_enforce.py`
