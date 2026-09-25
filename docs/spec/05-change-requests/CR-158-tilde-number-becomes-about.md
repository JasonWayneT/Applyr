# CR-158 — A tilde in front of a number becomes about

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-421, AC-532

## Product outcome

A tilde in front of a number is rewritten to about. The digits stay. The warning still fires on the tilde.

## Why

Holdout 20 parked because a resume wrote ~200 and ~25,000.

## Out of scope

- Accepting the warning without an edit
- Changing the digits
- A holdout run
