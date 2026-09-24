# CR-141 — Hedged figure and uncited employer sentence

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-403, AC-514, FR-404, AC-515

## Product outcome

A hedged `$100,000` is rewritten to `$100K` before the metric check. A sentence with no hedge word is left as written. When the only past-employer sentence in a letter is uncited, Stage 1 adds one cited resume sentence that names that employer and then removes the uncited sentence.

## Why

Holdout 3 parked one folder because both documents said roughly `$100,000`. That precise form is not the career figure. Another folder failed Stage 1 because the only employer sentence had no cite, so deleting it would leave the letter with no past employer, and the repair returned invalid provenance.

## Out of scope

- Adding `$100,000` to the approved-metric list
- Changing the evaluator
- A holdout run
