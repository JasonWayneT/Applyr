# CR-044 — Cover Letter Value-First Structure

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `CR-043`, `FR-233`–`FR-236` |
| **Source** | CVS cover critique — circular opener, credential recitation, generic close |

## Problem

Opener stacked JD mirrors (`posting_focus`, `match_thesis`, `transferable_bridge`, tenure claims). Closing was template-safe. Strong `cover_story` bodies were undermined by templated bookends.

## Requirements

| ID | Requirement |
|---|---|
| `FR-237` | Value-first opener from primary `cover_story`; no tenure recitation; dedupe fit phrases |
| `FR-238` | `render_forward_close` uses `extract_role_challenge` from JD role prose |
| `FR-239` | `extract_ranked_needs` prefers role-action sentences over qualification bullets |

## Acceptance

- Opener has no “I bring 5+ years”, “your posting emphasizes”, or `match_thesis` stacking
- Close references adoption/analytics (or role-specific) challenge when present in JD
- `test_cover_voice.py` green; CVS regen audit Pass
