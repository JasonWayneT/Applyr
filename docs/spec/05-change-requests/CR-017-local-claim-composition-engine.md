# CR-017: Local Claim Composition Engine

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-017` |
| **Status** | Implemented |
| **Priority** | P0 |
| **Date** | 2026-05-21 |
| **Builds on** | `CR-014`, `CR-012` |
| **Implements** | `FR-100`, `FR-101`, `FR-102`, `FR-103`, `FR-104` |

## Decision

Default drafting uses **compose mode**: bullets are rendered from `workExperience.md` Section 5 ACC inventory with Section 3 VOC replacements and JD bridge prefixes — not free-form local LLM rewrites. A fail-closed `verification_chain` and `recruiter_qa` gate run before Backlog.

## Policy

| Topic | Policy |
|-------|--------|
| `DRAFT_MODE` | Default `compose`; `legacy_llm` for experiments |
| `LOCAL_ONLY_MODE` | Env `1` or `primaryProvider: local` → local-only LLM stages + fit eval |
| Cloud drafting | Deprecated on hot path |
| Skills | No new `.agent/skills`; Python is source of truth |

## Acceptance criteria

- **AC-100:** No `ACC-`/`MET-`/`VOC-` tokens in final PDF text
- **AC-101:** `draft_manifest.json` lists claim IDs; compose mode recorded
- **AC-102:** `verify_content` failure blocks pipeline
- **AC-103:** Cover uses `display_company` from DB
- **AC-104:** Summary ≤380 chars; not full bullet paste
- **AC-105:** `verification_passed: true` in manifest when Backlog-eligible

## Files

| File | Action |
|------|--------|
| `scripts/claim_catalog.py` | New |
| `scripts/claim_composer.py` | New |
| `scripts/verification_chain.py` | New |
| `scripts/recruiter_qa.py` | New |
| `scripts/draft_compiler.py` | CR-017 orchestration |
| `scripts/verify_claims.py` | Extended `strip_ids` |
| `scripts/drafting_engine.py` | Education header fix; display name |
| `scripts/llm_stages.py` | Local-first / local-only |
| `scripts/batch_pipeline.py` | Display company; local fit |
| `docs/spec/08-implementation/IMP-CR-017-claim-composition-engine.md` | Implementation tasks + verification log |

## SDD verification (2026-05-21)

| Layer | Artifact | Status |
|-------|----------|--------|
| Business | `JobAgent_Architecture_and_PRD.md` §4.4 | updated |
| Spec | `FEAT-004`, `FEAT-012`, `02-requirements-registry`, `DESIGN-002` | updated |
| Implementation | `IMP-CR-017` | completed |
| Code | Module docstrings `# Implements FR-*` | updated |
| Test | `scripts/smoke_draft_compiler.py` | passed |
