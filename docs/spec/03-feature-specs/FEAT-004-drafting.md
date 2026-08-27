# Feature Spec: FEAT-004 Drafting & Generation

## Metadata

- Feature ID: `FEAT-004`
- Status: implemented
- Source artifacts: `BMAD-SRC-004`, `BMAD-SRC-006`
- Related requirements: `FR-014`, `FR-015`, `FR-016`, `FR-017`, `FR-018`, `FR-089`–`FR-094`, `FR-100`–`FR-104`, `FR-131`–`FR-146`, `FR-138`–`FR-140`, `FR-157`–`FR-163`, `FR-193`, `FR-252`–`FR-265`
- Related change requests: `CR-014`, `CR-017`, `CR-018`, `CR-021`, `CR-024`, `CR-040`
- Cover letters: see **`FEAT-013`** (`COVER_ENGINE=v1`)

## Problem statement

Writing custom resumes for every job is the biggest bottleneck. The system must generate high-quality drafts that emphasize the transition from Platform to Growth roles.

## Goals

- `GOAL-001`: Implement "Bridge Logic" to reframe existing wins for new role priorities.
- `GOAL-002`: Export clean, single-column, machine-readable PDFs.

## Requirements covered

| Requirement ID | Summary | Notes |
|---|---|---|
| `FR-014` | Bridge Logic | Translates Platform → Growth |
| `FR-015` | Resume Generation | Uses `data/Resume.md` as template |
| `FR-016` | PDF Export | ATS-optimized |
| `FR-100`–`FR-104` | Claim composition + verification | See `FEAT-012`, `CR-017` |
| `FR-136`–`FR-138`, `FR-140`–`FR-146` | Compose hardening — template cover, summary grounding, manifest, grammar lint | `CR-021` |
| `FR-139` | PDF export gate when verification not passed | `CR-021` |
| `FR-193` | Theme primary claims + cover/resume numeric corpus alignment | `CR-040` — `theme_primaries.py`, unified cover verify corpus |
| `FR-265` | Stage 1 first-draft quality contract | `CR-102` — pair repetition, JD specificity, quality checks, defensive language, and exact rebuilt-packet provenance |

## Pipeline entry (current)

- `drafting_engine.run_drafting_engine()` → `draft_compiler.run()` (`CR-014`, `CR-017`, `CR-021`).
- Ground truth: `data/workExperience.md` via `claim_catalog.load_catalog()`.
- Default bullet path: compose mode (`claim_composer`); not monolithic LLM resume generation.
- **CR-021 defaults:** `JD_PROFILE_MODE=deterministic`, `COVER_HOOK_MODE=template`, `DRAFT_MODE=compose`. Cover body = proof bullets only; optional LLM cover hook requires explicit `COVER_HOOK_MODE=llm`.
- **Manifest:** `draft_manifest.json` includes `claim_sources`, `jd_hash`, `verification_passed` (required for manual PDF compile in UI).
- **Current Stage 1 path:** `run_submission.py` builds a closed-world packet and
  `author_from_packet.py --verify-only` blocks missing evidence/ATS terms,
  substantive resume-letter repetition, insufficient JD specificity, document
  quality failures, defensive disclaimers, and provenance-contract v2 gaps.

## Verification plan

| Test ID | Requirement/AC IDs | Test type | Expected result | Status |
|---|---|---|---|---|
| `TEST-004` | `FR-014` | manual | Resume highlights "User Scaling" even if source says "API Stability" | verified |
