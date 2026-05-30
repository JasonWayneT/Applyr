# CR-ARCH-004 — ProcessRunner (Server Pipeline Transport)

**Status:** Implemented  
**Date:** 2026-05-30  
**Requirements:** NFR-MAINT-001 (spawn consolidation), mitigates R05

## Summary

Centralized Python subprocess spawning in `server/pipeline/processRunner.ts`:

| API | Use case |
|-----|----------|
| `buildSpawnEnv` | Sanitized env (secrets stripped, `buildPythonEnv` merged) |
| `pythonScriptPath` | Resolve script under `SCRIPTS_DIR` |
| `runBuffered` | One-shot scripts (middleware `runPythonScript`, auto-prune) |
| `runStreamLines` | Scout sync (npx/node or python line streaming) |
| `runDetached` | Fire-and-forget (experience summary regeneration) |
| `spawnPython` | Interactive SSE evaluate + manual draft (`attachClientAbort`) |

## Migrations

- `server/middleware.ts` — `runPythonScript` → `runBuffered`
- `server/scout.ts` — `spawnProcessAsync` → `runStreamLines`
- `server/index.ts` — auto-prune → `runBuffered`
- `server/routes/profile.ts` — summary regen → `runDetached`
- `server/routes/pipeline.ts` — evaluate SSE → `spawnPython`
- `server/routes/jobs.ts` — manual draft → `spawnPython`

## CI guard

`scripts/check_spawn_paths.py` allowlists `spawnPython(` in routes; raw `spawn('python'` only permitted in `processRunner.ts`.

## Verification

- `python scripts/check_spawn_paths.py`
- `npm run build`
- Manual (Windows): evaluate SSE + manual draft once per release until Vitest transport tests land (PR-06)

## Non-goals

- Route split (`jobs.ts`) — CR-ARCH-005
- Frontend `apiClient` / `sse.ts` — CR-ARCH-006
