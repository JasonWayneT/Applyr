# CR-156 — A copied opening sentence is dropped

**Status:** Implemented
**Date:** 2026-09-24
**Requirements:** FR-419, AC-530

## Product outcome

When the opening has another sentence, a sentence that repeats six or more words from the posting is dropped. A one-sentence hook is left alone. The warning still fires on the original wording.

## Why

Holdout 18 parked at the hiring-manager pass. The opening repeated seven words from the posting. A second opening sentence did not.

## Out of scope

- Accepting the warning without an edit
- Cutting a hook that has only that one sentence
- A holdout run
