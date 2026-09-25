# CR-145 — A cited contradiction is removed

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-408, AC-519

## Product outcome

A resume bullet that cites a fact and says something that fact does not say is removed before Stage 1 fails. A neighboring bullet stays. The check still fires on the original wording.

## Why

Holdout 7 failed Stage 1 on that check. The remover never loaded the cite file, so it could not see the line.

## Out of scope

- Changing the evaluator
- Accepting the finding without an edit
- A holdout run
