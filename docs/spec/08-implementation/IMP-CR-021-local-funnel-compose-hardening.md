# IMP-CR-021: Local Funnel + Compose Hardening

## Metadata

| Field | Value |
|---|---|
| **Task ID** | `IMP-CR-021` |
| **CR** | `CR-021` |
| **Status** | completed |
| **Date** | 2026-05-28 |
| **Requirement IDs** | `FR-131`–`FR-150`, extends `FR-109`–`FR-130` |

## Requirements implemented

| ID | Implementation |
|---|---|
| `FR-131` | `scripts/pipeline_env.py`; defaults in `batch_pipeline.py`, `server/shared.ts` `buildPythonEnv()` |
| `FR-132` | `scripts/pre_score_jobs.py`; sort + `save_pre_score()` in `batch_pipeline.py` |
| `FR-133` | `scripts/utils.py` — no cloud fallback when `LOCAL_ONLY_MODE=1` |
| `FR-134` | `scripts/llm_stages.py` — `STAGE_MODEL_KEYS`, `stage_model()`, fit uses `qwen2.5:7b-instruct-q4_K_M` default |
| `FR-135` | `scripts/scout_local.ts` — `passesSeniorityGate()`, years regex |
| `FR-136` | `scripts/local_draft_stages.py` — `COVER_HOOK_MODE=template` default |
| `FR-137` | `assert_summary_grounded()` in `local_draft_stages.py` |
| `FR-138` | `draft_compiler.py` manifest `claim_sources`, `jd_hash` |
| `FR-139` | `server/routes/jobs.ts` — PDF compile gate on `verification_passed` |
| `FR-140` | `src/lib/grammarCheck.ts` — `analyzeGrammarIssues()`; `DocumentEditor.tsx` |
| `FR-141` | `scripts/claim_composer.py` — `assert_draft_mode_allowed()` blocks `legacy_llm` + local-only |
| `FR-142` | `scripts/jd_tailoring.py` — `load_cached_jd_profile_from_folder()` / `save_cached_jd_profile()` |
| `FR-143` | `scripts/build_claim_embeddings.py`; auto-gen in `claim_catalog._sync_embeddings()` |
| `FR-144` | `scripts/draft_linter.py` — JSON lint, no rewrite |
| `FR-145` | `scripts/verification_chain.py` — `check_anti_claims()` |
| `FR-146` | `scripts/local_draft_stages.py` — `_verb_allowed()` in `validate_bullet_for_local` |
| `FR-147` | `scripts/scout_local.ts` — `scoutAtsWatchlist()` |
| `FR-148` | `.github/workflows/smoke.yml` |
| `FR-149` | `batch_pipeline.py` — `_pruned_work_exp_for_fit()`, JSON schema fit via `call_llm_stage('fit')` |
| `FR-150` | `scripts/drafting_engine.py` — `RESEARCH_MODE`; `research-engine.py` local-first branch |

## Tasks

- [x] CR-021 change request + registry + traceability
- [x] Update FEAT-001, FEAT-004, FEAT-012, PRD §4.4
- [x] `.agent/rules/pipeline_env.md` + FR-* module headers on entrypoints
- [x] Pipeline env defaults and compose hardening (Track B)
- [x] Pre-score, strict local-only, stage models, scout gates (Track A)
- [x] DB schema columns + FTS5 bootstrap in `server/db.ts`
- [x] Smoke + regression verification

## Verification

| Command | Result | Date |
|---------|--------|------|
| `python scripts/smoke_draft_compiler.py` | passed | 2026-05-28 |
| `python scripts/test_smoke_regression.py` | 8/8 passed | 2026-05-28 |

## Unresolved / deferred

- Dedicated cross-encoder rerank model (optional; `rerank_backlog.py` + embeddings remain default).
- Golden-file regression pack for 10 frozen JDs (extend smoke when `data/*.example` fixtures added).
