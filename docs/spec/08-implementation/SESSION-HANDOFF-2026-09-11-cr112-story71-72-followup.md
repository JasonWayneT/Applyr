# CR-112 Stories 7.1/7.2 follow-up — 2026-09-11

Local commit on `cr112-story71-72` only. No push. `b7f7197` stays isolated until this follow-up is the accepted parent.

## Durable state

- Reconciliation of 2026-09-11 remains accepted. Stories 3.1 / 3.5 / 3.6 were not reimplemented.
- Parent of this follow-up is `b7f7197` (`706504a` is the Epic 3 parent). Do not checkout `cr112-story71-72` in the sequence worktree.

## Reviews

| Pass | Agent | Verdict |
|------|--------|---------|
| Independent review of `b7f7197` | prior session | FAIL |
| Independent review of earlier uncommitted follow-up | prior session `f44fe072` | FAIL |
| Post-correction review of current follow-up | [Review](97887893-381a-47fa-b521-e5c1d5d2af78) first pass | FAIL (`expected_item_ids` / `created_at` optional) |
| Post-correction re-review after envelope fix | [Review](97887893-381a-47fa-b521-e5c1d5d2af78) | **PASS** |

Should-fix left open: type-check `created_at` as a non-empty string. Audit-only, not identity.

## Evidence

- Focused tests: `python -m unittest scripts.test_cr112_story71` → 41 OK
- Cascade tests: `python -m unittest scripts.test_stage0_evidence_cascade` → OK
- Review Center pause/resume: `test_workflow_pauses_then_resumes_after_hard_gate_answer` → OK (`pause_kind=review_center`)
- Synthetic no-cost exercise (temp `example-co`, no provider adapters, `APPLYR_STAGE0_REVIEW_DB` temp sqlite):
  - Pause: `WAITING_FOR_INPUT` / `cost_authorization` / `model_call_occurred=false` / `cost_applicable=false` / no `api_cents` / adapter calls `0`
  - `--status` copy includes folder path, `stage0_cascade_import.json`, and `--resume`
  - `check_workflow_complete` is false
  - Existing Resume.md / CoverLetter.md did not enter Stage 1 paste
  - Bound template import: Stage 0 `COMPLETE`, still `0` adapter calls, live import renamed to `stage0_cascade_import.consumed.json`
  - Normal Stage 1 paste entry was attempted via `run_until_waiting_for_llm`; this worktree then raised `FileNotFoundError` for missing `data/authoring_rule_digest.md` (worktree isolation, not a cost-pause defect)

Refused classification is recorded as no call occurred. Cost is not applicable. Unknown price was not converted to zero.

## Consumed-import rule

Successful Stage 0 that used a live `stage0_cascade_import.json` renames it to `stage0_cascade_import.consumed.json`. Only the live name is loaded. Replay after JD/requirement change fails closed. Changing the consumed bytes stale-locks Stage 0.

## Limitations

- This worktree has no `data/workExperience.md` and no `data/authoring_rule_digest.md`. Do not treat a paste-prompt FileNotFoundError here as a 7.x product failure.
- Default checkpoint DB remains `data/jobagent.sqlite` in production runs. Tests and the synthetic exercise used `APPLYR_STAGE0_REVIEW_DB`.
- No live provider calls. No push. No live `data/submissions` edits. No Stage 3 / jobs-table writes.

## Next action

Stories 7.1/7.2 are **integration-ready** for the cost-pause, bound manual import, and paid-ledger overlay contract. Keep `b7f7197` plus this follow-up off `main` until Jason asks to merge onto `cr112-selection-closed-world-design`. Do not upload.
