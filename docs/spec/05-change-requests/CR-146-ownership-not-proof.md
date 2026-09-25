# CR-146 — Ownership alone is not unused evidence

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-409, AC-520

## Product outcome

A required line that shares only the word ownership with a mapped claim does not fail Stage 1 when that claim is unused. A line that shares a real term, such as a product name, still requires the cite.

## Why

Holdout 8 failed Stage 1 because a leadership line and a scope excerpt shared only that word.

## Out of scope

- Attaching the unused id to a sentence that does not say it
- Changing the evaluator
- A holdout run
