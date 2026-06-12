# CR-043 — Deterministic Cover Letter Voice

| Field | Value |
|---|---|
| **Status** | implemented |
| **Related** | `CR-024`, `CR-023`, `FR-157`–`FR-163` |
| **Source** | My Voice Writer learnings; CVS cover regen feedback |

## Problem

Cover engine v1 passed audit but sounded robotic: repeated JD bridges, `bridge_para` filler, and tight 350-word trim. User voice is plain, direct, human — not casual dictation, not corporate AI.

## Requirements

| ID | Requirement |
|---|---|
| `FR-233` | `cover_phrasing.py` deterministic voice rules; no LLM rewrite on submission path |
| `FR-234` | Cover word band 300–400; metrics preserved in proofs |
| `FR-235` | Proof paragraphs use `cover_story` only (no “That experience is relevant to…” bridge) |
| `FR-236` | Opener embeds JD audit fragment via `jd_presence_clause`; `cover_story` uses resource-constraints language (FR-096) |

## Acceptance

- `AC-261`: Rendered cover has no `BANNED_ROBOT_PHRASES` strings
- `AC-262`: Audit word band 300–400 documented and enforced
- `AC-263`: `test_cover_voice.py` green; CVS cover regen audit Pass

## Files

- `scripts/cover_phrasing.py`
- `scripts/cover_letter_renderer.py`
- `scripts/cover_narrative_templates.py`
- `scripts/cover_letter_audit.py`
- `docs/spec/03-feature-specs/cover_voice.example.md`
- `data/master_claims.json` (cover_story tone)
