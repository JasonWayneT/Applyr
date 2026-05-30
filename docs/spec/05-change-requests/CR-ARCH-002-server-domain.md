# CR-ARCH-002 — Server Domain Module

**Status:** Implemented  
**Date:** 2026-05-30

## Summary

- `server/domain/jobStatus.ts` — `ACTIVE_STATUSES`, `submissionBaseDir`
- `server/domain/jobSearchPrefs.ts` — `materializeJobSearchPrefs` (ADR-005)
- `server/domain/paths.ts` — `DATE_POSTED_TO_DAYS`, `CANDIDATE_PREFS_PATH`
- Deduped constants in `jobs.ts` and `submissionFolders.ts`
- `shared.ts` re-exports domain modules for backward compatibility

## Non-goals

- ProcessRunner (CR-ARCH-004)
- Route split (CR-ARCH-005)
