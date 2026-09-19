# CR-119 supervised Agy shakedown - 2026-09-18

## Scope and status

This is the first real CSV queue batch and the live Task 3 test from
`PLAN-2026-09-18-stage0-new-flow-ready.md`. Agy is the only intended LLM path for
Stages 0 through 3. Every worker invocation in the clean run set
`APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` for that process. No Groq or Gemini API
fallback was used after the reset.

Pack 1 contained three jobs: `rentana`, `casper_studios`, and `raya`. The pack did
not reach Stage 2:

| Slug | Current workflow result | Queue result |
|---|---|---|
| `rentana` | Stage 0 Tier 2 pass; Stage 1 parked after three usable drafts failed validation | `paused` |
| `casper_studios` | Stage 0 parked because Agy again omitted evidence item IDs after Review Center answers | `paused` |
| `raya` | Stage 0 hard-gap skip after five Review Center answers | `done` |

Current queue totals are 31 `queued`, 2 `paused`, and 1 `done`. There are no
finalize-ready jobs. Stage 2 and Stage 3 were not run. `--finalize` was not run.

The live leftover classifier remained unchanged:

`77b317467a6018a17e47b28fe3bda59a6901015945fc75d0f770dd04bc775913`

## Summary

- Ingest matched the expected result exactly: 4 files, 61 rows, 34 queued, 0
  reused, 26 skip-ledger matches, and 1 quarantined row.
- CSV archive movement and the quarantine database row were verified. The live
  Review Center panel was not verified because no Review Center server was
  listening during ingest.
- Stage 0 failed closed when Agy returned incomplete evidence. It did not
  silently skip those jobs.
- The queue heartbeat extended a lease during a seven-minute Stage 0 job.
- `WAITING_FOR_INPUT` now maps to queue `paused`, preventing the earlier
  `in_progress` lease-expiry stall.
- Agy extraction caching worked. Retry extraction calls logged `cache_hit` with
  zero calls and zero subscription minutes.
- Pack 1 still cannot proceed reliably. Stage 0 evidence completion is
  nondeterministic, and the current prompt-only Stage 1 path produced zero valid
  drafts from three usable attempts.

## Issues

### 1. Agy evidence batches still omit item IDs

**Tag:** bug  
**Severity:** blocker  
**Frequency:** 3 observed pauses in the clean run across 2 of 3 jobs; also
reproduced in the archived pre-reset attempt.

What happened:

- `rentana` paused after 158.070 seconds with
  `subscription_review:harness omitted item_ids`.
- `casper_studios` paused after 324.070 seconds for the same reason.
- After its Review Center answers were completed, `casper_studios` retried and
  hit the same omitted-ID condition again after 61.830 seconds.
- Three-item evidence chunking and one missing-ID retry did not make the path
  reliable. A later nondeterministic retry happened to complete `rentana`.

Evidence:

- Command: `python scripts/run_queue_worker.py --worker chatgpt-1 --size 3 --once`
  with `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1`.
- Files: `data/pending_review/casper_studios/stage_receipts/stage0.json` and
  `data/pending_review/casper_studios/observability/run_events.jsonl`.
- The failed path reported a specific Agy evidence review pause and no API cost.

Suggested fix:

1. Validate each Agy chunk against the exact requested ID set before caching.
2. Retry missing IDs in a fresh Agy session with a smaller batch.
3. Include requested, returned, missing, duplicate, and malformed ID counts in
   non-sensitive telemetry.
4. Park only after the bounded retry policy is exhausted.

### 2. Stage 1 prompt-only authoring cannot produce a valid draft reliably

**Tag:** process gap  
**Severity:** blocker  
**Frequency:** 0 of 3 usable `rentana` drafts passed; 1 additional Agy call
returned an empty response.

What happened:

- The first Agy call returned `SUCCESS` with an empty response after a denied
  `read_file` attempt.
- Usable draft 1 failed on education truth, cover-letter closing structure,
  repeated phrasing, ground-truth attention flags, and missing required terms.
- Usable draft 2 failed on cover-letter length, repeated phrasing,
  ground-truth attention flags, and missing required terms.
- Usable draft 3 failed on two resume truth blocks, repeated phrasing, two
  uncited factual cover-letter sentences, ground-truth attention flags, and
  missing required terms.
- Re-sampling from the unchanged prompt consumed quota without converging.

Evidence:

- Raw streams and preserved failed artifacts:
  `data/eval/cr119_supervised/rentana_stage1_01/` through
  `data/eval/cr119_supervised/rentana_stage1_04/`.
- Validation events:
  `data/submissions/rentana/observability/run_events.jsonl` contains three
  `stage1.validate` / `verify_failed` pairs.
- Commands: quota-tracked Agy fresh sessions followed by
  `python scripts/run_queue_worker.py --worker chatgpt-1 --size 1 --once`.

Suggested fix:

Add the bounded Stage 1 repair path now assigned to Cursor. Each repair should
use a fresh session with only `authoring_prompt.md`, the failed draft artifacts,
and deterministic findings. Allow at most two repairs, then park the job with a
machine-readable failure summary. Do not re-sample a fresh draft from the same
unchanged prompt.

### 3. Paused rows promote without evidence that their blocker changed

**Tag:** bug  
**Severity:** high  
**Frequency:** both paused Agy-evidence jobs were promoted when only Raya's
Review Center answers had changed.

What happened:

- Starting the worker after Raya was answered also promoted `rentana` and
  `casper_studios`.
- `rentana` repeated several minutes of Agy evidence work without new input.
- `_promotable_paused_slugs` promotes all eligible paused rows before the claim
  query applies its size limit. A `--size 1` validation run also changed
  `casper_studios` from `paused` to `queued` without claiming it.

Evidence:

- `scripts/pipeline_queue.py`, `_paused_should_promote`, lines 517-543.
- `scripts/pipeline_queue.py`, `_promotable_paused_slugs` and `claim_pack`,
  immediately below that function.
- Fencing-token counts after pack 1: `rentana=5`, `casper_studios=3`, `raya=2`.

Suggested fix:

Use blocker-specific readiness checks. Review Center pauses should require a
new completed answer after `paused_at`; Agy incomplete-output pauses should
require a new import, cache version, or implementation version. Promote no more
paused rows than the requested claim size, inside the claim transaction.

### 4. Agy can report `SUCCESS` with no author output

**Tag:** bug  
**Severity:** high  
**Frequency:** 1 of 4 Stage 1 calls.

What happened:

The first clean author call reported `SUCCESS`, consumed quota, and returned an
empty response. Stderr stated that a required tool permission was denied.

Evidence:

- `data/eval/cr119_supervised/rentana_stage1_01/agy_stream.jsonl`.
- Result: 41,889 input tokens, 1,856 output tokens, empty final response.

Suggested fix:

Treat empty final response or missing required artifacts as failure regardless
of Agy's top-level status. For the author path, launch in a clean sandbox that
contains only `authoring_prompt.md` and verify the three required artifacts
before recording success.

### 5. Stage 1 quota/token accounting has an extreme outlier

**Tag:** bug  
**Severity:** high  
**Frequency:** 1 of 4 Stage 1 calls.

What happened:

One author call reported 419,638 input tokens and 4,154,618 cache-read tokens for
an approximately 11,459-token prompt. It took 385.741 seconds and reduced the
five-hour allowance by 3 percentage points.

Evidence:

- `data/eval/cr119_supervised/rentana_stage1_03_stream.jsonl`.
- `python scripts/agy_quota_tracker.py status`.

Suggested fix:

Log turn count and tool-call count with quota telemetry. Fail or warn when
reported input is an implausible multiple of the prompt estimate. The repair
launcher should prevent repeated file reads and unbounded internal loops.

### 6. Stage 1 validation failure is not represented in workflow status

**Tag:** bug  
**Severity:** medium  
**Frequency:** 3 of 3 usable draft validations.

What happened:

After `author_from_packet.run_verify_only` failed, `workflow_state.json` remained
`WAITING_FOR_LLM`. The queue correctly paused because that status is mapped, but
the mirror does not distinguish no draft from a rejected draft.

Evidence:

- `data/submissions/rentana/workflow_state.json`.
- `data/submissions/rentana/observability/run_events.jsonl` records three
  `verify_failed` events while queue `last_workflow_status` remains
  `WAITING_FOR_LLM`.

Suggested fix:

Persist a distinct Stage 1 repair-needed state or structured validation-failure
reason and map it to queue `paused`.

### 7. Quarantine panel visibility was not exercised live

**Tag:** process gap  
**Severity:** low  
**Frequency:** one run.

The quarantine row existed in `csv_quarantine`, and the server route and panel
component were present, but no Review Center server was listening. The live UI
check remains unrun.

Suggested fix:

Include starting Review Center and visually confirming the quarantine row in the
next preflight checklist.

## Improvements

Ranked by expected payoff:

1. Add a single supervised command that records stage, model, effort, quota
   before/after, wall time, cache status, and artifact validity for every Agy
   call.
2. Add blocker versioning to paused queue rows so a worker can tell whether a
   relevant answer, import, repair, or code version changed.
3. Add a bounded Stage 1 repair command that consumes deterministic findings
   and preserves each attempt.
4. Show per-job attempt count and last blocker reason in the pipeline panel.
5. Show Stage 0 cache-hit versus fresh-call status in receipts and the panel.
6. Add a Review Center launch-and-visibility step to the supervised-run script.

## Stats

### Ingest

| Metric | Result |
|---|---:|
| Files seen | 4 |
| Files archived | 4 |
| Total CSV rows | 61 |
| Queued | 34 |
| Reused | 0 |
| Skipped by Stage 0 ledger | 26 |
| Quarantined rows | 1 |
| Quarantine error | `EMPTY_COMPANY` |
| Duplicate file hash | 0 |
| Unstable files | 0 |

Skip-ledger reason groups: 9 cooldown rows, 4 years-over-ceiling rows, 4 hard
requirement/exclusion rows, 3 blocked associate-title rows, 3 fit-score rows, 2
travel-ceiling rows, and 1 solo-PM row. The 26 rows represent 24 distinct
postings because two postings appeared twice.

### Stage 0

| Slug | Attempt | Cache | Outcome | Wall time |
|---|---:|---|---|---:|
| `rentana` | 1 | fresh extraction/evidence | Agy incomplete evidence pause | 158.070s |
| `rentana` | 2 | extraction cache hit | Tier 2 pass | 334.697s |
| `casper_studios` | 1 | fresh extraction/evidence | Agy incomplete evidence pause | 324.070s |
| `casper_studios` | 2 | extraction cache hit | Review Center pause, 2 questions | 125.588s |
| `casper_studios` | 3 | extraction cache hit | Agy incomplete evidence pause | 61.830s |
| `raya` | 1 | fresh extraction/evidence | Review Center pause, 5 questions | 421.996s |
| `raya` | 2 | extraction cache hit | hard-gap skip | 19.001s |

Totals:

| Metric | Result |
|---|---:|
| Passes | 1 |
| Skips | 1 |
| Review Center pause events | 2 |
| Agy incomplete-evidence pause events | 3 |
| Stage 0 failures that silently skipped | 0 |
| Fresh extraction calls | 3 |
| Extraction cache hits | 4 |

Stage 0 per-call Gemini allowance was **not captured**. The Stage 0 adapter
reported `api_cents=None`; this is not equivalent to zero subscription usage.
Adding quota capture per Stage 0 evidence call is required for the next pack.

### Stage 1 author quota

Prompt estimate for every call: approximately 11,459 tokens.

| Run | Result | Wall | Agy input | Agy output | Thinking | Cache read | Weekly before/after | 5h before/after |
|---|---|---:|---:|---:|---:|---:|---|---|
| `stage1-01` | `SUCCESS`, empty response | 19.266s | 41,889 | 1,856 | 1,715 | 36,949 | 69% / 68% | 85% / 85% |
| `stage1-02` | usable draft, validation failed | 60.812s | 38,961 | 21,514 | 18,983 | 0 | 68% / 68% | 85% / 84% |
| `stage1-03` | usable draft, validation failed | 392.390s | 419,638 | 31,509 | 21,258 | 4,154,618 | 68% / 68% | 84% / 81% |
| `stage1-04` | usable draft, validation failed | 89.641s | 75,522 | 29,280 | 24,211 | 155,842 | 68% / 68% | 81% / 80% |

Stage 1 repair was not available during pack 1. The future policy is a maximum
of two fresh repair sessions using the prompt, failed drafts, and findings.

### Stage 1 validation

| Metric | Result |
|---|---:|
| Usable author drafts | 3 |
| First-pass validation passes | 0 |
| First-pass validation failures | 3 |
| Empty `SUCCESS` responses | 1 |
| Jobs parked after author attempts | 1 |

No document text is reproduced here. Failure categories are listed in Issue 2.

### Stage 2

Stage 2 did not run. Truth, ATS, HM, Mech, Policy, WARN/BLOCK findings,
dispositions, rubric scores, PDF page counts, and Stage 2 quota are all
**not measured**.

### Queue

| Metric | Result |
|---|---:|
| Pack 1 jobs | 3 |
| Claims: `rentana` | 5 |
| Claims: `casper_studios` | 3 |
| Claims: `raya` | 2 |
| Current paused | 2 |
| Current done | 1 |
| Current queued outside pack | 31 |
| Lease expiries in clean run | 0 |
| Heartbeat lease extensions observed | 1 |
| Stuck `in_progress` rows after mapping fix | 0 |
| Fence rejections | 0 |
| Duplicate queue slugs | 0 |
| Duplicate Raya skip rows | 0 |

Wall time from queued to current terminal/parked state:

| Slug | Queued at | Current state at | Elapsed |
|---|---|---|---:|
| `rentana` | 00:06:15Z | 00:58:12Z | 51m 57s |
| `casper_studios` | 00:06:15Z | 00:59:59Z | 53m 44s |
| `raya` | 00:06:15Z | 00:39:34Z | 33m 19s |

The queue timestamps do not include time spent in isolated author sessions after
the last queue update. Author call wall times are reported separately above.

### Workarounds

- Used `--size 1` for later worker runs to avoid pulling a fourth job into pack 1.
- Ran Stage 1 authors one at a time in isolated Agy sandboxes containing only
  `authoring_prompt.md`.
- Preserved every failed draft and raw Agy stream under
  `data/eval/cr119_supervised/`.
- Removed failed drafts from the live submission folder to prevent automatic
  queue validation retries.
- Kept `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` scoped to each worker process.

## Waiting to finalize

None. No pack 1 job reached Stage 2 completion.

## Next-run gates

Do not resume the worker until Jason says go after FIXQUEUE items 1-4 are marked
landed. Before each later pack, re-read
`docs/spec/08-implementation/FIXQUEUE-2026-09-18-agy-shakedown.md` and record the
first pack exercising any worker-path fix.

After the repair path lands and Jason says go, run one fresh Rentana author pass
with the strongest available Agy model or effort. Record quota before and after,
then compare its validation result and quota use with the Flash Medium calls
before attributing the Stage 1 failures to model capability.
