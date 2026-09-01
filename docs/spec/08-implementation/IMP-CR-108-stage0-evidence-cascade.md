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

- [ ] **7.1** Run all active CR-093 golden entries and record per-category results.
- [ ] **7.2** Add missing-ground-truth fixtures with expected pending behavior.
- [ ] **7.3** Run a clean archive sample separate from JD extraction-confounded
      samples.
- [ ] **7.4** Compare baseline and cascade call counts, batch sizes, tokens,
      fallback counts, latency, score, gate, and pending rates.
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
