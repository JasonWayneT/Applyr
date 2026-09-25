# CR-132 — QA lead

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-392, AC-502

## Product outcome

A sentence that calls him a QA lead is a hard block at Stage 1 and Stage 2. The block holds when the sentence cites a different fact, and when it cites nothing. A test-suite sentence that does not use that title does not block.

## Why

The before-fix Candor resume says he served as first-pass QA lead and cites ACC-204. The cite-matched check only fires for ACC-209.

## Out of scope

- "Hundreds of client databases"
- Changing the evaluator
