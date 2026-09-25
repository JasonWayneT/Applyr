# CR-131 — Portability inversion

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-391, AC-501

## Product outcome

A sentence that says profile portability was chosen over custom tagging is a hard block at Stage 1 and Stage 2. The block holds when the sentence cites a different fact, and when it cites nothing. The sentence that says custom tagging took priority does not block.

## Why

ACC-155 says custom tagging took priority over making profiles portable. The before-fix Obie letter reversed that and cited ACC-115, so the cite-matched check did not fire.

## Out of scope

- QA lead cited to a different fact
- "Hundreds of client databases"
- Changing the evaluator
