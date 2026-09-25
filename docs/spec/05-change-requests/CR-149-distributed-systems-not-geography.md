# CR-149 — Distributed data systems are not team geography

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-412, AC-523

## Product outcome

A resume line about distributed data systems does not fail the geography check. A line that says a team was distributed across offices still fails when the job description never asked for that.

## Why

Holdout 11 failed Stage 1 because a technical line used the word distributed. The check was written for team locations.

## Out of scope

- Dropping the technical line
- Changing the evaluator
- A holdout run
