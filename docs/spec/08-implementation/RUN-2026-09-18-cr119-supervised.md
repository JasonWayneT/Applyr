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

Those were the pack 1 results, not the current totals. After pack 5, the queue
had 38 `queued`, 4 `paused` (including one `ready_to_finalize`), and 1 `done`.
Jason subsequently authorized Rentana finalize. Its Stage 3 is now COMPLETE
and its queue row is `done`; current totals are 38 `queued`, 3 `paused`, and
2 `done`. No other job was finalized.

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

Pack 1: none. After pack 5, **Rentana** waited here with Stage 2 `COMPLETE`,
Stage 3 `READY`, clean Policy integrity, and both PDFs at 1 page. Jason
approved finalize in a subsequent turn. **Current waiting list: none.**
Rentana is now Stage 3 `COMPLETE`, queue `done`, with a Rentana / Product
Manager jobs row in `Backlog`. `check_workflow_complete` returned YES.

## Pack 2 start (post-FIXQUEUE 1-8)

- Start commit: `a241e06b5771865fb7f0b543608ba28f4d316069`.
- FIXQUEUE read before pack: `Items 1-4 landed: YES`; `Runtime hold: NO`.
- This is the first pack exercising the landed queue promotion, deterministic
  Stage 1 fixed-part injection, repair loop, forwarded findings, Stage 0
  screening/partial-result changes, and quota-tracker agent-step logging.
- Cursor also requeued nine earlier false skips under item 6. Pack 1's
  31-queued snapshot is therefore historical, not the current queue baseline.
- Rentana's packet and prompt were regenerated after the rule digest change
  by Cursor's orchestrator path (FIXQUEUE item 4b; file timestamps 19:04).
- At pack start, Rentana was paused at `WAITING_FOR_LLM`, Casper Studios at
  `WAITING_FOR_INPUT`, Raya done, and the next unpaused job was Binance.
- No worker or finalize command had run in this pack at this point.

### Pack 2 checkpoint

Two `--size 1 --once` worker claims ran on the start commit above, with
`APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` set per process. No finalize ran.

| Slug | Stage 0 | Source | Queue after claim | Elapsed claim-to-update |
|---|---|---|---|---:|
| `binance` | `WAITING_FOR_INPUT` | Fresh extraction (one Agy call logged) | `paused` | 1m 04s |
| `healthstream` | PASS | Fresh extraction (Agy calls logged) | `paused`, `WAITING_FOR_LLM` | 6m 39s |

The lease remained future-dated while HealthStream was `in_progress`;
no expiry or fence rejection was observed. Both rows released to `paused`.
Review Center answer status for Binance was not checked. Stage 0 Agy quota
cannot be attributed precisely per call from the current telemetry. The
account-level snapshot changed from 69% weekly / 81% five-hour after the
Opus author calls to 66% / 77% after both worker runs; concurrent Agy use
cannot be ruled out. Do not treat this as per-job consumption.

| Rentana author call | Model | Result | Wall time | Input | Cache read | Internal steps | Weekly before/after | Five-hour before/after |
|---|---|---|---:|---:|---:|---:|---|---|
| `opus-01` | Claude Opus 4.6 Thinking | Nominal `SUCCESS`, file read denied; no artifacts | ~10s | 21,419 | 0 | 1 | 69% / 69% | 81% / 81% |
| `opus-02` | Claude Opus 4.6 Thinking | Three artifacts produced | ~2m | 48,902 | 237,366 | 7 | 69% / 69% | 81% / 81% |

`opus-02` was a fresh sandboxed session whose only input file was the
regenerated `authoring_prompt.md`. The three generated artifacts were placed
in Rentana's submission folder. Author validation has **not run** because
the worker did not promote Rentana. The stronger-model comparison is thus
limited to artifact production and quota, not quality or first-pass pass rate.

**New P0 bug (queue):** `check_stage1_ready('data/submissions/rentana')`
returned `(True, [])`, but the next `--size 1` worker claimed Binance.
`scripts/pipeline_queue.py` computes paused promotion budget as
`max(0, size - queued_and_expired_count)`; with 39+ queued rows, that is zero.
How often: 1/1 ready paused job tested; the formula makes it deterministic
until the backlog falls below pack size. Fix: reserve bounded claim capacity
for eligible paused jobs and test with a queued backlog. Added to FIXQUEUE
"Incoming from testing" for Cursor. This blocks the requested Stage 1
repair and Stage 2 shakedown, not the Stage 0 queue.

At checkpoint: Rentana, Casper Studios, Binance, and HealthStream paused;
Raya done; 38 queued. No job is waiting to finalize. No Stage 1 repair,
Stage 2, or Stage 3 check ran in this pack. The item 2 fixed-part injection,
item 3 forwarded notes/story shape/repair behavior, item 5 Casper omitted-ID
retry, and FAILED no-restart behavior remain unverified live.

## Pack 3 start (post-FIXQUEUE 9a-9c)

- Start commit: `adbd8a2628619d08c87cfc4592b95c7d4d9c7ce2`.
- FIXQUEUE read before pack: `Runtime hold: NO`; items 9a-9c marked landed.
- This is the first live pack for paused-first claiming (9a), Stage 0 Agy
  quota receipts (9b), and nonempty Stage 1 artifact readiness (9c).
- Start queue: 38 queued, 4 paused, 1 done. Rentana's Opus-authored files are
  ready for worker validation. HealthStream has no Stage 1 author files yet.
- Claude Opus was a one-time comparison. All further author/repair sessions
  in this run use Agy Gemini.

### Pack 3 checkpoint

One `--size 1 --once` worker claim picked **Rentana** before the 38 queued
jobs, confirming item 9a live. Stage 1 first-pass validation failed. The
worker exited but left Rentana `in_progress` with workflow status
`IN_PROGRESS` and a 20-minute lease. No manual queue release or direct
`run_submission.py` invocation was made. HealthStream remains paused at
`WAITING_FOR_LLM`; no author files were generated for it in this pack.

**First-pass model comparison, same job (different prompt revisions):**

| Author | Usable first pass | First-pass blocking findings | Other findings | Repair path |
|---|---|---|---|---|
| Gemini Flash Medium, pack 1 | 3 usable samples, 0 pass | Sample 1: education/structure and repetition; sample 2: length and repetition; sample 3: two resume truth blocks, repetition, two uncited factual sentences | Coverage and missing-term attention on all three | No repair implementation then; full resamples, not comparable repair rounds |
| Claude Opus 4.6 Thinking, pack 3 | Yes, 0 pass | `LR-013`, `LR-015`, repeated phrase, one uncited factual sentence | Coverage and term attention; two evidence notes forwarded | Four Gemini repair rounds; no pass |

The Opus prompt was regenerated after FIXQUEUE item 4b and fixed-part
injection was newly active. This is a workflow/model comparison, **not** a
controlled model-only A/B test. One prior Opus invocation returned nominal
`SUCCESS` after read permission denial and produced no artifacts.

| Repair | Model | Result after verify | Input | Cache read | Internal steps | Tracker five-hour drop |
|---|---|---|---:|---:|---:|---:|
| 1 | Gemini 3.8 Flash Medium | Cleared `LR-015` and uncited sentence; `LR-013` and repetition remain | 91,012 | 253,235 | 7 | 2pp |
| 2 | Gemini 3.8 Flash Medium | Cleared one forwarded-evidence warning; same two blocks | 116,557 | 367,558 | 10 | 2pp |
| 3 | Gemini 3.8 Flash Medium | Cleared repetition; only `LR-013` blocks | 147,864 | 277,768 | 9 | 1pp |
| 4 | Gemini 3.8 Flash High | Same `LR-013`; `NO_PROGRESS` | 573,283 | 4,159,585 | 46 | 6pp |

Each repair used a fresh Agy session with only the generated
`stage1_repair_prompt.md`. The prompt included the original authoring prompt,
snapshotted failed drafts, and findings, not separate WE/claims/AGENTS/context
files. The four verification outputs are under
`data/eval/cr119_supervised/rentana_pack3_repair0{1-4}_verify.txt`; raw Agy
streams remain in isolated temporary session directories. The five-hour
window reset before repair 1, so its percentage must not be compared directly
to the earlier Opus window.

**Live checks:** The verifier reported `PASS [apply_resume_header]` and patched
the fixed header, education, role headings/locations, greeting, and sign-off.
`stage1_forwarded_findings.json` was written for unused high-priority
evidence, which remained a WARN rather than a block. The repair-state file
records `attempts: 4`, `last_outcome: no_progress_blocking`; truth/format
block `LR-013` remains blocking. Cover-letter 1-2-story quality was not
independently scored, and Stage 2 did not run.

**Additional runtime findings:**

- The worker printed stale Stage 1 receipt hash mismatches for the packet,
  prompt, and prompt metadata rebuilt under item 4b. Validation still ran;
  whether those stale receipts would block later Stage 2 is untested.
- On validation failure, workflow state `IN_PROGRESS` is unmapped by the
  worker, leaving the row `in_progress` until lease expiry. This reproduces
  the existing FIXQUEUE Stage 1 failure-state issue on item 9a code.
- Gemini Flash High spent 46 internal steps and 6 five-hour quota points
  without changing the sole remaining block. No further repair was started.

**Stop condition:** Stage 1 unable to pass after repairs, with quota burning
without progress. Queue snapshot: 38 queued, 3 paused, 1 in_progress, 1 done.
No job reached Stage 2 or waits to finalize. Casper's 3/3 omitted-ID retry,
Stage 2 findings, rubric scores, page counts, and finalize remain untested.
During this pack HEAD advanced to `65cab4a6ac013e316fbc16b9b0418c26a85a206c`
for the CR-120 ID/document reservation; the worker claim ran from the pack
start commit and that intervening commit did not change its worker path.

## Next-run gates

Before each later pack, re-read
`docs/spec/08-implementation/FIXQUEUE-2026-09-18-agy-shakedown.md` and record the
first pack exercising any worker-path fix. Item 9a's paused-first claim worked
in pack 3. Before another worker pack, resolve or explicitly account for
Rentana's unmapped `IN_PROGRESS` lease and the `NO_PROGRESS` Stage 1 truth
block. Keep the Opus artifacts and all four Gemini repair artifacts as
comparison evidence; do not resample Rentana from scratch. HealthStream is
still awaiting its first Gemini author pass. Jason receives a checkpoint
before the next pack.

## Pack 4 start (post-FIXQUEUE 9b-9e)

- Start commit: `63d7100095686c450136aad344d93ad22f5f3f77`.
- FIXQUEUE read before pack: `Runtime hold: NO`; items 9b-9e and 9g marked
  landed. This is the first worker pack testing deterministic Stage 1
  pre-repair, failed-validation pause/release, compact prompts, and refreshed
  WAITING receipt hashes.
- Start queue: 38 queued, 3 paused, 1 expired `in_progress` (Rentana), 1 done.
  Rentana's prior lease expired at 04:47:08Z; the check at 05:22Z found no
  other leased or in-progress row.
- Rentana's `authoring_packet.json` had already been rebuilt by Cursor at
  22:03 local and contains the new seven-year hard constraint. The older
  `authoring_prompt.md` did not contain that fact. No manual packet edit or
  direct `run_submission.py` call was made.
- No Opus author or repair call will run. Any new Agy author/repair call in
  this pack uses Gemini. Prompt size (KB) and quota-point delta will be
  recorded per repair round; single-finding target is under 10KB.

### Pack 4 checkpoint

**Rentana:** The worker reclaimed its expired lease. Its rebuilt packet
already contained the seven-year fact; the first Stage 1 check reported
`LR-013`, `stage1_prerepair.py` changed the years figure, and the next check
passed. `stage1_repair_state.json` records `auto_fixes: LR-013` and
`last_outcome: auto_fixed`. **Agy calls: 0.** This confirms item 9c live.

Stage 2 first found 2 Truth BLOCKs (unsupported company assertions in cover
letter provenance), 10 Truth WARNs, 4 ATS WARNs, and 4 HM WARNs. I removed
the unsupported assertions, tightened the letter to two connected stories,
updated provenance, and resolved a wrong-company false positive in the resume.
One ATS term with real evidence was added to the competencies row. Mech's
first PDF compile found a 2-page resume and 1-page letter. Trimming dense
bullets took the resume from 502 to 456 words; a direct preview compile and
the worker's later compile both confirmed a 1-page resume. No BLOCK was
accepted as a risk.

| Final Stage 2 phase | Current findings | Dispositions on current findings | Result |
|---|---:|---|---|
| Truth | 8 WARN, 0 BLOCK | 8 `ACCEPTED_AS_CORRECT` (7 unique IDs; see collision issue) | COMPLETE |
| ATS | 3 WARN, 0 BLOCK | 2 `FALSE_POSITIVE`, 1 `ACCEPTED_AS_CORRECT` | COMPLETE |
| HM | 2 WARN, 0 BLOCK | 1 `FALSE_POSITIVE`, 1 hash-bound `ACCEPTED_AS_CORRECT` critical read | COMPLETE |
| Mech | 0 current findings | 2 earlier BLOCKs cleared by edit; resume/letter 1 page each | COMPLETE |
| Policy | 0 reported findings | None | COMPLETE, integrity CLEAN |

The disposition file also retains 8 historical `RESOLVED_EDIT` entries for
findings cleared by content changes. Current rubric score: resume **78/100**,
cover letter **82/100**, with a hash-bound scorecard row and structured HM
review checked by their local contracts. The worker reported Stage 2 COMPLETE
and Stage 3 READY at 05:37:19Z (5h 31m 04s elapsed from queue ingest, including
supervision pauses). **Queue bug:** the row remained `in_progress`,
`last_workflow_status=IN_PROGRESS`, with a lease to 05:57:14Z instead of
finalize-ready. Logged in FIXQUEUE; no finalize run.

**HealthStream:** Its Stage 0 had passed in pack 2. The old packet and prompt
did not contain the new years fact; the generated packet and prompt were
refreshed before authoring, and the refreshed prompt did. Agy author attempt
1 returned `503 UNAVAILABLE` before generation (0 model steps, 0 measured
quota-point drop). Attempt 2, Gemini 3.8 Flash Medium, produced all three
artifacts: 88,687 input tokens, 224,771 cache-read tokens, 6 internal steps,
and tracker drops of 1 weekly / 2 five-hour points. Its first Stage 1 check
failed on `LR-016`, missing supported ATS terms, and one uncited factual
sentence; 12 coverage and 7 term-gap attention flags were also emitted. The
worker correctly set workflow `FAILED` and queue `paused` with no lease,
confirming item 9e live.

The repair builder wrote a **7.83 KiB (8,022-byte)** prompt for those
findings, below the 10 KiB target, and requeued HealthStream. Repair round 1
used Gemini 3.8 Flash Medium in a fresh session with that prompt only. After
177 step updates and more than five minutes it had written no draft files;
the call was interrupted under the quota-burning stop rule. Its truncated
stream prevented a final Agy usage result. Account snapshots moved from
67% weekly / 89% five-hour before to 65% / 84% afterward, an **unattributed
2pp / 5pp delta**, not a reliable per-call charge. The raw stream is saved
under `data/eval/cr119_supervised/`. No repair validation ran. The builder
had already left HealthStream `queued` with the old failed files and
`last_workflow_status=FAILED`, so another worker run could retry pointlessly.

Pack 4 end queue: 1 done, 2 paused, 1 `in_progress` (Rentana), 39 queued
(including HealthStream). No lease expiry, fence rejection, or duplicate
folder was observed in this pack. Stage 0 fresh/cache-hit timing did not run
in this pack. Stage 2 had no Agy call. Casper's live 3/3 omitted-ID retry and
Review Center quarantine-panel visibility remain untested.

## Pack 5 start (post-FIXQUEUE 9f-9i)

- Start commit: `fa5d247fd662082e6a4201398c1b9d538717b004`.
- FIXQUEUE read before pack: `Runtime hold: NO`; items 9f-9i marked landed.
  This is the first live pass testing `ready_to_finalize`, capped one-shot
  repair, valid-output requeue, and JD-conditional geography guidance.
- Planned sequence: Rentana one-sentence closing repair and worker
  re-verification; HealthStream capped Stage 1 repair; only after both clear,
  a new three-job confidence pack. No finalize.

### Pack 5 checkpoint

**Rentana:** A fresh, isolated Gemini 3.8 Flash Medium one-shot call received
only the exact closing finding and returned one replacement sentence. The Agy
result reports 4.67 seconds, one turn, 19,024 input, 702 output, and 678
thinking tokens. The closing and matching provenance were changed; no other
cover-letter sentence changed. The quota tracker could not open a new run
because HealthStream repair 1 lacks an after-result. A separate allowance
snapshot was 66% weekly / 100% five-hour before and after this short call;
rounding and concurrent account use prevent an exact point charge.

The first size-1 worker invocation unexpectedly claimed `binance`, because
its answered `WAITING_FOR_INPUT` pause was promotable and ready-paused rows
take precedence over the expired Rentana lease. Binance's extraction was a
cache hit, then five *fresh* Stage 0 evidence calls took 24.203, 24.954,
25.000, 30.657, and 51.187 seconds. The per-call five-hour snapshots were
100→99, 99→99, 99→98, 98→98, and 99→98%; weekly snapshots fluctuated
65–66%. They are rounded account snapshots, not additive per-call charges.
Binance passed Stage 0 and paused `WAITING_FOR_LLM`; no author call was made.
This detour consumed roughly 156 seconds of fresh evidence-call wall time.

The next worker claim took Rentana. Editing the closing made Stage 1 and
Stage 2 receipts stale as intended. New `LW-039` validation exposed another
geography mention in a resume bullet; the closing also required an exact
provenance citation. The resume bullet was changed only to remove location
names, and its provenance plus the closing provenance were updated. A
debug-only `author_from_packet.py --verify-only` passed all Stage 1 checks;
its exit remained nonzero because Stage 2 receipts were stale. Rentana was
explicitly requeued through `requeue_paused_for_repair` after the files
passed, not pre-claimed. The worker then completed Stage 1, Truth and ATS,
and paused at HM for a new hash-bound critical read. The changed passages
were reread, and the current hashes were recorded in the HM disposition,
scorecard, and manifest. The next worker pass completed HM, Mech, and Policy.

| Rentana re-verify | Result |
|---|---|
| Stage 1 | PASS; `LW-039` PASS; no Agy Stage 1 repair call |
| Truth / ATS / HM findings | 8 / 3 / 2 WARN, 0 BLOCK; current dispositions resolved |
| Mech / Policy | COMPLETE / COMPLETE; integrity CLEAN |
| Rubric | Resume 78, cover letter 82; reread against current hashes |
| PDFs | Resume 1 page, cover letter 1 page; mechanically_verified=true |
| Queue | `paused`, reason `ready_to_finalize`, no lease, last workflow `READY_TO_FINALIZE` |

Pack 5 made five one-job worker claims: Binance once, HealthStream once,
Rentana three times. All five released their leases to paused states; no
fence rejection was observed. Rentana's first claim reclaimed one previously
expired `in_progress` lease. Fencing tokens ended at Rentana 16,
HealthStream 3, Binance 2. Rentana's final ready timestamp was 19:33:35Z,
19h 27m 20s after its 00:06:15Z queue time, including long supervised holds.

**HealthStream:** An earlier queued FAILED row was claimed on one incidental
size-1 worker pass while Rentana was paused FAILED. It correctly returned to
paused FAILED with no lease; no Agy call ran in that pass. The repair builder
then refreshed its prompt to **11,886 bytes (11.61 KiB)**, above the <10 KiB
single-finding target because multiple blocking findings plus new geography
findings were present. `run_stage1_repair.py` used Gemini 3.8 Flash Medium in
a fresh sandbox with only that prompt. The new cap stopped it at **21 events,
21.718 seconds**, outcome `repair_timeout / event_count`, with no valid
artifacts. No Stage 1 re-validation followed. The row remained `paused` /
`FAILED`, no lease, so valid-output-only requeue worked.

Quota snapshot immediately before the capped call was 65% weekly / 99%
five-hour; after it was 66% / 98%. The weekly increase and account-wide
rounding make a precise call charge unknowable; observed five-hour change
was 1 percentage point. The prior interrupted repair still blocks
`agy_quota_tracker.py before`, so there is no trusted tracker record or Agy
final usage for this attempt. This is not a zero-cost call.

**Stop condition:** HealthStream has no repaired output after two repair
attempts (one interrupted tool loop, one capped timeout), while allowance
fell and no Stage 1 finding cleared. The requested three-job confidence pack
was not started because both jobs did not clear. Pack 5 end queue: 38 queued,
4 paused, 1 done. No finalize, commit, push, or direct queued-slug
`run_submission.py` invocation. Review Center quarantine-panel visibility,
Casper's post-fix omitted-ID retry, and the new-job confidence pack remain
untested.

### Jason-authorized finalize after pack 5

`check_finalize_ready('data/submissions/rentana')` returned `(True, [])`.
Jason then explicitly authorized finalize. Command:
`python scripts/run_submission.py data/submissions/rentana --finalize
--finalize-company Rentana --finalize-title 'Product Manager'`.
It completed Stage 3 with CLEAN integrity and workflow `COMPLETE`. A read-only
DB check found one Rentana / Product Manager `Backlog` jobs row and queue
`done`, no lease. `stage_receipts/stage3.json` says COMPLETE/CLEAN, and
`check_workflow_complete` returned `(True, [])`. No other job was finalized.

## Pack 6 start (HealthStream repair, Binance author)

- Start commit: `fa5d247fd662082e6a4201398c1b9d538717b004`.
- FIXQUEUE read before worker use: `Runtime hold: NO`. No new worker-path
  commit since pack 5. `APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` remains scoped
  to each worker process. No finalize in this pack.
- HealthStream repeated the 11,886-byte (11.61 KiB) prompt with a bounded
  90-second / 60-event one-shot Gemini 3.8 Flash Medium repair. It returned
  `repair_failed / invalid_artifacts` at 48 events and 61.797 seconds, with
  no accepted files or Stage 1 progress. Account allowance snapshots moved
  65%/99% to 65%/98% (weekly/five-hour); the 1pp five-hour change is
  account-level and rounded, not a precise call charge. Queue stayed
  `paused` / `FAILED`, no lease. No further identical repair was run.
- Binance's Stage 1 author used a fresh isolated Gemini 3.8 Flash Medium
  session containing only `authoring_prompt.md` (44,855 bytes). It returned
  all three nonempty artifacts in 85.033 seconds: 141,399 input, 38,058
  output, 32,729 thinking, 110,347 cache-read tokens, one turn. Account
  snapshots moved 66%/98% to 65%/96% (weekly/five-hour), with the same
  rounding/concurrency caveat. The worker then ran first-pass Stage 1
  validation: fixed parts were injected; `LW-039`, optimization, supported
  ATS terms, and extra-packet checks passed. It failed on CL-012, LR-026,
  one repeated phrase, and one uncited factual sentence. Coverage and one
  JD-term attention flag plus one forwarded high-priority evidence note
  were nonblocking. No Stage 2 phase ran for Binance yet.

### Pack 6 checkpoint

| Job | Stages cleared this pack | Repair / auto-fix | Agy quota evidence | End state |
|---|---|---|---|---|
| `healthstream` | None; prior Stage 0 PASS remains | One additional capped repair, 48 events / 61.797s, `invalid_artifacts`; 0 auto-fixes; no Stage 1 pass | Prompt 11,886 bytes; account weekly 65→65%, five-hour 99→98%; no final usage retained | `paused` / `FAILED`, no lease |
| `binance` | Stage 1 author artifacts landed; first-pass validation failed; no Stage 2 | One capped repair, 18 events / 5.906s, `invalid_artifacts`; 0 auto-fixes | Author prompt 44,855 bytes; author 85.033s, 141,399 input / 38,058 output / 32,729 thinking / 110,347 cache-read tokens; author account 66→65% weekly, 98→96% five-hour. Repair prompt 7,047 bytes; repair account 65→65% weekly, 96→97% five-hour, an upward rounded snapshot, not an attributable credit | `paused` / `FAILED`, no lease |
| `casper_studios` | None; Stage 0 still paused | No repair or auto-fix this pack | 0 new calls | `paused` / `WAITING_FOR_INPUT` |

The two `invalid_artifacts` results are distinct live failures on the same
one-shot runner. `scripts/run_stage1_repair.py` returned only the generic
reason and did not persist the rejected response or its final usage; the
failure could be model output format, stream extraction, or both. The
code's result parser reads final `output`/`text` but not Agy's observed
`result.response` field, while artifact validation requires all three
fenced blocks. This is a suspected mechanism, not a proven diagnosis from
the rejected output. The author call's `SUCCESS` and files are not a Stage 1
pass. Quota snapshot changes are account-wide and rounded; an increase must
not be reported as a negative cost or a free repair.

Casper has four completed Review Center confirmations and zero open ones,
but its latest Stage 0 receipt has `pause_kind=subscription_review` after
those answers. No `stage0_cascade_import.json` exists, so current
change-detection correctly does not auto-promote it. The post-item-5
omitted-ID retry has not run live. It needs an explicit safe retry trigger,
not another generic worker claim.

**Stop condition:** Stage 1 cannot advance on two jobs after capped repairs,
with quota spent and no valid repaired artifacts. The requested three new
queued jobs were not claimed. End queue: 38 queued, 3 paused, 2 done.
No job from this pack reached Stage 2 or `ready_to_finalize`; no finalize,
commit, push, or direct queued-slug `run_submission.py` invocation occurred.

## Pack 7 start (post-FIXQUEUE 9j-9k)

- Start commit: `aa833ab8dc260b103f7cec91ddc6efddbe01563d`.
- FIXQUEUE read before claim: `Runtime hold: NO`; 9j and 9k marked landed.
  There were no leased or in-progress rows. This is the first worker pass
  validating 9j's new full-document repair outputs. Casper stays untouched
  until 9l's explicit requeue command lands.
- Cursor's 9j live verification already made one accepted repair call per
  job before this pack: HealthStream prompt 13.11 KiB, 23.25s, 1 counted
  event; Binance prompt 10.25 KiB, 28.359s, 1 counted event. Both kept the
  existing provenance file because the model omitted a replacement. Their
  rows are queued. These are not Codex calls; no before/after quota snapshot
  for them is available in this supervised run, so their point cost is
  unknown, not zero.

### Pack 7 mid-run and 9l handoff

The first worker pass on `aa833ab8dc260b103f7cec91ddc6efddbe01563d`
validated both accepted 9j repairs. Neither passed Stage 1: HealthStream
had five exact-provenance mismatches, and Binance had three provenance
mismatches plus LR-026. Both stayed paused FAILED; no Stage 2 ran. The
model's optional provenance output left the old file attached to rewritten
documents, which did not satisfy the exact-sentence verifier.

HealthStream repair round 4 was built from those findings: prompt 10,013
bytes (9.78 KiB), fresh Gemini 3.8 Flash Medium, 96.454 seconds, one
counted non-text event, accepted full documents. The raw response is saved
under `stage1_repair_attempts/4.txt`; it has Resume.md and CoverLetter.md
blocks but no provenance block. Account snapshots moved 65%/96% to
65%/95% (weekly/five-hour), an observed 1pp five-hour drop, not exact
per-call cost. Auto-fixes: none. The row was queued for validation.

Cursor set `Runtime hold: YES` during this sequence, so no further worker
or repair call was started until it returned to NO. Cursor then landed 9l;
the next pack starts at commit `453af92310f7ae5953d21442df07f0be6d2165e4`.
This is the first worker-path pass with 9l. FIXQUEUE was reread and hold
was NO before the next claim. Casper has not yet been requeued.

### Pack 7 checkpoint after 9l

HealthStream's first worker validation on commit `453af923...` still failed
Stage 1: three exact-provenance mismatches and a supported ATS term missing.
Its round-4 repair output was accepted as structurally valid, but it omitted
provenance and did not clear the gate. Stage 0 remained passed; Stage 2 did
not run. No deterministic auto-fix occurred in this round.

Binance repair round 3 used a 10,712-byte (10.46 KiB) prompt and a fresh
Gemini 3.8 Flash Medium one-shot call. It returned full documents in 86.890
seconds with one counted non-text event; the raw output is saved at
`stage1_repair_attempts/3.txt`. It again omitted provenance. Account
allowance snapshots moved 65%/96% to 65%/94% (weekly/five-hour), an
observed 2pp five-hour drop, not exact per-call cost. The next worker pass
cleared LR-026 and the ATS term but failed Stage 1 on two uncited passages
and one repeated phrase. No deterministic auto-fix; no Stage 2 run.

The accepted 9j repairs across these two jobs are now 4/4 without a
provenance block (two Cursor live probes and one Codex round for each job).
The builder's instruction to keep old provenance when omitted conflicts
with exact-text citation checks after a document rewrite. This is logged
as a P0 cross-file contract issue in FIXQUEUE. No additional Agy repair was
started after the second live recurrence.

Casper was requeued exactly once via the new 9l command with an audited
reason. The queue transition succeeded, but the worker returned the
existing `WAITING_FOR_INPUT` Stage 0 receipt in under one second: no new
evidence call, preserved stream, or missing-ID list was generated. The
orchestrator's subscription-review predicate still requires a cascade
import file; the queue requeue intent alone does not satisfy it. Casper is
again paused `WAITING_FOR_INPUT`. This full-path gap is logged in FIXQUEUE.

| Job | Stage 0 this pack | Stage 1 this pack | Stage 2 | Quota this pack | End queue |
|---|---|---|---|---|---|
| `healthstream` | No new call; prior PASS | Repair round 4 accepted, then validation FAILED; 0 auto-fixes | Not run | 10,013-byte prompt; 96.454s / 1 event; account 65→65% weekly, 96→95% five-hour | `paused` / `FAILED` |
| `binance` | No new call; prior PASS | Repair round 3 accepted, then validation FAILED; 0 auto-fixes | Not run | 10,712-byte prompt; 86.890s / 1 event; account 65→65% weekly, 96→94% five-hour | `paused` / `FAILED` |
| `casper_studios` | Explicit 9l requeue, no evidence call; old pause returned | Not reached | Not run | No new Agy call | `paused` / `WAITING_FOR_INPUT` |

Pack end: 38 queued, 3 paused, 2 done. Neither HealthStream nor Binance
cleared Stage 1, so the conditional three-new-job confidence pack was not
started. No `ready_to_finalize` job was produced and no `--finalize`,
commit, push, or direct queued-slug `run_submission.py` call occurred.
