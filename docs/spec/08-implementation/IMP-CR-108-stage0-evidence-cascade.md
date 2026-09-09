---
status: in_progress
created: 2026-08-31
change_request: CR-108
requirements: FR-278-FR-285, NFR-009-NFR-012, DATA-002-DATA-004
---

# IMP-CR-108 - Stage 0 evidence cascade implementation plan

This remains a documentation-first implementation plan for the Stage 0 runtime.
The Review Center UI shell, client contract, additive migrations, repository,
authenticated list/answer API, Stage 0 producers, run checkpoints, workflow
pause/resume, provider batching, hard-gate review, and harness adapter are
implemented behind the explicit cascade rollout flag. The 2026-08-31 hardening
increment adds provider fixtures, policy parity, checkpoint failure injection,
isolated API tests, and the verified-evidence source-update boundary. The
deterministic 21-entry provider fixtures and API lifecycle checks pass. Archive
replay, live provider validation, live UI lifecycle validation, and default
cutover remain pending.

## Architecture boundaries

- `run_submission.py` remains the only Stage 0 workflow entry point and the only
  writer of Stage 0 receipts and workflow state.
- `evidence_scale.py` remains the public judgment contract during migration, but
  its per-line local-only call must be replaced by the cascade service.
- `build_stage0_fit_gate.py` remains responsible for Stage 0 extraction/wiring,
  not for provider selection or confirmation persistence.
- `scripts/utils.py` and `scripts/llm_stages.py` remain the provider boundary.
- `server/migrations/` owns additive SQLite schema changes.
- `scripts/stage0_confirmations.py` is the Python-side adapter over the same
  SQLite confirmation tables; it owns canonical skill normalization and is
  shared by Stage 0 and the harness.
- Review Center UI and harness answers call one shared resolver. Neither may edit JSON memory
  independently.

## Epics and stories

### Epic 1: Contracts and durable data

- [~] **1.1** Add versioned Stage 0 cascade settings and provider-specific
      model configuration types. Preserve CR-105/106 reads for existing task
      overrides without overloading their provider-only shape.
- [~] **1.2** Add additive migrations for `stage0_runs`,
      `stage0_judgments`, `skill_memory`, and `pending_skill_confirmations`.
      The skill-memory and pending-confirmation tables are landed in migration
      `018`, run/checkpoint tables in `019`, and append-only answer history in
      `020`.
- [~] **1.3** Define stable run/item/request hash functions and schemas for
      deterministic judgments, model batches, raw response spools, and
      confirmation payloads.
- [~] **1.4** Add idempotent repository functions for checkpoint writes, pending
      grouping, answer resolution, and skill-memory lookup. Server and Python
      adapters now share the SQLite boundary.
- [~] **1.5** Add privacy tests proving no API key, contact section, or unrelated
      profile text reaches logs or cloud payloads. The retrieval and cascade
      prompt boundary are covered offline.

### Epic 2: Deterministic evidence index

- [~] **2.1** Build the heading-aware work-experience evidence index using the
      existing retrieval rules and PII exclusions.
- [~] **2.2** Reuse verified catalog aliases and canonicalize named tools/skills.
- [~] **2.3** Implement conservative unknown named-skill/tool extraction. Add
      fixtures for Trello-like missing tools, generic responsibilities, employer
      product names, and role-category words that must not become tool questions.
- [~] **2.4** Implement only the approved zero-cost resolutions. Every other item
      must be explicitly marked ambiguous or pending model judgment.
- [~] **2.5** Add offline tests proving deterministic resolution never emits HARD.

### Epic 3: Batched provider cascade

- [~] **3.1** Replace one-call-per-line routing with one structured batch per
      opportunity and a documented maximum request size.
- [~] **3.2** Add the `stage0_evidence_classification` provider chain:
      deterministic, configured first provider, configured fallback, then
      confirmation/review. Default provider order is Groq then Gemini.
- [~] **3.3** Add provider-specific model selection without making local the
      default or an implicit fallback.
- [~] **3.4** Validate response completeness, schema, item identity, hard-gate
      category, reasoning grounding, and evidence-context boundaries.
- [~] **3.5** Implement asymmetric HARD handling. Escalate high-risk results to
      Gemini or create a `hard_gate_review` input for user review. Never allow
      low-confidence HARD to skip.
- [~] **3.6** Preserve the CR-093 weighted formula and score-band calibration
      unchanged.

### Epic 4: Durable Stage 0 workflow

- [~] **4.1** Persist a request record and atomic request spool before external
      calls. Persist raw responses before parsing.
- [~] **4.2** Reuse completed judgment rows only when content, prompt, provider,
      model, and index hashes match.
- [~] **4.3** Add `WAITING_FOR_INPUT` to the Stage 0 workflow contract without
      changing Stage 2 `NEEDS_DISPOSITION` semantics.
- [~] **4.4** Continue unrelated opportunities after one opportunity pauses.
- [~] **4.5** Resolve a skill decision and resume only the affected opportunity.
- [x] **4.6** Add crash and provider-failure injection tests for every checkpoint.

### Epic 5: Skill confirmation and evidence promotion boundary

- [~] **5.1** Create or join confirmation rows by canonical skill key.
- [~] **5.2** Implement `CONFIRMED_USE`, `NOT_PRESENT`, and
      `UNSURE_NO_REASK` with idempotent repeated answers.
- [~] **5.2a** Represent `CONFIRMED_USE` in the Stage 0 fit ledger at no more
      than evidence level 1. It may resolve an unknown-presence question but
      cannot satisfy direct evidence or become an authoring claim.
- [~] **5.3** Store optional evidence details as attestation context, never as an
      authoring claim by default.
- [~] **5.4** Add a separate, explicit promotion contract for
      `VERIFIED_EVIDENCE`. Do not write `workExperience.md` or catalog files in the
      initial answer path.
- [~] **5.5** Add regression tests ensuring a Yes answer cannot create an
      unsupported resume or cover-letter claim.
- [~] **5.6** Implement `KEEP_ELIGIBLE`, `CONFIRM_HARD`, and
      `NEEDS_MORE_INFO` for `hard_gate_review` inputs, with audit history and
      idempotent repeated answers.

### Epic 6: Standalone UI and harness adapter

- [~] **6.1** Add a Review Center page with grouped canonical skills,
      affected opportunities, requirement context, progressive evidence fields,
      and answer actions.
- [~] **6.2** Add a navigation badge and links into the grouped question.
- [~] **6.3** Add provider/model controls and explanatory cost/privacy text to
      Settings > AI Usage.
- [~] **6.4** Add API endpoints for list, answer, and source-promotion
      verification. Keep mutations idempotent. Resume scheduling remains
      intentionally outside this increment.
- [~] **6.5** Add the machine-readable harness confirmation contract and route
      harness answers through the same resolver.
- [~] **6.6** Add Vitest and API integration coverage for the full UI lifecycle.

### Initial UI slice implemented

- `src/pages/ReviewCenterView.tsx` implements the queue/detail experience,
  progressive evidence enrichment, hard-gate action presentation, explicit
  evidence preview, and affected-job links.
- `src/hooks/useReviewCenter.ts` and `src/lib/reviewCenter.ts` define the client
  loading, normalization, answer, and 404-safe service boundary.
- `src/components/Sidebar.tsx` and `src/App.tsx` add the first-class navigation
  destination and pending-count badge.
- `src/lib/reviewCenter.test.ts` covers response normalization and the minimum
  evidence threshold.
- `server/routes/reviewCenter.ts` exposes authenticated list and answer endpoints.
  It also exposes the authenticated source-promotion verification endpoint. The
  client still preserves the truthful unavailable state for deployments where the
  API is not present.

### Current implementation status

The explicit `STAGE0_EVIDENCE_CASCADE` path now batches retrieved evidence
excerpts, persists request/response spools with verified hashes, reuses matching
judgment checkpoints, and pauses on durable skill or hard-gate reviews. The
workflow resumes the affected opportunity after a resolved answer without
mutating authoring files or source-of-truth career data. The legacy classifier
remains the rollback path until Epic 7 golden and provider-backed validation is
complete.

### Epic 7: Golden validation and cutover

- [x] **7.1** Run all active CR-093 golden entries and record per-category results.
      Verified 2026-09-08: the fixture runner now prints a per-category
      PASS/FAIL summary and supports `--category`. Both provider adapters pass
      21/21 with exactly one routed batch call each, and every category holds
      (no hidden aggregate masking):
      `clean_evidence_match 2/2`, `degree_gate 4/4`, `domain_gate 6/6`,
      `hedge_nongate 1/1`, `internal_term 2/2`, `preferred_nongate 2/2`,
      `tool_nongate 4/4` -- identical for Groq and Gemini. The four HARD
      domain/degree gates hold, and the three domain false-positive guards
      plus all four tool cases stay NONE.
- [x] **7.2** Add missing-ground-truth fixtures with expected pending behavior.
      Implemented the previously dead Layer C model tunnel: the cascade
      validator now honors `needs_user_confirmation`, `canonical_skill`, and
      `skill_kind` (bool coercion, strict skill_kind vocabulary, fail-closed
      rejection of a flag without a canonical skill so the provider chain
      falls back), and the fit gate creates the same durable
      `skill_presence` confirmation the deterministic extractor path creates
      for a model-flagged tool that the extractor missed, then pauses with
      hard-gate reviews in one `Stage0NeedsInput`. A `CONFIRMED_USE` answer
      caps presence evidence at level 1 and resume reuses the persisted
      checkpoint (no repeated provider call). Tests:
      `test_validator_passes_model_flagged_confirmation_through`,
      `test_validator_coerces_flag_variants_and_defaults_false`,
      `test_validator_rejects_flag_without_canonical_skill`,
      `test_flag_with_domain_skill_kind_is_not_a_tool_question`,
      `test_batch_falls_back_when_flag_lacks_canonical_skill`,
      `test_model_flagged_unknown_tool_creates_pending_and_pauses`.
- [ ] **7.3** Run a clean archive sample separate from JD extraction-confounded
      samples. Deferred with 7.4 -- needs a controlled replay harness and
      real provider runs (see increment A note above).
- [ ] **7.4** Compare baseline and cascade call counts, batch sizes, tokens,
      fallback counts, latency, score, gate, and pending rates. Deferred with
      7.3.
- [ ] **7.5** Run a controlled provider-backed Groq/Gemini sample.
- [ ] **7.6** Enable cascade by default only after the CR-108 release gate passes.
- [ ] **7.7** Remove the legacy per-line local classifier and temporary rollback
      flag after cutover.

### Hardening increment: validation, safety, and source promotion

- [x] **H1** Add a deterministic provider-adapter golden runner for Groq and
      Gemini response contracts, with an opt-in live mode that never logs keys or
      candidate contact text.
- [x] **H2** Add a shared provider-policy fixture and Python/TypeScript parity
      tests for provider order, local-only mode, and model defaults.
- [x] **H3** Add failure injection at every Stage 0 checkpoint boundary and assert
      retryability, durable spool behavior, and no duplicate completed judgments.
- [x] **H4** Add Review Center API integration tests using an injected isolated
      SQLite database and authenticated requests.
- [x] **H5** Add the durable verified-evidence source-update proposal boundary.
      An attestation remains non-authorable until `workExperience.md` contains
      the reviewed details and local verification marks the proposal applied.
- [x] **H6** Attribute and review generated Stage 0 rows before any cleanup.

### Epic 7 increment A -- golden per-category record (7.1) and model-flagged confirmation tunnel (7.2) -- 2026-09-08

**7.1 per-category golden record.** The fixture runner
(`test_stage0_provider_golden.py`) currently prints only an aggregate 21/21 for
Groq and Gemini. That hides a category-level collapse behind a healthy aggregate
-- the same failure the CR-093 checker's own docstring warns about. Add
`--category` filtering and a per-category PASS/FAIL summary to the fixture runner
(parallel shape to `check_fit_rubric_golden_set.py`), run it, and record the
per-category table in this doc below.

**7.2 missing-ground-truth pending fixtures -- the unimplemented model tunnel.**
CR-108's Layer C response schema defines `needs_user_confirmation`,
`canonical_skill`, and `skill_kind`, and the design says "If the extractor misses
an entity and the batch model identifies it, the model may return
needs_user_confirmation=true, which creates the same pending item." None of the
three fields is read anywhere in code (grep across scripts/ matches nothing), so a
model-detected tool that the conservative extractor missed currently scores as a
permanent anonymous gap with no durable question. The deterministic extractor
path is already covered by tests; this tunnel is the missing half. Decision:

- Validator: accept and normalize the three fields. `needs_user_confirmation`
  defaults false (bool coercion for true/false/1/0). `skill_kind` must be one of
  `tool|skill|domain|role|none`. Fail closed: when `needs_user_confirmation=true`
  and `canonical_skill` is empty, raise `CascadeValidationError` so the provider
  chain falls back to Gemini and a headline can never silently finalize as a
  permanent gap. `skill_kind=domain|role` with the flag is not a tool-presence
  question -- it scores normally (documented non-question case).
- Fit gate: after the cascade batch, for each result flagged with a canonical
  skill (`skill_kind` tool|skill), create/join the confirmation via
  `create_skill_confirmation` (idempotent per review_key + opportunity, same
  skill-memory reuse rules as the deterministic path), then pause with any
  hard-gate reviews in a single `Stage0NeedsInput` raise.
- Tests: validator pass-through + fail-closed rejection with provider fallback;
  end-to-end fit-gate test with the deterministic extractor stubbed to miss
  (patched `named_skill_candidates` returns []) and the provider response flagging
  the skill, asserting exactly one durable open pending confirmation and a
  `WAITING_FOR_INPUT` pause, then a `CONFIRMED_USE` answer and resume reusing the
  persisted checkpoint.

**7.3 / 7.4 remain deferred** with the same live-access dependency as 7.5/7.6: a
clean archive-sample replay harness and a baseline-vs-cascade cost/latency
comparison need real provider runs (or a controlled local-provider run) and are
tracked here, not silently dropped.

## Required verification commands

During implementation, the narrow checks must include:

```text
python -m unittest scripts.test_evidence_scale scripts.test_stage0_evidence_cascade -q
python -m unittest scripts.test_build_stage0_fit_gate scripts.test_workflow_authority -q
npx vitest run tests/unit/stage0EvidenceCascade.test.ts tests/unit/stage0Confirmations.test.ts
npx tsc --noEmit
```

Before the change is reported complete, run the repository-required:

```text
npm test
npm run build
```

The live provider-backed golden sweep is separate from the default offline test
run and must record provider/model configuration, call counts, and result hashes
without logging credentials or personal contact data. The offline adapter fixtures
currently pass 21/21 for both Groq and Gemini.

## Definition of done

- CR-093's gate-and-source accuracy bar is preserved or exceeded.
- No false HARD result is accepted from an ungrounded or low-confidence response.
- Unknown skills pause only the affected opportunity and produce a durable,
  deduplicated question.
- UI and harness resolve the same records.
- Resumes reuse all persisted completed work.
- User attestation cannot bypass the existing authoring truth contract.
- Settings accurately show provider/model behavior and user-owned cloud costs.
- Legacy removal and default cutover remain blocked on the CR-093 release gate.
  Documentation, registry, traceability, changelog updates, and hardening
  verification are complete for this increment.
