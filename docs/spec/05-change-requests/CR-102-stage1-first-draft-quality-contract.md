# CR-102: Stage 1 first-draft quality contract

## Problem

The Sony and Solace end-to-end system tests showed that Stage 1 could pass drafts
that Stage 2 predictably returned for repeated resume/letter phrasing, weak JD
specificity, unsupported or defensive qualification, long bullets, and a missing
professional close. Known linter false positives also made real warnings harder
to trust.

## Requirement

`FR-265`: Stage 1 verification must fail closed on deterministic first-draft
quality defects while Stage 2 remains an independent safety audit.

## Acceptance criteria

- `AC-332`: substantive `LW-009-PAIR` findings block Stage 1.
- `AC-333`: `LW-026` JD-specificity findings block Stage 1.
- `AC-334`: packets rebuilt with provenance contract v2 require every resume
  bullet and factual cover-letter sentence to cite packet claim IDs.
- `AC-335`: Stage 1 runs resume and cover-letter quality checks, including
  bullet length and professional closing transition.
- `AC-336`: defensive ownership disclaimers hard-block under `LR-032`.
- `AC-337`: corrected Sony/Solace examples are eligible for packet retrieval,
  and global relevance can place later categories inside the example budget.
- `AC-338`: `LW-021`, `LW-028`, and `LW-032` do not report the confirmed
  operations/`decisions`, ACC-303 separate-subject, contact-header, or ambiguous
  common-name false positives.

## Safety and compatibility

- Closed-world evidence rules are unchanged.
- Provenance v2 applies only to newly rebuilt packets. Legacy packets skip this
  one gate until rebuilt.
- Stage 1 does not auto-disposition Stage 2 findings.
- No completed Sony or Solace workflow artifact is rewritten for validation.

## Validation

- 128 authoring/packet unit tests passed.
- 63 linter regression tests passed.
- Preserved Sony and Solace first drafts now fail at least one new deterministic
  gate, while both final documents pass quality, pair-repetition, specificity,
  and hard-block checks.
