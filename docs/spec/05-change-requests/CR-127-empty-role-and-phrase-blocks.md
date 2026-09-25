---
status: implemented
date: 2026-09-23
related: CR-126, FR-386
---

# CR-127: Empty roles and the low false-positive phrase blocks

## Decision sought

Stop Stage 2 from marking COMPLETE when a resume role has no bullets, when the letter never names a past employer, or when the draft uses a banned data-model phrase or drops "estimated" on two figures work experience already hedges.

## Problem

`nisum_2` reached COMPLETE with three role headings and zero bullets. The author output and the pre-repair resume already had no bullets. A separate set of finished letters used "data model", or stated the $1M to $3M figure and the drafting-time line without "estimated". Those fail from the words on the page. The larger set of false sentences, the ones that cite a real ID and contradict that entry, is out of scope here. See `docs/spec/08-implementation/FINDINGS-2026-09-24-entailment-gap.md`.

## Product outcome

Stage 2 HM collects four new hard blocks from `lint_folder`. Stage 1 verify fails on that same list, so repair can edit the draft before the hiring-manager pass. A BLOCK finding still cannot be closed with ACCEPTED_AS_CORRECT. The draft has to change, or someone records HUMAN_ACCEPTED_RISK, which is the existing hard-block rule.

An experience role with at least one bullet passes. A letter that names Cision, Sterkly, or Zero To Sixty in a prose paragraph passes. "reading the schema" passes. "estimated $1M to $3M" passes. "$8,500 annually" stays on the existing LR-042 check and is not reimplemented.

## Out of scope

The verify step that deletes an uncited line and then passes. Scorecard rebind. Stage 0 fit. The earlier-role bullet floor. The auto-written hiring-manager disposition. A model judge over cited entries. A partner-team hard block. The Visible codename.

## Requirements and acceptance

| Requirement | Acceptance |
| --- | --- |
| `FR-386` Stage 2 blocks an empty role, a letter with no past employer, a data-model phrase, and a dropped estimate hedge | `AC-496` The empty three-role fixture fails. A letter with no employer fails. "data model" fails. "$1M and $3M" without "estimated" fails. The hedged forms, a schema sentence, and a letter that says "At Cision" pass. A copy of the Medrisk before-fix letter fails the data-model check. |

## Evaluation

Unit tests in `scripts/test_submission_linter.py`. The before-fix assertion copies files from `data/review_evidence/2026-09-23-before-fix/` into a temp directory. It does not read `data/submissions/`.
