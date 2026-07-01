# CR-055: Collection Gate Accuracy

## Metadata
- **Status**: Partially implemented (Epics 1–2 complete; Epic 3 open)
- **Date**: 2026-06-30
- **Related requirements**: `FR-244`, `FR-245`, `FR-248`
- **Tracker**: [IMP-CR-053-055-fit-gate-overhaul.md](../08-implementation/IMP-CR-053-055-fit-gate-overhaul.md)

## Problem
1. **Years gate** parsed incidental figures (e.g. Jackson Laboratory "90 years" of history) as experience requirements.
2. **Title blocklist** used whole-line substring match — `Product Manager, Growth` and NVIDIA "Developer Productivity" false-blocked.

## Decision
1. **Requirements-anchored years parsing** in `seniority_gate.parse_max_years_required` with plausibility cap (shared with CR-053 must-have extraction story).
2. **Two-list title model**: `blocked_role_titles` (always block) vs `blocked_focus_area_words` (block only when focus word is primary role, not `PM, Growth` pattern).
3. **Rollout automation**: `apply_gate_rollout.py` / `npm run gate-rollout` merges example keys into live prefs.
4. **Legacy `blocked_titles`** still supported; split lists preferred.

## Acceptance criteria
| ID | Criterion |
|----|-----------|
| `AC-267` | Jackson Lab / Civica fixtures do not parse incidental years (`test_seniority_years_gate.py`) |
| `AC-268` | `Product Manager, Growth` passes; `Head of Growth` blocks (`test_title_blocklist.py`) |

## Out of scope
- `freshness_days: 7` policy change (Epic 3 — needs manual URL sampling + Jason decision)
