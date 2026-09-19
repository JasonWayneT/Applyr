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
  - [ ] **9f.** P2 live quarantine-panel check stays a Codex preflight.

- [ ] **10. Stage 1 split (CR-120 reserved: `FR-348`–`FR-352`, `AC-451`–`AC-455`; docs renamed from colliding CR-117).** Build behind a switch: plan, code-check plan, write both docs, validate + 3d repair, generate `claim_provenance.json` from the plan. One fresh sandboxed Agy session per job. Don't change the default until it wins on frozen cases in `data/eval/cr117/`.

---

## Incoming from testing

Ranked findings not already covered by items 1-8:

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

**Evidence:** The first post-item-4b Rentana worker run printed three
`STALE: stage1` hash mismatches for `authoring_packet.json`,
`authoring_prompt.md`, and `authoring_prompt_meta.json` before validation.
Item 4b rebuilt those files; the Stage 1 receipt still reflected the old
versions. **How often:** 1/1 rebuilt-packet job tested. Later-stage impact
is unknown because validation failed.

**Suggested fix:** Have the orchestrator issue a matching Stage 1 receipt
when it rebuilds the packet/prompt, or make the rebuild path invalidate and
recreate the receipt before resume. Test Stage 2 transition after a rebuild.

### P1 - Validation mutates failed drafts before the repair step can consume them

Landed in item 3d. Verify snapshots author output into `stage1_author_output/`
before header injection.

### P2 - Stage 0 cache provenance is not available in the durable receipt

**Suggested fix:** Add non-sensitive receipt fields for extraction/evidence
cache hit, fresh call count, retry count, model/effort, and subscription minutes.

### P2 - Live quarantine-panel visibility remains untested

**Suggested fix:** Add Review Center startup and a visible quarantine-row check
to the next supervised preflight.
