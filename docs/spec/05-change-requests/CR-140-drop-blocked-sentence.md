# CR-140 — Drop a blocked sentence

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-402, AC-512

## Product outcome

Stage 1 removes a cited experience bullet or cover-letter sentence that is itself a hard block, then re-checks the draft. The sentence stays when removing it would create a new hard block. A line whose only blocked-tool hit is the word epic stays. No missing hedge is invented.

## Why

Holdout 1 left four Stage 1 failures. Two of them were a data-model phrase and an unverified tool. Repair saw the same findings again and stopped. The block stays a block. The line that already fails is removed so the rest of the draft can continue.

## Out of scope

- Changing the evaluator
- Adding a tool or a metric to an allowlist
- Inserting a 5 percent hedge that is not already in the sentence
- A holdout run
