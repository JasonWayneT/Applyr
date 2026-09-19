# FIXQUEUE — Agy whole-workflow shakedown (2026-09-18)

Items 1-4 landed: YES
Runtime hold: NO

PLAN-2026-09-18 Task 3. Gemini and Groq free tiers are off. Agy is the only LLM path (`APPLYR_STAGE0_SUBSCRIPTION_ADAPTER=1` for Stage 0, Agy for Stage 1). Codex runs tests and does not edit code. Cursor fixes. Agy quota is the binding budget. Each fresh Agy call carries about 22k tokens of harness overhead.

CR-117 (years-range low-end) and CR-118 (false skips / people-gate negation / exact company match) already landed. Do not redo those. Do not edit `data/candidate_preferences.json`. Do not push.

A new session resumes at the first unchecked box. Finish each item fully (fix, tests pass, CHANGELOG line, checkbox note) before starting the next.

Before changing any script the worker uses, check `pipeline_queue` for `leased` or `in_progress` rows. If any exist, Codex is mid-pack: wait, or work on a non-runtime item.

GATE: when items 1-4 are checked, set the top line to `Items 1-4 landed: YES`. Codex resumes then.

---

## Queue

- [x] **1. Paused jobs stay paused until something changes.** Promote rules landed. `claim_pack` promotes at most remaining claim capacity. `WAITING_FOR_INPUT` without new input returns the last Stage 0 receipt.

- [x] **2. Inject every fixed part.** Header, education, role headings plus location, greeting, and sign-off always overwritten from `workExperience.md`. Author contract stripped in `_PREAMBLE` and digest §2/§4. Tests: fake institution, wrong Cision date, missing sign-off.

- [x] **3. Stage 1 evidence rules, cover letter shape, and repair loop.**
  - [x] **3a.** `[optimization_bar]` stays blocking. Resume still leads with strongest required-mapped claim per role.
  - [x] **3b.** `[evidence_utilization]` is a WARN plus `stage1_forwarded_findings.json`. Unused high-priority claims are not forced into the resume.
  - [x] **3c.** Cover letter = 1-2 stories covering several top requirements, in `_PREAMBLE` and digest §5. Rubric C2 untouched.
  - [x] **3d.** Repair loops until pass or no progress. Ranked findings. Snapshot in `stage1_author_output/` before verifier mutation. Skill updated.

- [x] **4. Stop throwing out good jobs.**
  - [x] **4a.** Cooldown NULL-date falls back to `applied_at`, then `created_at`. Omnissa 30d passes. Ulteig 120d still blocks.
  - [x] **4b.** AI/ML hard-skip is train / fine-tune / build models, or ML eng / DS background. SS&C-style deploy language passes. Digest regenerated (`2eae1d7894b79a1f`); rentana packet + prompt rebuilt.
  - [x] **4c.** People management: ESO coaching/mentoring does not skip. Direct-reports language still skips. CR-118 not redone.

- [ ] **5. Make Stage 0 screening reliable.**
  - [ ] **5a.** Keep partial answers. Cache returned items. Retry only missing IDs. Test: 8-item chunk that returns 6 re-asks only 2.
  - [ ] **5b.** Find why Agy omits item IDs using `data/eval/cr119_supervised/`. One session per job, never across jobs. Incomplete still fail-closed, never loop. Target: casper_studios evidence passes three runs in a row.

- [ ] **6. Re-run the wrong skips (after 4).** Back up the DB, delete these `stage0_skips` rows, re-queue via a new CSV in `data/inbox/csv/` pulled from archive by URL. Slugs: omnissa, optum, origami_risk, goodrx_product_manager, businessolver_product_manager_remote, cordance, binance_product_manager_social_features_content, eso (drop `eso_product_manager`), velera_product_manager_shared_branch, employers, ss_c_technologies. Cordance and Binance only need the ledger row cleared. Velera and Employers get a fresh Stage 0. Leave legitimate: Associate x3, Sartorius, Infojini, Urrly, Alinea, Imagine Learning, Salas O'Brien, Solace, Ulteig, Helix.

- [ ] **7. Company field polluted with titles.** Fix at ingest where CSV or bookmarklet appends the title.

- [x] **8. Trustworthy quota numbers.** Tracker copies Agy's final `result.usage` faithfully. `rentana_stage1_03` was 58 internal agent steps whose inputs sum to 419,638 (cache-read sum 4,154,618). A clean one-step author (`stage1-02`) was 38,961 input, 0 cache, 1 five-hour point. Cache-read did not move the five-hour window 1:1 with input. Size batches from five-hour drops (~1pp per clean author call, 3pp for a tool-loop). Tracker now logs `agent_steps` and `cache_read`.

- [ ] **9. Incoming from testing**, in the order Codex ranks it.

- [ ] **10. Stage 1 split (CR-117 plus RESEARCH-2026-09-18-stage1-authoring-shape.md).** Give CR-117 a free CR number first (ID collision). Build behind a switch: plan, code-check plan, write both docs, validate + 3d repair, generate `claim_provenance.json` from the plan. One fresh sandboxed Agy session per job. Don't change the default until it wins on frozen CR-117 cases.

---

## Incoming from testing

Ranked findings not already covered by items 1-8:

### P0 - Capture Agy quota for every stage, not only Stage 1 authoring

**Evidence:** Pack 1 captured before/after allowance for all four Stage 1 author
calls, but captured no allowance snapshots around Stage 0 extraction or evidence.
The adapter reported `api_cents=None`, which does not measure subscription usage.
Stage 2 did not run, so its quota is also unmeasured. The supervised run now
requires separate Stage 0 evidence, Stage 1 author, Stage 1 repair, and Stage 2
quota totals.

**Frequency:** Every Stage 0 call in pack 1 lacked before/after quota data.

**Suggested fix:** Wrap each Agy call site with one shared quota receipt helper.
Persist stage, slug, task, model, effort, cache status, prompt estimate, reported
usage, weekly/five-hour before and after, and wall time. Keep extraction and
evidence separable. A missing allowance snapshot should be explicit, not
silently represented as zero.

### P0 - Reject Agy `SUCCESS` when required author artifacts are empty or absent

**Evidence:** `cr119-rentana-stage1-01` returned top-level `SUCCESS` after a
denied `read_file` attempt, consumed 41,889 input and 1,856 output tokens, and
had an empty final response. Stream:
`data/eval/cr119_supervised/rentana_stage1_01/agy_stream.jsonl`.

**Suggested fix:** Author success requires nonempty `Resume.md`,
`CoverLetter.md`, and valid `claim_provenance.json`. Treat missing artifacts,
empty response, denied required action, or malformed fences as a failed author
call regardless of Agy's top-level status. The clean author workspace should
contain only `authoring_prompt.md`.

### P1 - Claiming a small pack mutates more paused rows than the claim size

**Evidence:** `_promotable_paused_slugs` promotes all eligible paused rows before
`claim_pack` applies `LIMIT`. During a `--size 1` Rentana validation run,
`casper_studios` changed from `paused` to `queued` without being claimed.

**Suggested fix:** Select and promote at most the remaining claim capacity in
the same transaction. Rows outside the claimed pack must remain unchanged.

### P1 - Stage 1 validation failures are lost from workflow and queue state

**Evidence:** Rentana produced three `stage1.validate` / `verify_failed` events,
but `workflow_state.json` and queue `last_workflow_status` remained
`WAITING_FOR_LLM`.

**Suggested fix:** Persist a structured Stage 1 repair-needed state with the
validation result path and attempt count. Map it to queue `paused`.

### P1 - Validation mutates failed drafts before the repair step can consume them

**Evidence:** `author_from_packet.run_verify_only` applied header repairs before
returning failure. Preserve immutable author-output artifacts before verifier
mutation.

### P2 - Stage 0 cache provenance is not available in the durable receipt

**Suggested fix:** Add non-sensitive receipt fields for extraction/evidence
cache hit, fresh call count, retry count, model/effort, and subscription minutes.

### P2 - Live quarantine-panel visibility remains untested

**Suggested fix:** Add Review Center startup and a visible quarantine-row check
to the next supervised preflight.
