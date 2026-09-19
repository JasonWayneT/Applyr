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

- [x] **5. Make Stage 0 screening reliable.**
  - [x] **5a.** Partial results are cached. Same chunk key re-asks only missing IDs (one retry, then fail-closed). Test: 8-item chunk returning 6 re-asks 2.
  - [x] **5b.** Live worker is already one-shot per chunk (no cross-job session). Omitted IDs: example `req-001` vs live `required:0:<hex>` plus uncached partials. Prompt now uses a live-shaped id. Replay/smoke extraction sessions are per job. Empty omissions do not retry. casper_studios 3/3 is Codex live.

- [x] **6. Re-run the wrong skips (after 4).** DB backup `data/archive/item6-pre-requeue-20260919T032035Z.sqlite`. Deleted 12 `stage0_skips` rows (including `eso_product_manager`). Re-queued 9 via new inbox CSV: omnissa, optum, origami_risk, goodrx, businessolver, eso, velera, employers, ss_c_technologies. Cordance and Binance ledger-only. `eso_product_manager` not queued.

- [x] **7. Company field polluted with titles.** Ingest strips a trailing/prefixed Position from Company (`ESO Product Manager` → `ESO`, slug `eso`). LinkedIn grab uses the first line of the company link. Title-only Company cells quarantine as EMPTY_COMPANY.

- [x] **8. Trustworthy quota numbers.** Tracker copies Agy's final `result.usage` faithfully. `rentana_stage1_03` was 58 internal agent steps whose inputs sum to 419,638 (cache-read sum 4,154,618). A clean one-step author (`stage1-02`) was 38,961 input, 0 cache, 1 five-hour point. Cache-read did not move the five-hour window 1:1 with input. Size batches from five-hour drops (~1pp per clean author call, 3pp for a tool-loop). Tracker now logs `agent_steps` and `cache_read`.

- [x] **9. Incoming from testing**, in the order Codex ranks it.
  - [x] **9a.** Ready paused jobs are claimed before queued backlog. Oldest `paused_at` first, up to pack size, then oldest queued. Promotion rules from item 1 unchanged.
  - [x] **9b.** Stage 0 Agy calls write quota receipts (`observability/agy_quota.jsonl`). Missing `/usage` snapshots are explicit, not zero.
  - [x] **9c.** Empty `Resume.md` / `CoverLetter.md` / invalid `claim_provenance.json` are not Stage 1 ready, even if Agy returned `SUCCESS`.
  - [x] **9b (pack 3).** Packet `hard_constraints` and digest self-check include total PM experience from `workExperience.md` §1.0 (7 / seven; never 4, 5, or 6). Not hardcoded.
  - [x] **9c (pack 3).** Deterministic pre-repair for mechanical findings (years, LR-014/LR-006/LR-015) before any Agy call. `scripts/stage1_prerepair.py` logs `auto_fixes` on `stage1_repair_state.json`. Tests: six years fixed with no Agy prompt; clean draft byte-identical.
  - [x] **9d (pack 3).** Small repair prompts: rule/file/line/offending text/suggestion, local context, relevant digest, mentioned excerpts. Rentana LR-013 case stays under 10KB.
  - [x] **9e (pack 3).** Stage 1 validation failure maps to `paused` with `last_workflow_status=FAILED`, lease released, never auto-promoted. Repair requeues explicitly.
  - [x] **9g.** Rebuilt packet/prompt refreshes the Stage 1 `WAITING_FOR_LLM` receipt hashes. Resume no longer prints `STALE: stage1` for a WAITING receipt.
  - [x] **9f (pack 4).** Stage 2 COMPLETE / Stage 3 READY maps to `paused` `ready_to_finalize`, lease released, Review Center panel count separate, never auto-promoted. `--finalize` maps to `done`.
  - [ ] **9g (pack 4).** Repair calls are single-shot sandboxed text in/out with a wall-time and event cap.
  - [ ] **9h (pack 4).** Requeue a FAILED repair only after valid artifacts are written.
  - [ ] **9f.** P2 live quarantine-panel check stays a Codex preflight.

- [ ] **10. Stage 1 split (CR-120 reserved: `FR-348`–`FR-352`, `AC-451`–`AC-455`; docs renamed from colliding CR-117).** Build behind a switch: plan, code-check plan, write both docs, validate + 3d repair, generate `claim_provenance.json` from the plan. One fresh sandboxed Agy session per job. Don't change the default until it wins on frozen cases in `data/eval/cr117/`.

---

## Incoming from testing

Ranked findings not already covered by items 1-8:

### P0 - Stage 2 complete remains leased in_progress instead of finalize-ready

**Evidence:** On pack 4 start commit
`63d7100095686c450136aad344d93ad22f5f3f77`, the worker completed
Rentana's Truth, ATS, HM, Mech, and Policy phases. Its output said
`Stage 2 COMPLETE` and `Stage 3 READY`; `workflow_state.json` has stage2
`COMPLETE`, stage3 `READY`, and top-level `IN_PROGRESS` at stage3. The worker
returned `claimed=1 results=ran`, but `pipeline_queue` stayed `in_progress`,
`last_workflow_status=IN_PROGRESS`, with a 20-minute lease. Both PDFs were
1 page and `verification_receipt.json` said `mechanically_verified=true`.
**How often:** 1/1 jobs reaching Stage 3 READY in this supervised run.

**Suggested fix:** Map the precise `(active_stage=stage3, stage2=COMPLETE,
stage3=READY)` state to a distinct `waiting_to_finalize` paused/terminal queue
status and release the lease. Do not infer completion from generic
`IN_PROGRESS`; other stages genuinely use it. Add a worker regression test
and make the Review Center panel display this as ready for Jason, not stuck.

### P1 - Compact repair prompt still triggers a long Agy tool loop

**Evidence:** HealthStream's first repair prompt was 8,022 bytes (7.83 KiB)
for three Stage 1 finding categories, below the 10 KiB target. A fresh
Gemini 3.8 Flash Medium session emitted 177 `step_update` events over more
than five minutes and wrote none of the three required files. The call was
interrupted under the agreed quota-burning stop rule. `agy_quota_tracker.py
after` failed closed on the truncated stream, so final model usage is
unavailable; account allowance snapshots moved from 67%/89% to 65%/84%
(weekly/five-hour), which may include concurrent work. Stream preserved at
`data/eval/cr119_supervised/healthstream_repair01_interrupted_stream.jsonl`.
**How often:** 1/1 compact repair call tested; no usable output.

**Suggested fix:** Put a hard wall-time/internal-step budget on isolated
repair calls and fail when required artifacts are absent. Disable tool and
slash-command exploration for prompt-only repairs. Record an interrupted
call's allowance delta separately even without a final Agy result event.

### P1 - Repair builder requeues before repaired files exist

**Evidence:** HealthStream failed Stage 1 and correctly paused at `FAILED`
with no lease. `build_stage1_repair_prompt.py` wrote the 7.83 KiB prompt and
immediately changed the row to `queued`. The following Agy repair was
interrupted without output, leaving the row queued with the old failed
draft files and `last_workflow_status=FAILED`. A worker claim now would
repeat validation without any changed content. **How often:** 1/1 live
repair-builder invocation with failed external authoring.

**Suggested fix:** Keep `FAILED` paused while only a repair prompt exists.
Promote only when complete, changed Stage 1 artifacts are present, or add a
distinct repair-pending queue status that the worker cannot claim.

### P2 - Coverage finding IDs collide across claim variants

**Evidence:** Rentana Truth emitted two distinct coverage WARNs for
`ACC-110-LEADERSHIP` and `ACC-110-OPS`, both with the id
`truth.coverage.unused.ACC-110`. `dispositions.json` therefore has one slot
for two findings; one disposition silently settles both. **How often:** 2
findings sharing 1 ID in the first Stage 2 Truth review.

**Suggested fix:** Use the full claim ID in each finding ID and test
multiple variants under one project ID. Preserve separate dispositions.

### P0 - Ready paused jobs starve behind any queued backlog

Landed in item 9a. `claim_pack` now leases promotable paused rows first
(oldest `paused_at`), up to pack size, then fills from the oldest queued
rows. Change-detection rules from item 1 are unchanged.

### P0 - Capture Agy quota for every stage, not only Stage 1 authoring

Landed in item 9b. Stage 0 extraction/evidence/retry/cache-hit calls emit
`observability/agy_quota.jsonl`. Missing allowance snapshots are `missing`
with a reason, never zero. Stage 1 author/repair still use
`agy_quota_tracker.py before/after`. Stage 2 has no Agy call site yet.

### P0 - Reject Agy `SUCCESS` when required author artifacts are empty or absent

Landed in item 9c. `check_stage1_ready` and runner `_docs_present` reject empty
resume/cover letter bodies and empty/invalid `claim_provenance.json`. Those
jobs stay `WAITING_FOR_LLM`.

### P1 - Claiming a small pack mutates more paused rows than the claim size

Landed in item 9a. Extra paused rows stay paused.

### P1 - Stage 1 validation failures are lost from workflow and queue state

Landed in item 9e. Stage 1 verify/ready failure writes workflow `FAILED`.
The worker maps that to `paused` and releases the lease. `FAILED` never
auto-promotes. `build_stage1_repair_prompt.py` requeues the paused row
when it writes a prompt or auto-fixes.

### P1 - A one-finding Gemini repair can burn quota without progress

Landed in items 9b–9d. Years figure is in the packet. Mechanical findings
auto-fix before Agy. Remaining repair prompts are compact (rule/line/
offending/suggestion + local context), under 10KB for Rentana LR-013.

### P1 - Rebuilt Stage 1 packet leaves old receipt hashes stale

Landed in item 9g. A WAITING_FOR_LLM Stage 1 receipt is rewritten to match
the current packet/prompt hashes before reconcile. COMPLETE receipts still
go STALE if those files change after validation.

### P1 - Validation mutates failed drafts before the repair step can consume them

Landed in item 3d. Verify snapshots author output into `stage1_author_output/`
before header injection.

### P2 - Stage 0 cache provenance is not available in the durable receipt

**Suggested fix:** Add non-sensitive receipt fields for extraction/evidence
cache hit, fresh call count, retry count, model/effort, and subscription minutes.

### P2 - Live quarantine-panel visibility remains untested

**Suggested fix:** Add Review Center startup and a visible quarantine-row check
to the next supervised preflight.
