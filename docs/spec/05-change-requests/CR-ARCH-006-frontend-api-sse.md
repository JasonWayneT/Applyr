# CR-ARCH-006 — Frontend API Client + SSE Parser

**Status:** Implemented  
**Date:** 2026-05-30

## Summary

- `src/lib/sse.ts` — `parseSseChunk` for evaluate SSE streams
- `src/lib/apiClient.ts` — `apiFetch` / `apiJson` with optional `VITE_APPLYR_API_TOKEN` → `X-Applyr-Token`
- `src/hooks/usePipeline.ts` — uses shared SSE parser + `apiFetch`
- `src/lib/sse.test.ts` — Vitest unit tests
- `vitest.config.ts`, `npm test`, CI step in `smoke.yml`

## Non-goals

- Migrate all `fetch(api(...))` call sites (incremental)
- `src/features/` folder layout
