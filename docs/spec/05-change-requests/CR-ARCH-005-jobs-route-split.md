# CR-ARCH-005 — Jobs Route Split

**Status:** Implemented  
**Date:** 2026-05-30

## Summary

Split monolithic `server/routes/jobs.ts` into:

| Module | Routes |
|--------|--------|
| `jobs/crud.ts` | list, create, reconcile, stats, **rerank**, status, patch |
| `jobs/files.ts` | files CRUD, skill-gap, ai-rewrite, download-all |
| `jobs/draft.ts` | `POST /api/jobs/:id/draft` |
| `jobs/shared.ts` | `jobBaseDir` helper |
| `jobs/index.ts` | mounts sub-routers + `requireApiToken` |

## Route-order fix

`POST /api/jobs/rerank` registered in `crud.ts` before any `/:id` routes so Express does not treat `rerank` as a job id.

## Entry point

`server/index.ts` imports `./routes/jobs/index.js`.
