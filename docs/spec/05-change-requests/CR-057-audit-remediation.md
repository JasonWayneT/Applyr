# CR-057: JobAgent Deep Audit Remediation

## Metadata
- **Epic**: Reliability & Data Integrity
- **Status**: Implemented
- **Date**: 2026-07-06

## Problem
An independent adversarial audit of the JobAgent pipeline identified three primary vulnerabilities regarding data integrity and silent failure masking:
1. **Missing Transaction Boundaries**: `jobRepository.ts` wrote to `jobs` and `jobs_fts` in separate, non-transactional statements. A crash between the two would leave the FTS index permanently out of sync.
2. **Type Safety Gaps in Connectors**: Scraper connectors (`theirstack`, etc.) casted `res.json()` directly into expected interfaces without runtime validation. Malformed ATS payloads (e.g. `data: "string"` instead of an array) would cause downstream `TypeError` crashes.
3. **Silent Failures**: `openpostings` swallowed background sync fetch errors, and `scoutOrchestrator.ts` silently swallowed `UNIQUE` constraint errors from concurrent inserts.

## Decision
- Wrap all mutation endpoints in `jobRepository.ts` (`insertJob`, `patchJob`, `deleteJobRecord`) inside `db.transaction()` to enforce atomicity.
- Implement explicit error logging in `openpostings` and `scoutOrchestrator.ts`.
- Introduce runtime array validation in `theirstack` before `.slice()` processing to safely return `[]` on malformed API payloads. 

## Acceptance Criteria
- FTS index stays fully synced even under adversarial crash scenarios (prevented by SQLite WAL transactions).
- Theirstack connector gracefully ignores malformed JSON payloads.
- Scout failures and ATS sync errors are visible in logs/stdout.

## Out of Scope
- A global rewrite of all 11 connectors to use strict Zod validation (deferred for future architectural cleanup).
- Resolving NPM dependency vulnerabilities (requires `dompurify` breaking changes, deferred for human review).
