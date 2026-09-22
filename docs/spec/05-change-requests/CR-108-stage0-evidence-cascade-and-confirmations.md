---
status: in_progress
created: 2026-08-31
related: CR-093, CR-105, CR-091, CR-107, CR-015, CR-122
implementation_plan: ../08-implementation/IMP-CR-108-stage0-evidence-cascade.md
---

# CR-108 - Stage 0 evidence cascade, durable checkpoints, and skill confirmations

**Partial supersession (CR-122, 2026-09-21):** `AC-363` pause-on-unknown-tool and durable `NOT_PRESENT` / `UNSURE_NO_REASK` as forever-No are superseded. Unknown tools still create grouped Review Center cards. They default to WE (not evidence for that JD) and do not pause Stage 0. Required named tools withhold via CR-121 `conversion_risk`. `BAD_DATA`, `CONFIRMED_USE` / `FR-284`, and `hard_gate_review` pauses remain.

## Decision summary

Replace Stage 0's one-model-call-per-requirement path with a validated cascade:

1. Existing deterministic Stage 0 exclusion gates remain first.
2. A zero-cost evidence index resolves only high-precision, already-grounded matches
   and safe administrative cases.
3. Ambiguous requirement lines are sent in one structured batch per opportunity to
   the configured first provider. The default chain is Groq, then Gemini.
4. A local model is an explicit user-selectable option, not the default and not an
   implicit fallback.
5. A proposed HARD decision is never accepted from a low-confidence or ungrounded
   response. It is escalated to Gemini or held for review.
6. A named skill or tool that is not present in the profile is not silently treated
   as a permanent gap. It creates a durable confirmation item and pauses only that
   opportunity. Other opportunities continue. A possible unresolved HARD result
   uses the same durable input workflow with a different question type.
7. The answer is stored as reusable skill memory. A confirmation is allowed to
   improve Stage 0 fit judgment, but it does not authorize a resume claim until
   the reviewed details are verified in the local source of truth.

This is an accuracy-first change. The primary release gate is no regression from
CR-093's validated 21/21 gate-and-source result. Cost reduction is achieved by
avoiding calls for high-precision deterministic matches and by batching the
remaining work, not by accepting a weaker classifier.

### Hardening increment approved 2026-08-31

The remaining CR-108 work is now explicitly scoped as a validation and safety
increment rather than an implicit default cutover:

1. The CR-093 golden set gets a provider-adapter runner with deterministic Groq
   and Gemini transport fixtures. A live provider sample remains opt-in and is
   never part of the default test suite because it requires the user's
   configured credentials and can spend quota.
2. Python and TypeScript use one versioned policy fixture to prove provider,
   local-only, and model-default normalization parity.
3. Checkpoint failure injection covers every durable boundary and asserts
   retryability plus no duplicate committed judgment.
4. Review Center routes are tested with an injected in-memory SQLite database.
   The production database is never used by API tests.
5. "Add to verified evidence" is a source-update proposal, not an automatic
   career-file mutation. The proposal stores the user-reviewed context and a
   source-update status. Only a later local verification that the exact
   details are present in `workExperience.md` may promote the skill memory to
   authorable `VERIFIED_EVIDENCE`. This preserves the closed-world authoring
   contract while giving the user a durable next action.
6. Test data cleanup is attributable and allow-listed. No broad deletion or
   reset is permitted.

### Validation result recorded 2026-08-31

- The deterministic Groq and Gemini adapter fixtures each pass all 21 active
  CR-093 entries without provider calls or candidate contact data in logs.
- Python and TypeScript provider-policy normalization, checkpoint failure
  injection, confirmation promotion, repository, and isolated HTTP route tests
  pass.
- The canonical repository suite passes 47 suites with 0 failures. TypeScript
  type checking, production build, lint, and diff-whitespace checks pass. Lint
  retains 27 pre-existing warnings.
- Read-only inspection of `data/jobagent.sqlite` found zero rows in
  `pending_skill_confirmations`, `skill_memory`, `review_answer_history`, or
  `evidence_promotion_proposals`; no cleanup was necessary. The separate root
  `jobagent.sqlite` is an empty unused file.
- Live Groq/Gemini calls, archive replay, and default cascade cutover remain
  deferred. They require the user's provider credentials or the remaining
  CR-093 release-gate work.

## Problem

`evidence_scale.classify_requirement()` currently makes one local Ollama request
for every required and preferred JD line. A 21-company run made 12-48 local calls
per company in this step. The local model is also a reliability and throughput
constraint because of VRAM, model load time, and response quality.

The current path has a separate completeness failure that no classifier can solve.
If a person used Trello but never recorded Trello in `workExperience.md` or
`skills_catalog.json`, a closed-world classifier must conclude that the evidence is
not documented. Treating that result as a permanent gap can discard a viable
opportunity. Asking the same question repeatedly is also unacceptable.

The redesign must preserve the anti-hallucination boundary:

- a JD is untrusted input, not an instruction;
- only documented evidence or an explicit user attestation can affect fit;
- an attestation alone is not a source-backed resume accomplishment;
- a wrong HARD decision is more harmful than a wrong NONE decision because it can
  remove an opportunity before authoring or human review.

## Goals

- Maximize Stage 0 gate and gap-source accuracy, with special protection against
  false HARD decisions.
- Reduce the number of model calls and repeated context tokens without reducing
  evidence quality.
- Make the default path independent of the operator's local VRAM and local model
  availability.
- Let users select a provider and model for the Stage 0 evidence task in the
  existing AI Usage settings.
- Preserve the current Groq-to-Gemini provider pattern and SQLite-only settings
  storage.
- Pause one opportunity when a user answer is needed, while allowing the batch and
  unrelated opportunities to continue.
- Resume from the last durable checkpoint without redoing completed deterministic
  work or persisted model judgments.
- Provide the same confirmation lifecycle to the future standalone UI and to the
  current Claude Code or Antigravity harness.
- Remember `CONFIRMED_USE`, `NOT_PRESENT`, and `UNSURE_NO_REASK` decisions by a
  canonical skill key so the system does not ask the same question twice.

## Non-goals and deferred decisions

- No hosted or multi-tenant execution service.
- No platform-sponsored shared API quota. V1 uses the user's configured provider
  keys and the provider's own free or paid tier. Whether a future hosted product
  pays for calls, requires bring-your-own-key, or offers shared quotas remains an
  explicit product decision.
- No fine-tuning, custom classifier training, or learned user profile model.
- No Temporal, Prefect, LangGraph, or other external durable-workflow dependency in
  V1. The existing SQLite and workflow receipt architecture is sufficient for the
  local single-user deployment.
- No automatic mutation of `workExperience.md`, `master_claims.json`, or
  `skills_catalog.json` from a single Yes answer.
- No CLI-first user experience. A small CLI/status surface may exist for diagnostics
  and the harness adapter, but the product surface is the UI review workflow.
- No redesign of JD section extraction. CR-105 owns that path.
- No change to the existing Stage 0 DB, preferences, title, location, years, or
  exclusion-zone gates except where their result must be represented in the new
  durable state.
- No automatic job submission or external action.

## Scope decision

### V1 ships

1. A Stage 0 evidence cascade with a deterministic evidence index and batched
   provider fallback.
2. Provider and model configuration for the `stage0_evidence_classification` task
   in AI Usage.
3. Structured per-item judgment contracts, asymmetric HARD policy, and validation
   telemetry.
4. SQLite migrations for run checkpoints, per-item judgments, skill memory, and
   pending confirmation occurrences.
5. A per-opportunity `WAITING_FOR_INPUT` state that is distinct from Stage 2's
   `NEEDS_DISPOSITION`, covering both missing skill confirmation and unresolved
   high-risk HARD review.
6. Resume behavior that consumes a resolved skill decision and continues only the
   affected opportunity.
7. A Review Center UI with grouped skill cards, job context, answer actions,
   progressive evidence capture, and a badge or link from the relevant job detail.
8. A harness response contract so Claude Code or Antigravity can present the exact
   same question and write the answer through the same resolver.
9. Golden-set, archive-corpus, crash-recovery, provider-failure, and UI/API
   validation before the cascade becomes the default.

### V1 remains legacy-only during rollout

The current per-line implementation is retained temporarily behind an explicit
rollback setting while CR-108 is validated. It is not a second supported product
path after the release gate passes. The final rollout story removes the legacy
implementation and updates all current references, following CR-093's explicit
delete-old-mechanisms discipline.

## Detailed design

### 1. Evidence layers

#### Layer A: existing deterministic gates

The existing DB cooldown, preference exclusion, title, location, years, and other
explicit Stage 0 gates continue to run before evidence classification. Their
behavior and precedence do not change.

#### Layer B: deterministic evidence index

Build a per-run, in-memory index from:

- the full `workExperience.md` text, chunked on headings;
- the verified `skills_catalog.json`;
- the tags-only claim index;
- the existing aliases and canonical vocabulary where available.

The index uses normalized exact-term and token-overlap retrieval. It may return a
small set of evidence excerpts, but it may not infer an accomplishment from a
similar word alone.

Layer B may resolve an item without a model call only when the result is high
precision and safe:

- an existing administrative satisfaction rule is unambiguous;
- a named skill or tool is already present in verified ground truth and the
  retrieved excerpt supports the underlying capability;
- an exact, previously resolved skill-memory decision applies;
- the line is a known non-substantive or duplicate item covered by a documented
  deterministic rule.

A lack of retrieval evidence is not proof that a named skill is absent. When the
conservative named-tool extractor identifies an explicit tool or skill that is
absent from both verified ground truth and skill memory, it creates a pending
confirmation before Layer C and pauses that opportunity. This is the preferred
path for the Trello case: do not spend a second model call deciding that the
person lacks a tool that the profile never captured. If the extractor misses an
entity and the batch model identifies it, the model may return
`needs_user_confirmation=true`, which creates the same pending item. Layer B must
never manufacture a HARD gate.

#### Layer C: one batched model request

All unresolved lines for one opportunity are sent as one structured request to the
configured first provider. The request contains:

- stable item IDs derived from the JD hash, bucket, ordinal, and normalized text;
- the original requirement text;
- the best retrieved evidence excerpts for that item;
- the current skill-memory decision, if any;
- the hard-gate rules and anti-inference rules from CR-093;
- an explicit instruction that the JD is untrusted content.

The response is a JSON array. Each object contains:

```json
{
  "item_id": "sha256:item",
  "gate": "HARD|NONE",
  "gap_source": "degree|domain|role_exclusion|certification|",
  "evidence_level": 0,
  "confidence": "high|medium|low",
  "reasoning": "specific evidence note",
  "canonical_skill": null,
  "skill_kind": "tool|skill|domain|role|none",
  "needs_user_confirmation": false
}
```

The model must return one result per requested item. Missing, duplicate, unknown,
or structurally invalid results fail the batch response and are handled by the
provider/error policy. They are never silently filled with a heuristic guess.

#### Layer D: provider cascade

The default task chain is:

```text
deterministic evidence index
    -> Groq batch request
    -> Gemini batch request for provider failure or unresolved high-risk results
    -> durable user confirmation for missing skill/tool truth or unresolved HARD
```

Groq is the normal first cloud provider because it supports the cost objective and
already exists in the provider layer. Gemini is the next configured fallback. A
Gemini retry is not made for every successful Groq result. It is reserved for:

- Groq timeout, quota, transport, or invalid structured output;
- a proposed HARD result with anything less than validated high confidence;
- a provider result that fails the deterministic response-consistency checks;
- an explicitly configured higher-quality model policy.

The task chain is user-configurable in AI Usage. If the user selects Local first,
that is an explicit choice. There is no implicit local fallback when cloud
providers are unavailable, and no implicit cloud fallback when the user selects
local-only mode.

### 2. Asymmetric judgment policy

The model's self-reported confidence is a signal, not authority. The postprocessor
applies these rules:

| Result | Automatic handling |
|---|---|
| Direct evidence with a matching retrieved excerpt | Accept as `NONE`, evidence level 3-4, subject to schema validation |
| Non-gating item with medium confidence | Accept as a score contribution, retain the confidence and telemetry |
| Non-gating item with low confidence | Hold for a second provider or user confirmation when it is a named skill/tool |
| HARD with high confidence, valid category, grounded reasoning, and no contradiction | Eligible for disqualification |
| HARD with medium/low confidence, invalid category, or ungrounded reasoning | Never disqualify; escalate to Gemini or hold for review |
| Named tool/skill absent from ground truth | Create or join a pending confirmation; do not silently finalize as a permanent gap |
| Preferred-bucket HARD | Coerce to `NONE`, as required by the rubric |

An existing deterministic exclusion gate can still reject before this cascade when
its own contract says it is authoritative. CR-108 does not widen those gates.

The score remains the CR-093 weighted formula. No new weights, confidence
multipliers, or score bands are introduced by this CR.

### 3. Missing skill and tool detection

The system distinguishes three cases:

1. **Known and documented:** canonical key is in the verified profile/catalog and
   retrieval supports it. No question is created.
2. **Known absent:** a prior user decision says `NOT_PRESENT`. The item is scored as
   not documented (evidence level 0, no authoring `claim_ids`) and is not asked again.
   Named tools stay SOFT: they never HARD-skip the opportunity. Transferable bridges
   must not copy the JD tool name.
3. **Unknown to the profile:** a named skill/tool candidate is not in the verified
   profile or memory. The item creates a confirmation question and the
   opportunity pauses before a final Stage 0 verdict.
4. **Known by attestation:** a prior user decision says `CONFIRMED_USE`, but no
   evidence details have been promoted. Stage 0 may treat the named tool as
   present at evidence level 1 for the Stage 0 fit ledger, but it must not raise
   the item above level 1 or treat the attestation as authorable evidence.

A generic responsibility such as "communicate clearly" is not an unknown tool and
must not generate a question. Candidate extraction is limited to explicit named
tool/skill forms and named entities, with conservative normalization and a
confidence flag. The profile-plausibility signal described below is a routing aid,
not proof of absence. A user decision always overrides a plausibility prior.

An unresolved high-risk HARD result is a separate confirmation type, not a skill
memory row. After the configured provider chain is exhausted, it creates a
`hard_gate_review` input with the requirement, the evidence excerpts, the model
reasoning, and the reason it was not safe to auto-disqualify. It must offer
`KEEP_ELIGIBLE` and `CONFIRM_HARD` actions, and may offer `NEEDS_MORE_INFO`.
`KEEP_ELIGIBLE` clears the proposed HARD result and continues weighted scoring.
`CONFIRM_HARD` is the only user action that may authorize the hard-gate result.
`NEEDS_MORE_INFO` keeps the opportunity waiting until the user supplies the
requested context or changes the decision.

The system may derive broad profile domains from existing headings and verified
tags to prioritize questions and avoid asking about ordinary responsibilities that
are clearly not tool/skill entities. It may not conclude that a user lacks a skill
solely because their current occupation makes it seem unlikely.

### 4. Durable skill memory

Skill memory has two levels:

- `CONFIRMED_USE`: the user attests that they have used the skill or tool. This can
  resolve the Stage 0 completeness question and can be shown to later authoring
  stages as an attestation. It is a presence signal only, capped at evidence
  level 1 until details are supplied; it cannot satisfy a direct-evidence
  requirement.
- `VERIFIED_EVIDENCE`: the user supplies source-backed context, such as the
  project, responsibility, timeframe, scope, or metric. This is the only level
  eligible for an explicit promotion proposal into the authoring evidence map or
  the verified work-experience/catalog path. The initial answer flow still does
  not write either file.

Negative and uncertain decisions are also durable:

- `NOT_PRESENT`: do not ask again unless the user edits the decision.
- `UNSURE_NO_REASK`: do not ask again automatically. Treat the skill as
  unverified for authoring and leave the decision visible for later editing.

A Yes answer never causes a resume or cover-letter claim by itself. The packet
builder must continue to enforce the closed-world claim contract and must mark
attestation-only skills as not authorable until verified evidence exists.

### 5. Durable execution and checkpointing

The existing folder receipts remain authoritative for Stage 0 completion. SQLite
adds the finer-grained execution memory required to resume safely:

- `stage0_runs`: one row per opportunity run, keyed by submission slug and JD hash;
- `stage0_judgments`: one row per deterministic or model judgment, keyed by stable
  item ID and request hash;
- `skill_memory`: one canonical decision per normalized skill key;
- `pending_skill_confirmations`: one occurrence per opportunity, with a
  `question_type` (`skill_presence` or `hard_gate_review`), an optional foreign
  reference to the canonical skill memory key, and the requirement context.

The execution protocol is:

1. Compute the run key and item keys from content hashes. Reuse a completed
   judgment only when the item, JD hash, prompt version, provider/model policy,
   and evidence index version all match.
2. Persist a `REQUESTED` batch record and an atomic request payload before making
   a provider call.
3. Never hold a SQLite write transaction open during a network/model call.
4. Persist the raw response to an atomic local spool file immediately after the
   call returns, then validate and commit item judgments in a short transaction.
5. Commit pending confirmation rows before returning `WAITING_FOR_INPUT`.
6. Write the Stage 0 receipt only after all items are resolved and the weighted
   score is complete.
7. On resume, consume committed judgments and skill decisions first. Only the
   missing or invalid work is retried.

This provides at-most-once reuse after a persisted response. A crash in the
unavoidable interval between a provider accepting a request and the local process
persisting its response can still cause a provider retry because the provider APIs
do not share one universal idempotency contract. The design must document and
measure that boundary rather than claim impossible exactly-once network behavior.

SQLite continues to use WAL, a busy timeout, short transactions, and additive
idempotent migrations. Spool files are local, hash-addressed, and excluded from
tracked Git data.

### 6. Opportunity state and batch behavior

`WAITING_FOR_INPUT` is a Stage 0 state meaning that this opportunity has durable
pending questions. It is not the same as Stage 2 `NEEDS_DISPOSITION`, and it is
not a global pipeline pause.

When an opportunity reaches this state:

- its completed judgments and pending questions are durable;
- its final Stage 0 score and PASS/SKIP placement are not minted yet;
- the current batch records the opportunity as waiting and continues with the next
  opportunity;
- the UI shows the opportunity as "Needs your answer";
- a harness invocation prints a structured question with the confirmation ID and
  answer options;
- resolving the question schedules or allows `--resume` for that opportunity only.

If multiple unknown tools are discovered in one batch, the UI groups them by
canonical skill key and the opportunity remains paused until all required questions
are resolved. A skill already answered elsewhere is applied without another prompt.

### 7. User experience

The product surface is a dedicated **Review Center** in the persistent sidebar,
not a passive notification, a transient modal, or a second per-job workflow.
The page uses a two-pane queue-and-detail layout that fits the existing Applyr
shell:

- the sidebar item is labeled `Review Center` and shows the unresolved-item count;
- the left queue has `Needs your answer`, `Strengthen evidence`, and `Completed`
  views, with open work first and a clear empty state;
- items are grouped by canonical skill, so one answer resolves repeated occurrences;
- the right detail pane focuses on one question at a time and shows why it exists,
  which jobs are affected, the relevant requirement text, and what the answer will
  change;
- skill questions use plain-language actions: `Yes, I've used it`, `No`, and
  `Not sure`;
- selecting Yes progressively reveals optional evidence fields. The initial
  presence answer is saved without forcing a long form;
- when enough details exist for a stronger claim, Applyr shows a reviewable
  evidence preview and requires an explicit `Add to verified evidence` action;
- No and Not sure complete the question without inventing evidence and explain
  what happens next;
- `hard_gate_review` items use `KEEP_ELIGIBLE`, `CONFIRM_HARD`, and, when needed,
  `NEEDS_MORE_INFO` instead of skill-presence actions. The consequence is stated
  next to the action, not hidden in a confirmation dialog;
- job detail shows a paused banner and links back to the relevant Review Center
  item, but does not duplicate the question workflow;
- after resolution, the page shows what changed and which jobs can resume;
- notifications may link to the queue, but never replace the queue.

These choices apply established service-design patterns:

- GOV.UK's question-page pattern keeps a question focused and understandable.
- GOV.UK's check-answers pattern supports a review step before committing
  consequential information.
- Nielsen Norman Group's progressive-disclosure guidance supports hiding optional
  evidence fields until the user chooses Yes.
- Material Design's dialog guidance supports avoiding modal interruption for a
  multi-field evidence task. Hard-gate consequences remain inline and explicit.

The Review Center is therefore a queue plus a focused question page, not a
dashboard of simultaneous forms. Keyboard focus moves to the selected question,
all actions have visible text labels, errors appear beside the relevant field,
and the selected queue item remains identifiable after a save or answer.

The harness adapter emits the same question object:

```json
{
  "type": "stage0_skill_confirmation",
  "question_type": "skill_presence",
  "confirmation_id": "sc_...",
  "skill_key": "trello",
  "question": "Have you used Trello in your work?",
  "affected_opportunities": ["example_slug"],
  "options": ["CONFIRMED_USE", "NOT_PRESENT", "UNSURE_NO_REASK"],
  "evidence_requested": true
}
```

The UI and harness both call the same resolver. They must not maintain separate
decision stores or separate normalization rules.

For a hard-gate review, the adapter uses the same envelope with a different
question type and action set:

```json
{
  "type": "stage0_hard_gate_review",
  "question_type": "hard_gate_review",
  "confirmation_id": "hg_...",
  "requirement": "Requires an active professional license",
  "question": "Should this requirement disqualify the opportunity?",
  "affected_opportunities": ["example_slug"],
  "options": ["KEEP_ELIGIBLE", "CONFIRM_HARD", "NEEDS_MORE_INFO"]
}
```

### 8. Settings and provider/model selection

Add `stage0_evidence_classification` to the existing AI Usage surface. The task
settings need:

- provider chain or first-provider selection, with the default displayed as
  `Groq, then Gemini`;
- an explicit Local option;
- provider-specific model fields. A model identifier may be selected from a
  supported list or entered explicitly when the provider supports arbitrary model
  IDs. Groq and Gemini must not share one model field because their model names
  are provider-specific;
- a local-only toggle for users who intentionally want no cloud calls;
- a clear note that provider keys and any applicable provider charges belong to the
  user in V1;
- a visible local usage summary for calls, batches, fallback count, and pending
  confirmations. The summary is aggregate telemetry only and never includes
  provider credentials or candidate contact text.

V1 should store a versioned task configuration object, for example:

```json
{
  "stage0_evidence_classification": {
    "provider_order": ["groq", "gemini"],
    "models": {
      "groq": "configured Groq model",
      "gemini": "configured Gemini model",
      "local": "configured Ollama model"
    },
    "local_only": false
  }
}
```

The existing `taskProviderOverrides` shape remains readable for CR-105/106
compatibility, but it must not be overloaded with model or chain semantics.
Task-scoped Stage 0 configuration takes precedence over the global primary
provider setting. `LOCAL_ONLY_MODE=1` remains a global safety switch and forces
the task to local-only, but merely having Local configured or having another
task use Local must not silently redirect Stage 0.

### 9. Privacy boundary

Before a cloud request:

- only the JD item and retrieved evidence excerpts for that item are included;
- contact and professional-reference sections remain excluded;
- existing PII redaction in `call_llm` remains active;
- no raw skill-memory table or unrelated career history is sent;
- the selected provider/model and request hash are recorded locally, but API keys
  and raw secrets are never logged.

Cloud use is opt-in through configured provider credentials. The product does not
silently create a shared account or send career data to a hosted Applyr service.

## Acceptance criteria

- [ ] The deterministic layer resolves only its approved high-precision cases and
      makes zero provider calls for those cases.
- [ ] All unresolved requirement lines for one opportunity are represented in one
      structured batch request, subject to a documented request-size limit.
- [ ] The default configured chain is Groq then Gemini, with Gemini reserved for
      provider failure or high-risk unresolved results.
- [ ] The user can select the Stage 0 evidence provider and supported model in
      Settings > AI Usage. Selecting Local is explicit and does not silently alter
      other tasks.
- [ ] The new structured response validator rejects missing, duplicate, malformed,
      or ungrounded item results without substituting a heuristic judgment.
- [ ] CR-093's active 21-entry golden set retains 21/21 correct `gate` and
      `gap_source` results. Evidence levels remain exact or within the existing
      +/-1 tolerance.
- [ ] The false-positive domain and degree cases remain non-HARD, and no tool-only
      case becomes HARD.
- [ ] A proposed HARD result with low/medium confidence, invalid category, or
      ungrounded reasoning cannot disqualify an opportunity.
- [ ] An unknown named tool absent from ground truth creates one durable pending
      confirmation and does not silently finalize as a permanent gap.
- [ ] If the configured providers cannot safely resolve a proposed HARD result,
      a durable `hard_gate_review` input is created and the opportunity is not
      auto-Skipped. Only `CONFIRM_HARD` can authorize that disqualification.
- [ ] `KEEP_ELIGIBLE` clears a proposed HARD result for weighted scoring,
      `CONFIRM_HARD` authorizes disqualification, and `NEEDS_MORE_INFO` keeps
      the opportunity waiting for additional context.
- [ ] Repeated occurrences of the same canonical skill are grouped and one answer
      resolves all eligible occurrences without another question.
- [ ] `CONFIRMED_USE` may improve the Stage 0 fit ledger only at evidence level 1.
      It cannot satisfy direct evidence, and no resume or cover-letter claim is
      permitted until `VERIFIED_EVIDENCE` exists.
- [ ] `NOT_PRESENT` and `UNSURE_NO_REASK` are durable and suppress duplicate
      questions on later opportunities.
- [ ] A waiting opportunity persists its completed judgments and does not block
      unrelated opportunities in the same batch.
- [ ] Resolving a question and resuming reuses completed judgments and resumes from
      the next missing item. It does not rebuild or repeat the completed batch.
- [ ] A crash injected before, during, and after each checkpoint leaves a
      recoverable run. Invalid or incomplete requests are retryable; committed
      judgments are not repeated.
- [ ] The UI Review / Questions page and the harness adapter use the same
      confirmation records, normalization, and resolver.
- [ ] Review Center uses the existing sidebar shell, presents one focused question
      at a time, progressively reveals optional evidence fields, and requires an
      explicit review action before stronger evidence is promoted.
- [ ] Cloud payloads contain only the intended JD/evidence context and remain
      covered by the existing PII-redaction tests.
- [ ] The legacy path is removed after the cascade cutover gate passes. Until then,
      rollback is explicit, visible, and covered by tests.
- [ ] The active CR-093 golden entries pass through deterministic Groq/Gemini
      provider fixtures, and any live-provider result is recorded separately
      without credentials or contact text.
- [ ] Python and TypeScript produce identical normalized Stage 0 provider policy
      output for the shared fixture.
- [ ] Every Stage 0 checkpoint boundary has failure-injection coverage.
- [ ] Review Center API integration tests use an injected isolated database.
- [ ] Evidence promotion creates a pending source-update proposal and does not
      authorize Stage 1 until local source-of-truth verification succeeds.
- [ ] Generated test rows are reviewed and cleaned only when their provenance is
      confirmed.

## Validation plan

### Accuracy gate

Run the cascade against the frozen CR-093 golden set with the same candidate data,
active entries, and expected semantics. Compare:

- `gate` accuracy;
- `gap_source` accuracy;
- evidence-level exact and +/-1 agreement;
- false HARD count, especially on tool and false-positive domain/degree rows;
- pending-confirmation precision and recall on missing-ground-truth fixtures.

The release gate is 21/21 on `gate` plus `gap_source`, zero false HARD on the
existing false-positive/tool protections, and no unexplained schema or item loss.
Any failure blocks production cutover.

### Cost and latency comparison

Run the old and new paths on a fixed archive sample with identical JD and profile
inputs. Record locally:

- provider calls per opportunity;
- batched requests per opportunity;
- input/output tokens when providers expose them;
- fallback count;
- deterministic-resolution rate;
- wall-clock duration;
- number of opportunities paused for user input.

Cost reduction is a secondary measure. A cheaper path that misses a golden hard
gate or creates an unsafe HARD result fails the release.

### Durability and failure injection

Test process termination or simulated failure:

- before request creation;
- after request creation but before provider call;
- after provider response before spool persistence;
- after spool persistence before judgment commit;
- after judgment commit before pending-row commit;
- after pending-row commit before the process exits.

Also test provider timeout, 429, malformed JSON, partial batch response, duplicate
resume, answer changes, and a second job running while the first waits.

### UI and harness verification

- API tests cover list, grouped view, skill answers, hard-gate answers, evidence
  attachment, idempotent repeat answer, and resume scheduling.
- Vitest covers badge counts, group rendering, affected-job links, skill and
  hard-gate answer actions, and the paused-job state.
- Harness tests assert that the emitted confirmation object is actionable and that
  a harness answer resolves the same database row the UI would resolve.

### Rollout

1. Build the deterministic and durable pieces behind a disabled cascade flag.
2. Run the golden and offline failure suites.
3. Run provider-backed batch validation using the configured Groq/Gemini chain.
4. Enable the cascade for a controlled archive sample.
5. Compare receipts, pending questions, scores, call counts, and errors.
6. Make the cascade default only after the accuracy gate passes.
7. Remove the local-only legacy classifier and its rollback flag in the final CR
   implementation story.

## Research basis

This design uses the following current external guidance as principles, not as a
substitute for Applyr-specific validation:

- Temporal, "Reliable document approvals with human-in-the-loop workflows":
  https://docs.temporal.io/guides/reliable-document-approvals
- Temporal, Python error handling: retry policies and idempotent Activities:
  https://docs.temporal.io/develop/python/best-practices/error-handling
- LangGraph, durable execution: deterministic and idempotent workflow steps:
  https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph, interrupts: side effects before a pause should be idempotent:
  https://docs.langchain.com/oss/python/langgraph/interrupts
- Prefect, interactive workflows: pause or suspend a flow for UI input:
  https://docs.prefect.io/v3/advanced/interactive
- SQLite, Write-Ahead Logging:
  https://sqlite.org/wal.html
- Dynamic model routing and cascading research:
  https://arxiv.org/html/2606.27457v1
- GOV.UK Design System, question pages:
  https://design-system.service.gov.uk/patterns/question-pages/
- GOV.UK Design System, check answers:
  https://design-system.service.gov.uk/patterns/check-answers/
- GOV.UK Service Manual, designing good questions:
  https://www.gov.uk/service-manual/design/designing-good-questions
- Nielsen Norman Group, progressive disclosure:
  https://www.nngroup.com/articles/progressive-disclosure/
- Material Design 3, dialogs:
  https://m3.material.io/components/dialogs/guidelines

The practical conclusions applied here are: make external calls replay-safe,
persist state before and after side effects, keep human input as a durable signal,
and measure the quality/cost frontier rather than assuming that a cheaper route is
an acceptable route.

## Open questions

1. For a future hosted release, will users bring provider keys, will Applyr
   sponsor a quota, or will both modes exist? V1 deliberately does not decide.
2. Which provider-specific model catalog should the UI expose beyond free-text
   model identifiers? V1 stores supported model selections without building a
   provider marketplace.
3. What evidence fields are sufficient for a `VERIFIED_EVIDENCE` promotion into
   `workExperience.md` or `skills_catalog.json`? The promotion must remain an
   explicit user edit and should be specified before that write path is built.
