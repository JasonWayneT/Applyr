# CR-021: Local Funnel + Compose Hardening (40-item plan)

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-021` |
| **Date** | 2026-05-28 |
| **Status** | Implemented |
| **Priority** | P0 |
| **Author** | Jason Taylor / Agent |
| **Implements** | `FR-131`–`FR-150` (extends `FR-109`, `FR-111`–`FR-130` wiring) |

## Problem statement

The 40-item local-first improvement plan combined funnel efficiency (scout → fit → draft) with resume/cover anti-hallucination hardening. CR-017/018 established compose-mode drafting, but:

1. Cover letter paragraph 1 still used an optional LLM hook that could invent JD skills.
2. `JdProfile` LLM extraction could introduce themes not substring-valid in the JD.
3. Batch fit evaluation sent full work-experience text and could fall back to Gemini under misconfiguration.
4. Scout ingested roles that batch gates would reject (years/title), wasting scrape and VRAM.
5. SDD traceability for the combined plan was incomplete on first code landing.

## Solution overview

### Track A — Funnel (items A1–A20)

| # | Item | Requirement | Code |
|---|------|-------------|------|
| A1 | Scout seniority + years | `FR-135` | `scout_local.ts` |
| A2 | Pre-score before fit | `FR-132` | `pre_score_jobs.py`, `batch_pipeline.py` |
| A3 | Strict local-only | `FR-133` | `utils.py` |
| A4 | Stage-specific models | `FR-134` | `llm_stages.py` |
| A5 | Embed at ingest | `FR-111` | existing vector save in batch |
| A6 | DOM cleanup | `FR-117` | `dom_cleanup` in batch |
| A7 | BM25 prune fit context | `FR-149` | `_pruned_work_exp_for_fit()` |
| A8 | JSON schema fit | `FR-149` | `call_llm_stage('fit')` + schema |
| A9 | JdProfile cache | `FR-142` | `jd_profile_cache.json` per folder |
| A10 | Local research | `FR-150` | `RESEARCH_MODE`, SearXNG path |
| A11 | Metadata tagger | `FR-115` | existing `tag_job_metadata` |
| A12 | UI rerank | `FR-114` | existing `/api/jobs/rerank` |
| A13 | Cross-encoder rerank | — | deferred; BM25+embed rerank |
| A14 | FTS5 search | `FR-116` | `server/db.ts` jobs_fts |
| A15 | Truncation guard | `FR-126` | existing `utils._truncate_prompt` |
| A16 | Skill gap | `FR-120` | existing route |
| A17 | ATS watchlist | `FR-147` | `scoutAtsWatchlist()` |
| A18 | CI smoke | `FR-148` | `.github/workflows/smoke.yml` |
| A19 | Compose enforcement | `FR-131` | env defaults |
| A20 | Settings/env docs | `FR-131` | `buildPythonEnv`, README via release notes |

### Track B — Drafting (items B1–B20)

| # | Item | Requirement | Code |
|---|------|-------------|------|
| B1 | Deterministic JdProfile | `FR-131` | `JD_PROFILE_MODE` |
| B2 | Template cover hook | `FR-136` | `COVER_HOOK_MODE` |
| B3 | Summary grounding | `FR-137` | `assert_summary_grounded()` |
| B4 | Numeric whitelist | `FR-146` | `_verify_bullet_local` + verb gate |
| B5 | Block legacy_llm | `FR-141` | `assert_draft_mode_allowed()` |
| B6 | Claim embeddings | `FR-143` | `build_claim_embeddings.py` |
| B7 | Cover proof rules | `FR-136` | `pick_cover_bullets()` metric dedup |
| B8 | Manifest audit | `FR-138` | `draft_manifest.json` |
| B9 | Style guard | `FR-074` | existing in `draft_compiler` |
| B10 | Anti-claim | `FR-145` | `check_anti_claims()` |
| B11 | JD inflation | `FR-102` | existing `check_jd_inflation` |
| B12 | Grammar no-rewrite | `FR-140` | `grammarCheck.ts` |
| B13 | Draft linter | `FR-144` | `draft_linter.py` |
| B14 | Golden regression | — | partial via smoke extension |
| B15 | Verb allowlist | `FR-146` | `_verb_allowed()` |
| B16 | Single metric cap | `FR-105` | existing `recruiter_qa` |
| B17 | Optional LLM profile | `FR-134` | `JD_PROFILE_MODE=llm` |
| B18 | PDF export gate | `FR-139` | `jobs.ts` PUT guard |
| B19 | Editor facts panel | `FR-140` | `DocumentEditor.tsx` |
| B20 | Compiler-only path | `FR-089` | `drafting_engine` → `draft_compiler` |

## Environment defaults

| Variable | Default |
|----------|---------|
| `DRAFT_MODE` | `compose` |
| `LOCAL_ONLY_MODE` | `1` |
| `JD_PROFILE_MODE` | `deterministic` |
| `COVER_HOOK_MODE` | `template` |
| `RESEARCH_MODE` | `local` |
| `FIT_EVAL_TOP_N` | unset (all jobs) |
| `LOCAL_LINT` | `1` (set `0` to skip phi3.5 lint) |

## Files changed

| File | Change |
|------|--------|
| `scripts/pipeline_env.py` | New — central env helpers |
| `scripts/pre_score_jobs.py` | New — BM25+embed pre-score |
| `scripts/build_claim_embeddings.py` | New — ops entrypoint |
| `scripts/draft_linter.py` | New — JSON lint only |
| `scripts/batch_pipeline.py` | Defaults, pre-score, schema fit, schema migration |
| `scripts/scout_local.ts` | Seniority gate, ATS watchlist |
| `scripts/jd_tailoring.py`, `local_draft_stages.py`, `claim_composer.py` | Compose hardening |
| `scripts/llm_stages.py`, `utils.py` | Stage models, strict local-only |
| `scripts/draft_compiler.py`, `verification_chain.py` | Manifest, anti-claim |
| `scripts/drafting_engine.py`, `research-engine.py` | Research mode |
| `server/db.ts`, `server/shared.ts`, `server/routes/jobs.ts` | FTS5, env, PDF gate |
| `src/lib/grammarCheck.ts`, `src/components/DocumentEditor.tsx` | Lint + facts panel |
| `.github/workflows/smoke.yml` | CI |
| `config/ats_watchlist.example.json` | ATS template |

## Acceptance criteria

See `02-requirements-registry.md` — `AC-139` through `AC-158` for `FR-131`–`FR-150`.

## Verification results (2026-05-28)

- `python scripts/smoke_draft_compiler.py` — **passed**
- `python scripts/test_smoke_regression.py` — **8/8 passed**
- Manual: restart server to apply `jobs_fts` migration; run `python scripts/build_claim_embeddings.py` once

## Layer 1 (business rules)

- `.agent/rules/pipeline_env.md` — always-on agent rule for env defaults and drafting invariants

## Related specs

- `FEAT-001-scouting.md`, `FEAT-004-drafting.md`, `FEAT-012-hybrid-intelligence.md`
- `IMP-CR-021-local-funnel-compose-hardening.md`
- `JobAgent_Architecture_and_PRD.md` §4.4
