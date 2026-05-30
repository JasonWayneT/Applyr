# CR-ARCH-000 — Spawn Inventory and Gate Matrix (Structural)

**Status:** Implemented (documentation)  
**Date:** 2026-05-30  
**Implements:** Architecture refactor Phase 0 (PR-00)

## Purpose

Document all server-side subprocess invocations and scout vs batch gate scope before structural refactors (ProcessRunner, route splits).

## Spawn inventory

| ID | File | Command | Args (pattern) | cwd | Mode | Abort | Env |
|----|------|---------|----------------|-----|------|-------|-----|
| S01 | `server/index.ts` | `python` | `path.join(SCRIPTS_DIR, 'auto_prune_db.py')` | default | detached interval | no | `buildSpawnEnv()` |
| S02 | `server/scout.ts` | `buildTsxSpawn` → `node` + tsx | `scripts/scout_local.ts` | `PROJECT_ROOT` | stream lines | no | `buildSpawnEnv(extraEnv)` |
| S03 | `server/scout.ts` | tsx | `scripts/archive/backfill_urls.ts` | `PROJECT_ROOT` | stream | no | same |
| S04 | `server/scout.ts` | tsx | `scripts/requeue_needs_retry.ts` | `PROJECT_ROOT` | stream | no | same |
| S05 | `server/scout.ts` | tsx | `scripts/scrape_new_jobs.ts` | `PROJECT_ROOT` | stream | no | same |
| S06 | `server/scout.ts` | `python` | `scripts/batch_pipeline.py --mode batch` | `PROJECT_ROOT` | stream (`[BATCH_PROGRESS]`) | no | same |
| S07 | `server/routes/pipeline.ts` | `python` | `path.join(SCRIPTS_DIR, 'batch_pipeline.py')` + single args | `PROJECT_ROOT` | SSE stream | **yes** `attachClientAbort` | `buildSpawnEnv()` |
| S08 | `server/routes/jobs/files.ts`, `crud.ts` | `runPythonScript` | skill_gap, verify, guard, compile, ai_rewrite, rerank | `PROJECT_ROOT` | buffered | no* | via ProcessRunner |
| S09 | `server/routes/jobs/draft.ts` | `spawnPython` | `batch_pipeline.py` draft (manual) | `PROJECT_ROOT` | stream stdout | no | via ProcessRunner |
| S10 | `server/routes/profile.ts` | `spawn` | `scripts/generate_experience_summary.py` | `PROJECT_ROOT` | detached | no | `buildSpawnEnv()` |
| S11 | `server/middleware.ts` | `spawn` | via `runPythonScript(args)` | `PROJECT_ROOT` | buffered | optional | `buildSpawnEnv()` |

\*Evaluate path uses abort; editor save chain does not attach client abort to intermediate scripts.

## Allowlisted spawn paths (PR-01 `check_spawn_paths.py`)

- `path.join(SCRIPTS_DIR, ...)`
- `runPythonScript(`
- `scripts/batch_pipeline.py` (scout S06, cwd `PROJECT_ROOT`)
- `scripts/generate_experience_summary.py` (profile S10, cwd `PROJECT_ROOT`) — standardized in PR-04

## Gate matrix (scout vs batch)

| Gate | Scout (`scout_local.ts`) | Batch (`passes_jd_keyword_gate`) | Notes |
|------|--------------------------|----------------------------------|-------|
| Title blocklist | Yes (title string) | Yes (`passes_title_gate` / JD title line) | Shared semantics via `seniority_gate.py` in batch |
| Years cap | Subset at ingest if JD snippet | Yes (`check_years_gate`) | Scout may lack full JD |
| Industry blocklist | Yes (`industry_gate` TS mirror) | Yes (`check_industry_gate` / header) | REG-08/10; batch scans header 600 chars |
| Must-have keywords | No | Yes (`passes_keyword_gate`) | Batch only |
| Anchor gate | No | Yes (env `ANCHOR_GATE_ENABLED`) | Off by default |
| Onsite classifier | No | Yes (batch zero-shot) | Batch only |

## Non-goals (this CR)

- ProcessRunner implementation (CR-ARCH-004)
- Changing lock semantics
- Auth on `/api/system-status`

## Verification

- Spawn table reviewed against `server/` grep
- REG-15 added in PR-01 for title gate parity
