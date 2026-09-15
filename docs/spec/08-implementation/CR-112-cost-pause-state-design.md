---
status: design
created: 2026-09-11
from: Cursor (Grok 4.6)
depends_on: CR-112-reconciliation-2026-09-11.md
implements_on: cr112-story71-72 (do not merge to sequence or integration yet)
independent_review: FAIL (1fa3fdac-5976-4535-9430-6a7ee0fe886c)
follow_up_review: PASS (97887893-381a-47fa-b521-e5c1d5d2af78)
---

# CR-112 cost-pause state transition and Stage 0 continuation

Design only until this file is the contract for the isolated 7.x follow-up
commit. Do not land this on `cr112-selection-closed-world-design` until
7.x is independently re-reviewed.

Independent review of `b7f7197`: **FAIL**. Eligibility unit tests pass.
Adapters are mocked. The pause is not a workflow outcome.

## Decision 1 — Workflow status

**Reuse `WAITING_FOR_INPUT`.** Do not add a sibling status.

Why existing semantics are correct:

- Stage 0 is not complete.
- `--resume` already re-enters `run_stage0` when `stage0` is not
  `COMPLETE`/`SKIPPED`, then returns early if status is still
  `WAITING_FOR_INPUT` (`runner.py` `run_until_waiting_for_llm`).
- The orchestrator is already the sole writer of that receipt today
  (`Stage0NeedsInput` → `commit_stage`).

Why `WAITING_FOR_LLM` is wrong: that status means Stage 0 finished and
`authoring_prompt.md` is ready. Cost ineligibility happens during Stage 0
evidence classification, before a packet exists.

Why `FAILED` is wrong: cost pause is expected and resumable. The Stage 0
checkpoint must not be marked `FAILED` on this path
(`build_stage0_fit_gate.py` currently does that in the cascade
`except Exception`).

Why a new top-level status is unnecessary: the confusion is the Review
Center console copy, not the state machine. Fix the copy with
`result.pause_kind`.

## Decision 2 — Typed exception

Add `Stage0CostAuthorizationNeeded` next to `Stage0NeedsInput` in
`build_stage0_fit_gate.py`.

`CostPauseError` stays a helper exception from `cost_eligibility.py`.
Helpers still do not write `workflow_state.json` or `stage_receipts/`.

`build_stage0_fit_gate` catches `CostPauseError` from
`classify_requirements_batch` and raises `Stage0CostAuthorizationNeeded`
with the payload below. It must not wrap it as `Stage0ExtractError`.

`run_stage0` catches `Stage0CostAuthorizationNeeded` the same way it
catches `Stage0NeedsInput`: `commit_stage` with
`workflow_status="WAITING_FOR_INPUT"`, `active_stage="stage0"`.

## Decision 3 — Receipt payload

`stage_receipts/stage0.json` `result`:

```
pause_kind: cost_authorization
stage: stage0
attempted_operation: evidence_classification
authorization_mode: unknown | free_only | paid_with_budget | offline | manual_paste
ineligible_providers: [{provider, cost_class, reason}]
model_call_occurred: false
cost_known: false
api_cents: omitted
cost_confidence: unknown
next_paths: [import_cascade_json, certify_zero_charge, paid_allowlist_budget]
resume_command: python scripts/run_submission.py <folder> --resume
```

Existing Review Center receipts gain `pause_kind: review_center` so
status text can branch. Old receipts without `pause_kind` keep today's
Review Center copy (backward compatible).

## Decision 4 — Status reporting

`run_submission.py` and `contracts.py` must read `pause_kind` from the
stage0 receipt when status is `WAITING_FOR_INPUT`.

Cost-authorization copy, plain language:

- Processing paused because no eligible Stage 0 classifier was
  authorized.
- No model API call occurred.
- No API cost was incurred. Unknown cost is not recorded as zero.
- The same run resumes with `--resume` after one next path below.
- Free/manual path: drop a validated cascade JSON at
  `stage0_cascade_import.json`, or a provider whose adapter can assert
  zero charge for this account/call.
- Paid path: allowlist the provider, set a positive budget and a known
  estimate, then `--resume`.
- Do not paste `authoring_prompt.md`. Stage 0 is not finished.

`--status` must be able to print this from receipts alone. Terminal
stderr is not the source of truth.

## Decision 5 — Cascade must not change authorization mode

On `CostPauseError`, stop. Do not continue to the next provider. Do not
fire `provider_event_callback("call")` before an adapter is actually
entered. Do not treat `CostPauseError` as a transport fallback on the
retry path.

Unproven `free_only` is `unknown`. It must not unlock a later paid
provider in the same cascade loop.

`authorize_provider_chain` remains the single filter inside `call_llm`.
Cascade should not second-guess it by walking ineligible names.

## Decision 6 — Stage 0 continuation (daily use)

Default Groq and Gemini stay `unknown` until an adapter can assert the
configured call cannot incur a charge. That is fail-closed, not a
product bug. The product bug is the missing resume path.

**Chosen path: manual cascade import, same schema as provider output.**

1. File: `<submission>/stage0_cascade_import.json`
2. Shape: `{"results":[...]}` validated by existing
   `validate_batch_response` against the current `BatchItem` list.
3. On `--resume`, if that file exists and validates, Stage 0 uses it and
   does not call a provider.
4. If it is missing or invalid, re-pause at the same `WAITING_FOR_INPUT`
   receipt. Do not fail closed into `Stage0ExtractError`.
5. Invalid import is not a license to skip HARD/NONE. Do not fall back
   to NLP-only classification.

Other paths, explicit and separate:

- `local` / `LOCAL_ONLY_MODE`: already `offline`. Unchanged.
- Adapter-asserted `free_only`: unchanged. Settings checkbox is not
  enough.
- `paid_with_budget`: allowlist + remaining budget + known estimate.
  Cumulative remainder must persist across `call_llm` invocations in
  the same Stage 0 run (checkpoint run metadata or an orchestrator-owned
  sidecar, not a rebuilt settings ceiling).

Rejected as default: deterministic extraction-only for uncached
required/preferred lines. That silently weakens Stage 0.

Stage 1 paste does not complete Stage 0.

## Decision 7 — Receipt confidence (7.2 follow-up in the same isolated commit)

| Situation | `cost_known` | `cost_confidence` | `api_cents` |
|---|---|---|---|
| No call, unknown/ineligible | false | unknown | omitted |
| Offline or asserted free call | true | zero | 0 |
| Paid call with table estimate | true | estimated | estimate |
| Provider-confirmed usage | true | confirmed | actual |

Do not stamp an estimate as `known` without distinguishing estimated vs
confirmed. Do not convert missing estimate to 0
(`estimated_cents or 0` in `utils.py` is forbidden).

Confirmed is out of scope until a provider returns trusted usage. Paid
success is `estimated`.

## Tests required before claiming the follow-up is done

Negative controls that fail if the guard is removed:

- Default groq+gemini unknown: adapters not called; workflow is
  `WAITING_FOR_INPUT` / `pause_kind=cost_authorization`; `--status`
  mentions no API call and does not mention authoring_prompt.
- `--resume` with no import and no certified provider: still paused.
- `--resume` with a `stage0_cascade_import.json` that passes
  `validate_batch_response`: Stage 0 can complete without adapters.
- Invalid import: still paused, not `Stage0ExtractError`, not NLP skip.
- Declared `free_only` without assertion plus paid next: paid adapter
  not called; mode stays unknown / free_only, never paid.
- Two paid calls against a budget that only covers one: second adapter
  not called.
- Checkpoint run status is not `FAILED` on a cost pause.

No live API. No `data/submissions` production edit. No push.
