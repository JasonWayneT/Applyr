# CR-147 — An overlong letter loses an uncited sentence

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-410, AC-521

## Product outcome

A cover letter over 2800 characters loses an uncited sentence until it fits one page. The only past-employer sentence stays. The character limit stays 2800.

## Why

Holdout 9 failed Stage 1 because the letter was 2976 characters. Raising the limit would loosen the page check.

## Out of scope

- Raising the 2800 character limit
- Changing the evaluator
- A holdout run
