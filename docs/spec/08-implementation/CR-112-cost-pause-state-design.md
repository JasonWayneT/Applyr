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

---

## Addendum 2026-09-15 — the concrete `certify_zero_charge` path (Story 7.3, FR-326/AC-424)

This addendum defines the operator free-tier attestation as the concrete
form of Decision 6's `certify_zero_charge` next path. Implementation
packet: `.metis/plans/cr112-cost-operator-free-tier-authorization-packet.md`.
Nothing in Decisions 1-7 changes; this adds one new way for
`adapter_can_assert_zero_charge()` to return True for `groq`/`gemini`.

**Shape.** A typed attestation record per provider in the `llm_settings`
profile blob (same blob as `costClasses` / `paidProviderAllowlist` /
`paidBudgetCents`), under a new top-level key `freeTierAssertions`:

```json
"freeTierAssertions": {
  "groq": {
    "provider": "groq",
    "acknowledged": true,
    "statement": "<canonical per-provider sentence, character-for-character>",
    "asserted_at": "2026-09-15T00:00:00Z"
  }
}
```

The canonical statements are constants in `scripts/cost_eligibility.py`
(`OPERATOR_FREE_TIER_STATEMENT`). `OPERATOR_FREE_TIER_CERTIFIABLE` is
exactly `{groq, gemini}`; `local` is already `offline`, and `claude` /
`perplexity` are permanently excluded (no operator-certifiable free tier;
naming them would weaken the paid guard). `OPERATOR_FREE_TIER_ASSERTION_MAX_AGE_DAYS`
is 30.

**Validation (all fail-closed, no exception escapes).** In order:
`local` → True; process-local test stub → True; provider not certifiable
→ False (`free_only_assertion_not_certifiable`); attestation missing →
False (`free_only_assertion_missing`); record not an object, `provider`
mismatch, `acknowledged is not True`, `statement` differing by any
character, or `asserted_at` missing/unparseable/naive → False
(`free_only_assertion_invalid`); older than 30 days → False
(`free_only_assertion_expired`); otherwise True. `classify_provider`
still requires both halves: `costClasses[provider]="free_only"` **and** a
valid attestation. Declaration without attestation stays `unknown`;
attestation without declaration changes nothing.

**Write path.** Only `POST /api/profile/llm_settings`
(`server/routes/profile.ts`), surfaced via the Settings → AI Usage card.
Never a direct SQLite edit, file edit, or environment variable.
`freeTierAssertions` contains no secrets; the CR-104 masking lists are
unchanged and the route preserves the key verbatim.

**Telemetry (additions only).** A successful operator-asserted free call
records `cost_class="free_only"`, `cost_known=true`,
`cost_confidence="zero"`, `api_cents=0`, plus
`zero_charge_basis="operator_assertion"` and `assertion_asserted_at`
echoed, so an attested zero stays auditable as attested, not measured.
Refusals use the new `reason` values above in the existing receipt shape;
`api_cents` stays omitted. `subscription_minutes` remains separate and is
never summed with `api_cents` (AC-414).

**Why not a checkbox.** Decision 6 already rejects "Settings checkbox is
not enough." A bare boolean or provider-name list is the backdoor that
`test_settings_zero_charge_list_is_not_a_backdoor` guards. The typed
record with an exact canonical statement, strict boolean identity,
timestamp, and expiry is the smallest shape meaningfully stronger than a
checkbox that stays offline; no billing-API verification is possible
without a network call, which this mechanism never makes.

**Residual risk (accepted).** The attestation cannot prove billing is
disabled; it records an accountable human certification, re-certified
every 30 days, with `zero_charge_basis="operator_assertion"` keeping
attested zeros distinguishable from measured zeros.

---

## Status-copy refinement (2026-09-16)

Implements `FR-316` / `AC-413`.

Both user-visible `WAITING_FOR_INPUT` paths must branch on
`result.pause_kind` read from `stage_receipts/stage0.json`:

1. `contracts.waiting_for_input_message`, which feeds `--status`.
2. The post-run console copy in `run_submission.py`.

For `pause_kind=cost_authorization`, both paths state that no model API
call occurred, Stage 0 is not complete, and the same run can resume by
importing validated cascade JSON, certifying a zero-charge provider, or
authorizing a paid provider with an allowlist, budget, and known estimate.
Both paths explicitly prohibit pasting `authoring_prompt.md`.

For an old receipt with no `pause_kind`, both paths preserve the existing
Review Center confirmation copy. This is a compatibility fallback, not a
new inference from other receipt fields.

The offline provider golden harness must make the same authorization
contract explicit. Its mocked Groq and Gemini adapters use the test-only
zero-charge assertion and `free_only` class. A provider name alone never
authorizes even a deterministic fixture call.
