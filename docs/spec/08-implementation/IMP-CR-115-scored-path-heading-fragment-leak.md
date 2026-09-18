# IMP-CR-115 Scored-path heading and fragment leak

Status: in progress. Stories in `docs/spec/05-change-requests/CR-115-scored-path-heading-fragment-leak.md` stay unchecked until independent QA.

## What landed

- `_is_unscored_chrome_item` / `_divert_scored_chrome` in `scripts/build_stage0_fit_gate.py` move heading, job-board metadata, and truncated-fragment chrome out of required/preferred before evidence scoring. Implements FR-330 / AC-428.
- Sitting-1 fixtures: Accuity "Education and Credentials" vs degree pair, 1uphealth "Mid and Senior level", 1uphealth truncated fragment. Leftover junk list is not reclassified.
- Tests: `scripts/test_build_stage0_fit_gate.py::TestCR115ScoredChrome`.
- Production switch stays off. No gold labels manufactured.

## Not done

Independent QA has not marked the CR-115 stories. Replay is still not a promotion gate.
