# CR-014: Unified Draft Compiler (Single Pipeline, All Providers)

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-014` |
| **Status** | Implemented |
| **Priority** | P0 |
| **Date** | 2026-05-20 |
| **Supersedes** | Monolithic `_run_gemini_monolithic_draft`; dual-path routing in `run_drafting_engine` |
| **Builds on** | `CR-012`, `CR-013` |
| **Implements** | `FR-089`, `FR-090`, `FR-091`, `FR-092`, `FR-093`, `FR-094` |

## Decision

One **draft compiler** stage graph for Gemini, local, and mixed deployments. Models only power micro-steps (JD profile JSON, claim selection JSON, one bullet per claim). Structure, assembly, summary, cover, guards, and PDF are code-owned.

## Locked policy

| Topic | Policy |
|-------|--------|
| `llm_verify_claims` | Retired for compiler output |
| Research packet | Cheat sheet / interview prep only — not in resume or cover |
| Providers | `call_llm_stage(stage_id)` with per-stage `['gemini','local']` preference |
| Fit input | `evaluation_result.Summary` boosts `JdProfile` / claim scores |
| Manifest | `draft_manifest.json` (rename from `local_draft_manifest.json`) |

## Stage graph (0–11 + cheat sheet)

| Stage | Name | LLM | Notes |
|-------|------|-----|-------|
| 0 | Save `Original_JD.txt` | No | |
| 1 | `JdProfile` | Optional JSON | Validated substrings only |
| 2 | Select claims / employer | Optional JSON | Uses fit summary + jd scores |
| 3 | Bullet per claim | Yes | Only hot loop; gates + fallback |
| 4 | Order + char budget | No | |
| 5 | Summary template | No | JD themes from profile |
| 6 | Cover template + bridges | No | `pick_cover_bullets` |
| 7 | Render markdown | No | |
| 8 | `verify_content` with `[ID]` then strip | No | |
| 9 | Guards + QA + PDF | No | |
| 10 | `draft_manifest.json` | No | |
| 11 | `generate_cheat_sheet` | Gemini | Post-pass, separate |

## Files to create / change

| File | Action |
|------|--------|
| `scripts/draft_compiler.py` | **New** — sole drafting entry from `run_drafting_engine` |
| `scripts/jd_tailoring.py` | **New** — `JdProfile`, scoring, bridge hints |
| `data/bridge_phrases.json` | **New** — FR-014 allowlist |
| `scripts/drafting_engine.py` | Remove `_run_gemini_monolithic_draft`; delegate to compiler |
| `scripts/bullet_generation.py` | Stage 3 bullets + `fallback_bullet()` |
| ~~`scripts/local_draft_pipeline.py`~~ | **Deleted** (was thin wrapper) |
| ~~`scripts/batch_pipeline_new_only.py`~~ | **Deleted** (duplicate of batch_pipeline) |
| ~~`scripts/repair_resume_content.py`~~ | **Deleted** (superseded by compiler min bullets) |
| `docs/spec/02-requirements-registry.md` | FR-089–094 |
| `scripts/smoke_draft_compiler.py` | **New** |

## Acceptance criteria

- **AC-091:** Same section structure for gemini-only vs local-only runs
- **AC-092:** `draft_manifest.json` lists claim IDs and `pipeline_version`
- **AC-093:** No invented numerics vs bullet corpus
- **AC-094:** No monolithic draft function called from `run_drafting_engine`
