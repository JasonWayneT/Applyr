# FEAT-013: Cover Letter Conversion Engine

- Feature ID: `FEAT-013`
- Change request: `CR-024`
- Related: `FEAT-004` (drafting), `FEAT-012` (compiler)

## Purpose

Generate **conversion-oriented** cover letters that complement resumes: JD match argument, grounded proofs from `master_claims.json`, employer-value framing — without reading `Resume.md` or pasting resume bullets.

## Requirements

| ID | Summary |
|----|---------|
| `FR-157` | `COVER_ENGINE=v1` Match Brief compiler |
| `FR-158` | Cover selection uses JD + catalog only |
| `FR-159` | `cover_letter_plan.json` per submission |
| `FR-160` | Application-first opener (not “Company is hiring…”) |
| `FR-161` | `format_themes_for_prose` for summary and cover themes |
| `FR-162` | `cover_letter_audit` weighted rubric |
| `FR-163` | `ranked_needs` from JD responsibilities |

## User-visible behavior

1. Batch or single-job draft produces `CoverLetter.md` + PDF alongside resume.
2. Letter opens with “I am applying for the {role} at {company}…”
3. Two body paragraphs: context → claim proof → employer bridge.
4. Plan file documents which claims and JD needs were used.

## Cover voice (CR-043)

- Deterministic phrasing via `scripts/cover_phrasing.py` — see `cover_voice.example.md`
- Word band **300–400**; proof bodies are `cover_story` without robot JD bridges
- No LLM voice rewrite on submission path

## Out of scope (v1)

- Full-letter local LLM prose
- LLM voice rewrite pass
- Gemini/cloud cover generation
- Reading resume for complement selection (optional overlap **warning** only, post-hoc)

## Entry points

- `scripts/draft_compiler.py` when `skip_cover` is false
- `scripts/regenerate_all_cover_letters.py` (`COVER_ONLY=1`, `COVER_ENGINE=v1`)
- `scripts/pilot_cover_forbes.py` (smoke)

## Acceptance

See `CR-024` criteria `AC-164`–`AC-169`.
