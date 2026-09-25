# CR-148 — A thin letter gains a cited sentence

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-411, AC-522

## Product outcome

A cover letter under 220 words gains a cited resume sentence until it reaches that floor. It does not pass 450 words or 2800 characters. A letter already in range stays as written.

## Why

Holdout 10 parked at the hiring-manager pass because the letter body was 172 words. The floor stays 220.

## Out of scope

- Lowering the 220 word floor
- Adding a sentence that has no cite
- Changing the evaluator
- A holdout run
