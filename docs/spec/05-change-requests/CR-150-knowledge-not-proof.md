# CR-150 — Knowledge alone is not unused evidence

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-413, AC-524

## Product outcome

A required line that shares only the word knowledge with a mapped claim does not fail Stage 1 when that claim is unused. A line that shares a real term still requires the cite.

## Why

Holdout 12 failed Stage 1 because a software-analysis line and a scaling excerpt shared only that word.

## Out of scope

- Attaching the unused id to a sentence that does not say it
- Changing the evaluator
- A holdout run
