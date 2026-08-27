# IMP-CR-102: Stage 1 first-draft quality contract

## Requirements

`FR-265`, `AC-332`–`AC-338`

## Implemented

- [x] Block pair repetition and insufficient JD specificity in Stage 1.
- [x] Run deterministic resume/cover quality checks before Stage 1 exits.
- [x] Add packet provenance contract v2 and exact unit-level verification.
- [x] Hard-block narrow defensive disclaimer patterns.
- [x] Add corrected Sony/Solace retrieval examples and global category ranking.
- [x] Fix confirmed `LW-021`, `LW-028`, and `LW-032` false positives.
- [x] Convert the linter suite to dependency-free `unittest` discovery.
- [x] Validate preserved first/final Sony and Solace documents.

## Verification

- `.venv\Scripts\python.exe -m unittest scripts.test_author_from_packet scripts.test_build_authoring_packet -v`
  passed 128 tests.
- `.venv\Scripts\python.exe -m unittest scripts.test_submission_linter -v`
  passed 63 tests.

## Remaining role of Stage 2

Stage 2 remains responsible for independent truth, ATS, hiring-manager,
mechanical, and policy review. CR-102 moves only deterministic recurring defects
earlier.
