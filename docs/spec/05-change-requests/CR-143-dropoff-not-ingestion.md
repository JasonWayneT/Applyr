# CR-143 — Drop-off story is not an ingestion pipeline

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-406, AC-517

## Product outcome

A 40% contact-data drop-off sentence that calls the story an ingestion pipeline is rewritten to ETL path before the hiring-manager pass. The 40% outcome stays. A sentence that is not that story keeps the words ingestion pipeline. The same block now fails Stage 1, so a repair can run before the hiring-manager pass.

## Why

Holdout 5 parked on that block. It was only raised at the hiring-manager pass, which cannot rewrite the draft.

## Out of scope

- Changing the evaluator
- Adding the misnamed story to an allowlist
- A holdout run
