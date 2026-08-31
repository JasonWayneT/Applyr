# Observability & Batch Reporting Design — Stage 0-3 Replay

**Status: discovery/design only. No production code changed. Not yet approved.**

Written to answer: as we replay `data/submissions/*` through Stages 0-3 one at a time, how do we
know whether each stage did its job, catch recurring problems, and compare runs objectively
instead of by memory? This document traces the actual pipeline code (not filenames) to ground
every proposed metric in a real, cited source. Terms are defined on first use.

---

## 0. Executive summary (read this first)

Three real observability assets already exist and this design **extends them, does not replace
them**:

1. **`data/submissions/{slug}/stage1_first_draft/verify_history.json`** — an append-only log of
   every Stage 1 verify-only attempt, with pass/fail, rule violations, and
   `rule_digest_version`/`example_bank_version` (prompt/config version tracking). Written by
   `author_from_packet.py`'s `run_verify_only` (CR-097 Story 1.2).
2. **`data/authoring_defect_ledger.json`** + `scripts/scan_authoring_defects.py`** — a
   cross-submission ledger of Stage 1 *and* Stage 2 findings by rule/category, with a
   promote/decline review workflow (CR-097). Gitignored (local only).
3. **`stage_receipts/stage{0,1,2,3}.json`** — one receipt per stage, written by the single
   function `scripts/workflow/receipts.py::build_receipt`, hash-chained via `prior_receipt_id`.
   This is proof-of-completion, not a metrics record (see §7 on why we keep it that way).

What's missing, and what this design adds: **duration** (no stage receipt has one — see §4.1 for
why this is trickier than it sounds), **Stage 0 and Stage 3 coverage** (the existing ledger only
covers Stage 1/2), **disposition-type breakdown** (dispositions are a bare enum today, no reasoning
text), **causal attribution** (a Stage 2 finding is currently recorded as a Stage 2 event even when
Stage 1 caused it), and **a single per-opportunity report** that reads across all of the above so
you don't have to open six JSON files to understand one submission's run.

---

## 1. Current-state observability map

### What exists, where, and what it can tell us today

| Artifact | Location | Written by | What it tells us | What it cannot tell us |
|---|---|---|---|---|
| `stage_receipts/stage{0,1,2,3}.json` | per submission | `receipts.py::build_receipt`, called from each `run_stageN` in `runner.py` | Stage ran, status (COMPLETE/FAILED/SKIPPED/NEEDS_DISPOSITION), a single `issued_at` timestamp, input/output file hashes, a thin `result` block (varies per stage — see §2) | Duration (only one timestamp per receipt). Any per-attempt history (a receipt is overwritten on retry, per its own hash-chain contract). |
| `workflow_state.json` | per submission | `receipts.py::write_state` / `commit_stage` | Current stage/subphase status, receipt IDs, `integrity` (CLEAN/OVERRIDDEN) | History — this file is *mutated*, not appended. A submission that failed Stage 2 twice before passing shows no trace of the first failure once it passes. |
| `stage0_fit_gate.json` | per submission | `build_stage0_fit_gate.py::build_stage0_fit_gate` | `tier`, `decision`, `fit_score`, `confidence_score`, `extraction_source` (`nlp`\|`llm`\|`deterministic`), `thin_jd`, `flagged_gaps` | Whether the confidence score is *warranted* — it's the model's own self-report, not validated against outcomes (see §2, Stage 0 quality). |
| `reviews/{truth,ats,hm,mech}_findings.json` | per submission | `runner.py::collect_{truth,ats,hm,mech}_findings` | Every finding this run, with `id`, `source`, `severity` (BLOCK/WARN), `message` | Aggregate counts across submissions (each file is single-submission, single-attempt — overwritten on re-run). |
| `reviews/dispositions.json` | per submission | `runner.py::sync_dispositions_for_phase` (write), agent (edits) | Which findings were dispositioned and to which of 5 enum values | **Why** — there is no reasoning/note field in the schema, only `{finding_id: enum_value}`. |
| `reviews/policy_findings.json` | per submission | `runner.py::run_stage2_policy` | Why `check_stage2_ready` blocked (usually missing `rubric_score`) | — |
| `stage1_first_draft/verify_history.json` | per submission | `author_from_packet.py::run_verify_only` | Every verify attempt (not just the last), pass/fail, violations by rule_id, prompt/rule-bank version, timestamp | Cost/latency of the LLM call that produced each attempt (the draft itself is generated **outside this codebase** — see §2 Stage 1). |
| `data/authoring_defect_ledger.json` | repo-root, gitignored | `scripts/scan_authoring_defects.py` (via `runner.py`'s `_run_advisory_defect_scan`, called after Stage 2 COMPLETE) | Cross-submission occurrence counts by rule/category for Stage 1 *and* Stage 2 findings; a promote/decline review queue | Stage 0 or Stage 3 defects (out of scope by design — see `_stage1_occurrences`/`_stage2_occurrences` in that file). Timing. Disposition types. |
| `draft_manifest.json` | per submission | `author_from_packet.py` (claim IDs etc.) + **hand-entered** `rubric_score` | The one real quality number the pipeline has (R1-R8/C1-C5 rubric total) | Whether the hand-entered score is honest — `AGENTS.md` already documents a known gaming risk (`verify_submission.py --audit` catches byte-identical scores across different JDs) |
| `verification_receipt.json` | per submission | `verify_submission.py::verify_one` | `mechanically_verified`, `lint_all_clean`, `page_counts_ok` | Quality beyond mechanical rules |
| `build_stage0_fit_gate.py::batch_report` | function, not a file | Stage 0 module | A Tier1/Tier2/Skip Markdown table **for JDs not yet processed** (pre-authoring triage) | Anything about Stages 1-3. This is a different tool for a different job (deciding what to pursue), not pipeline health. Do not confuse it with what this design builds. |
| `activity_log` SQLite table | `data/jobagent.sqlite` | `logActivity()` (Node) / today's `_log_provider_notification` (Python, CR-106) | Real-time provider rate-limit/cascade events, Gmail sync events | Nothing about the submission-authoring pipeline — this table is App/Gmail/LLM-provider scoped, not `run_submission.py`-scoped. |

### Important gaps (the actual list this design has to close)

1. **No duration anywhere.** Every receipt has exactly one timestamp (`issued_at`, stamped when
   the receipt is written — i.e. *after* the stage's work is done). Confirmed by reading
   `receipts.py::build_receipt` (line ~57): `issued_at` defaults to `utc_now()` called at
   construction time, and `build_receipt` is only ever invoked at the *end* of each
   `run_stageN` function in `runner.py` (e.g. `run_stage0` calls
   `build_stage0_fit_gate(...)` first, *then* builds the receipt at line ~240). **A receipt-only
   fix cannot produce duration** — the start time has to be captured inside each `run_stageN`
   wrapper, before the real work begins, and threaded through as a value, not inferred from the
   receipt file itself. This directly answers the constraint in the request: yes, adding a field
   to `build_receipt` alone is not sufficient.
2. **No cross-run history for Stage 2/3** the way Stage 1 has `verify_history.json`. A
   `reviews/truth_findings.json` from attempt 1 is gone once attempt 2 overwrites it.
3. **No causal attribution.** A Stage 2 `truth.coverage.unused.ACC-101` finding is recorded as a
   Stage 2 event. Whether the *root cause* was Stage 1 (picked the wrong claims) or is a Stage
   2-native concern (Truth's own coverage heuristic being noisy) is not recorded anywhere.
4. **No LLM cost/token/latency instrumentation anywhere.** Confirmed: `scripts/utils.py::call_llm`
   and its `_call_{groq,gemini,claude,perplexity,local}` helpers return only text (`Optional[str]`)
   or, on the Node side, `{text, rateLimited}` — no `usage` field is parsed from any provider
   response today, even though Groq/Claude/Gemini all return token counts in their raw JSON. This
   is **derivable with new instrumentation**, not currently available.
5. **Stage 1's real "authoring" step is invisible by design, not by oversight.** Per
   `CLAUDE.md`/`AGENTS.md`: "Stage 1 authoring still uses `authoring_prompt.md` only (digest plus
   packet)" — the default flow has a human/agent paste `authoring_prompt.md` into a **separate,
   fresh LLM session**, outside `run_submission.py`'s process. `scripts/build_authoring_packet.py`
   (the file that runs *inside* the pipeline for Stage 1) contains zero `call_llm` calls — verified
   by grep. So "Stage 1 LLM latency/provider/cost" is not a gap to close; it is **structurally
   unmeasurable from inside this codebase** for the default path. What *is* measurable and useful
   is wall-clock elapsed time between the `WAITING_FOR_LLM` receipt and the Stage 1 COMPLETE
   receipt — that's real, but it's "time including whatever the external agent session took," not
   "LLM latency." Naming this correctly in the report avoids a misleading metric.
6. **Disposition reasoning is not captured.** `reviews/dispositions.json`'s schema is
   `{finding_id: enum}` — verified against the real file (`data/submissions/exterro/reviews/dispositions.json`).
   There is no free-text field. Any "why was this accepted" analysis requires reading the actual
   disposition choice plus, for `RESOLVED_EDIT`, a diff of the document — not a report field.
7. **The rubric score (the only real quality number) is hand-entered**, per `AGENTS.md`: "The
   rubric score itself still cannot be mechanized." Trending it over time is trending a
   human-entered number with a documented gaming risk, not a measured system output. Treat it as a
   quality *proxy* with a known integrity caveat, never as ground truth.

---

## 2. Stage intent and health model

Terms used below, defined once:
- **Completion** — the stage ran end-to-end and produced its output artifact(s), with no crash.
- **Validity** — the artifact satisfies its schema/contract (what `scripts/contracts.py`'s
  `check_stageN_ready` functions check) — the next stage *can* read it, structurally.
- **Quality** — the artifact actually serves the stage's real purpose (a valid-but-wrong fit
  decision is still invalid *for our purposes*, even though it satisfies the schema).
- **Downstream utility** — did the next stage get what it needed without extra rework?
- **Efficiency** — time, retries, provider calls, tokens (where measurable).

A stage is not "healthy" just because it didn't throw — this section exists specifically to keep
completion and quality from being conflated in the metrics that follow.

### Stage 0 — Fit Gate

**Code**: `scripts/build_stage0_fit_gate.py::build_stage0_fit_gate`, invoked from
`scripts/workflow/runner.py::run_stage0`, gated by `scripts/workflow/policy.py::evaluate_stage0`,
contract checked by `scripts/contracts.py::check_stage0_fit_gate`.

- **Intended job**: decide PASS (Tier 1/Tier 2) or SKIP for one JD, using deterministic hard gates
  plus an evidence-scale judgment per required/preferred requirement line.
- **Inputs**: `Original_JD.txt`, `data/candidate_preferences.json`, `data/workExperience.md`
  (retrieval), `data/master_claims_tags_only.json`.
- **Required output**: `stage0_fit_gate.json` with (per `check_stage0_fit_gate`'s own docstring)
  required list, preferred list, responsibilities list, flagged gaps, stage signal, thin-JD flag —
  not just the tier/decision.
- **Completion**: the file exists and `check_stage0_fit_gate` returns `ok=True`.
- **Validity**: same as completion here — the contract check *is* the schema check.
- **Quality**: the tier/decision is actually right — a JD correctly identified as Tier 2 with the
  real soft gaps named, not a plausible-looking gate that happens to land on the right tier for
  the wrong reason.
- **Downstream utility**: Stage 1 gets a packet with real, evidence-backed `claim_constraints` and
  soft-gap mappings it can actually author from — not a shallow required-list that under-specifies
  what the JD actually needs.
- **Important failure modes**:
  - `Stage0ExtractError` — hard extraction failure, no output at all.
  - `EvidenceClassificationError` (from `evidence_scale.py`) — the per-requirement evidence-scale
    judgment is **hard-locked to a local Ollama model by design** (`llm_stages.py`'s
    `_HARD_PROVIDER_STAGES = {"rewrite", "evidence_scale"}` — raises rather than substituting a
    cloud provider). A local-model outage here is a **different failure class** than a cloud
    provider rate-limit — it stops Stage 0 entirely, with no fallback, on purpose.
  - `extraction_source == "llm"` — the free NLP path (TF-IDF/LogReg, per CR-105) missed and fell
    through to an LLM call for section extraction. A high rate here across a batch is itself a
    signal the NLP model needs retraining, independent of any single run's correctness.
  - A hard gate false-positive (see PRODUCT_CAPABILITIES.md's own history: "a real miss (a JD
    auto-rejected sight-unseen over one Tableau mention)").
- **Downstream consequence of underperformance**: Stage 1 authors from an incomplete or
  wrong-shaped packet; Stage 2's `ats.jd_terms.missing.*` findings will look like Stage 1's fault
  when the actual cause was Stage 0 mis-extracting the JD's terms.
- **Signals that already exist**: `fit_score`, `confidence_score`, `extraction_source`, `tier`,
  `decision`, `thin_jd`, `flagged_gaps` (all in `stage0_fit_gate.json`, confirmed against a real
  submission).
- **Signals missing**: duration; whether `confidence_score` is *warranted* (no historical
  calibration check exists); a record of which hard gate fired when one does (currently only in
  `policy.evaluate_stage0`'s `reasons` list, written into the receipt's `result.reasons` but not
  structured by gate name); local-model-unavailable as a distinct, countable event.

### Stage 1 — Authoring

**Code**: `scripts/build_authoring_packet.py` (packet build, zero LLM calls — verified by grep),
`scripts/workflow/runner.py::run_stage1_prompt` (build + stop at `WAITING_FOR_LLM`),
[external, untracked: a human/agent pastes `authoring_prompt.md` into a fresh LLM session and
saves `Resume.md`/`CoverLetter.md`], `scripts/author_from_packet.py::run_verify_only` (mechanical
post-author gate), `scripts/workflow/runner.py::run_stage1_validate` (writes Stage 1 COMPLETE).

- **Intended job**: turn the Stage 0 packet into a Resume/CoverLetter that cites real evidence for
  every claim and covers what the packet says the JD needs.
- **Inputs**: `authoring_packet.json` (evidence map, WE excerpts, `claim_constraints`),
  `authoring_prompt.md` (digest + packet).
- **Required output**: `Resume.md`, `CoverLetter.md`, `claim_provenance.json` (every bullet/proof
  point cites a real Fact ID).
- **Completion**: the two docs exist (`_docs_present`) — this is checked as a precondition to even
  attempt validate, so "the LLM never wrote anything back" is a **distinguishable, named
  precondition failure**, not silently indistinguishable from "wrote something bad."
- **Validity**: `check_stage1_ready` passes — packet status ready + docs present. Structural only.
- **Quality**: `run_verify_only`'s real check — no `HARD_BLOCK` lint violations, ground-truth
  coverage clean (WARN-tier judgment), JD-term gaps addressed. This is where "did it pick good
  claims and write them well" gets its first automated check.
- **Downstream utility**: how much Stage 2 finds wrong that Stage 1 should have caught — this is
  the causal-attribution question (§6).
- **Important failure modes**:
  - Docs never appear (external authoring session never produced them, or produced them in the
    wrong location).
  - `run_verify_only` FAIL → a fix-repair cycle, capped by the docstring's own stated protocol at
    "Maximum 2 fix rounds before escalating to Jason" — **already-documented policy this design
    should just measure compliance with**, not invent.
  - A recurring `LR-xxx`/`LW-xxx` rule violation across submissions — this is exactly what
    `authoring_defect_ledger.json` already tracks for Stage 1.
- **Downstream consequence**: an under-verified draft reaching Stage 2 means Truth/ATS/HM findings
  that are really "Stage 1 didn't do its job," inflating Stage 2's apparent noise.
- **Signals that already exist**: the entire `verify_history.json` — attempt number, pass/fail,
  rule violations by ID, `rule_digest_version`, `example_bank_version`, timestamp per attempt. This
  is genuinely good, already-built instrumentation.
- **Signals missing**: elapsed wall-clock between `WAITING_FOR_LLM` and Stage 1 COMPLETE (available
  by diffing two receipts' `issued_at`, not currently computed anywhere); which specific claims
  from the packet were actually used vs. available (packet has `claim_constraints`,
  `claim_provenance.json` has what was used — a join nobody currently performs); real
  provider/token/cost data (structurally unavailable for the default flow, see §1 gap 5).

### Stage 2 — Review & Disposition

**Code**: four independent, **entirely mechanical** collectors —
`runner.py::collect_truth_findings` (claim-provenance + ground-truth-coverage checks),
`collect_ats_findings` (JD-term-gap check), `collect_hm_findings` (submission_linter +
one hardcoded "confirm a human read happened" finding — **not an LLM-graded qualitative read**,
verified by reading the function: it appends a static reminder finding, nothing else), and
`collect_mech_findings` (PDF compile + `verify_submission.py::verify_one` + rubric-presence check).
Each subphase's verdict comes from `policy.py::evaluate_truth_findings` (reused for all four
phases by `_apply_subphase_verdict` — same function, different findings input) against
`reviews/dispositions.json`. Stage 2 COMPLETE is minted by `run_stage2_policy` once all four
subphases are COMPLETE and `contracts.py::check_stage2_ready` passes (mainly: is a real
`rubric_score` present).

- **Intended job**: catch truth/ATS/HM/mechanical defects Stage 1 (or Stage 0, via ATS term gaps)
  left behind, force a real decision on each one, and gate finalization on a passing state.
- **Inputs**: `Resume.md`, `CoverLetter.md`, `claim_provenance.json`.
- **Required output**: four findings files, `dispositions.json` fully resolved for BLOCK findings
  (only `RESOLVED_EDIT`/`HUMAN_ACCEPTED_RISK` clear a BLOCK — `policy.py` line ~129), a rubric
  score in `draft_manifest.json`, compiled PDFs, `verification_receipt.json`.
- **Completion**: all four subphases reach `COMPLETE`.
- **Validity**: `check_stage2_ready` passes.
- **Quality**: findings are *real* defects, not noise, and get resolved rather than rubber-stamped
  — this is where disposition-type breakdown matters (a subphase that's 100%
  `ACCEPTED_AS_CORRECT` every time is either genuinely clean or a reviewer that never says no; a
  subphase heavy on `RESOLVED_EDIT` is genuinely catching things Stage 1 missed).
- **Downstream utility**: did Stage 3 finalize cleanly, or need an override (a real quality
  signal — an override means "we let this ship with a known gap").
- **Important failure modes**:
  - `FAIL` verdict (a `BLOCK`-severity finding with no valid disposition) — this genuinely stops
    the pipeline, correctly.
  - `NEEDS_DISPOSITION` (renamed from `WAITING_FOR_HUMAN` this session, CR-107) sitting unresolved
    across a session boundary — the exact anti-pattern CR-107 targeted. This design should make
    that measurable (§6), not just hope the rename fixed it.
  - `policy_findings.json`'s block: almost always a missing `rubric_score` — i.e. the *contract*
    is fine but the *human step* (rubric scoring) hasn't happened yet. Worth distinguishing from a
    real content defect.
- **Downstream consequence**: an unresolved or falsely-cleared finding here ships as a real
  document defect Jason discovers later, or worse, a hiring manager discovers.
- **Signals that already exist**: findings by `severity`/`source`/`id` per subphase, per run
  (overwritten each attempt); dispositions by enum value; `authoring_defect_ledger.json`'s
  cross-submission occurrence counts (Stage 1 + Stage 2 combined, by rule/category).
- **Signals missing**: disposition-type distribution over time; time-to-disposition; whether a
  disposed finding actually got fixed (a `RESOLVED_EDIT` disposition doesn't verify the edit
  happened — it's an agent's self-report); duplicate/conflicting findings across subphases (e.g.
  Truth and ATS both flagging the same underlying gap); causal source (Stage 0/1/2) per finding.

### Stage 3 — Finalization

**Code**: `runner.py::run_stage3_finalize`, wrapping the existing `finalize_submission_job`
worker, gated by `contracts.py::check_finalize_ready`.

- **Intended job**: write the approved submission into the real jobs DB exactly once, with a
  receipt chain that `check_workflow_complete` can verify end-to-end.
- **Inputs**: Stage 2 COMPLETE receipt, `stage0_fit_gate.json` (for company/title), a fresh
  `verification_receipt.json`.
- **Required output**: a DB row (production mode) or an explicit skip (practice mode), Stage 3
  receipt, terminal `workflow_state.json` status (`COMPLETE`/`COMPLETE_WITH_OVERRIDE`/
  `PRACTICE_COMPLETE`).
- **Completion**: `finalize_submission_job` returns without raising.
- **Validity**: `check_finalize_ready` passes — a fresh, passing verification receipt AND
  `draft_manifest.json.verification_passed`.
- **Quality**: the DB row is *correct* (right company/title/URL) and the integrity is CLEAN, not
  OVERRIDDEN — an override-assisted finalize is a real quality signal, not a formality (this
  design should never quietly average it away — see §5's stance against a single health score).
- **Important failure modes**: implausible job title guard rejecting a real title (a false
  positive, worth tracking separately from a true catch); a stale Stage 2 output hash forcing a
  re-verify.
- **Downstream consequence**: a wrong DB write is discovered much later, disconnected from the
  run that caused it, unless the receipt chain is intact.
- **Signals that already exist**: `company`, `title`, `reach_out`, the finalize message, whether
  `integrity == OVERRIDDEN`.
- **Signals missing**: end-to-end duration (Stage 0 start → Stage 3 finish); override rate over
  time and its reasons (today: the override exists in the state, but *why* it was needed isn't
  captured beyond whatever free text the disposition that caused it happened to contain).

---

## 3. Metric catalog

Grouped by stage, MVP first within each stage. Each metric specifies every field the design brief
asked for; fields are labeled inline rather than as table columns because the full field set does
not fit a readable table (15 columns).

Legend for **Type**: Health = did it complete/is it valid; Quality = did it do its job well;
Diagnostic = helps explain *why*; Guardrail = should trigger attention past a threshold; Efficiency
= time/resource cost.

### Stage 0

---
**M0.1 — Decision distribution** · *MVP*
- Question: What share of replayed JDs pass, and at which tier?
- Why: The single highest-level Stage 0 health signal; a batch that's 100% Skip or 100% Tier 1
  during a replay (where the original run already decided) is itself informative.
- Formula: count(`decision`) grouped by `decision`×`tier`, as % of batch.
- Denominator: number of opportunities in the batch.
- Source: `stage0_fit_gate.json.decision`, `.tier`. **Available now.**
- Unit: count and %. Scope: batch (trivially per-run too).
- Type: Health. Direction: n/a (a distribution, not a score).
- Threshold: baseline first — no defensible threshold without replay history.
- Limitations: says nothing about whether the decision was *right*, only what it was.

---
**M0.2 — Extraction fallback rate** · *MVP*
- Question: How often did the free NLP extractor miss, forcing an LLM call?
- Why: Per CR-105, this is a direct signal the NLP model needs more training data; also a cost
  signal (LLM calls aren't free the way NLP inference is).
- Formula: count(`extraction_source == "llm"`) / count(all runs).
- Source: `stage0_fit_gate.json.extraction_source`. **Available now.**
- Unit: %. Scope: batch (also meaningful trended per-run over time).
- Type: Diagnostic + Efficiency. Direction: lower is better.
- Threshold: baseline first. CR-105's own audit found the *old* rule-based classifier missing
  ~41% of cases in a different context (email), which is not directly transferable evidence for
  this rate — do not reuse that number here.
- Limitations: a low fallback rate could mean the NLP model got better, or that the JD mix in this
  batch happened to be easy. Needs the input-characteristics cut (M0.7) to disambiguate.

---
**M0.3 — Hard-gate trigger reasons** · *MVP*
- Question: When Stage 0 skips, why?
- Why: A Skip pile that's 80% one gate (e.g. seniority mismatch) versus one that's evenly spread
  across gates implies different things about whether the gate itself is well-tuned.
- Formula: count grouped by the specific gate/reason string in `policy.evaluate_stage0`'s
  `reasons` list.
- Source: `stage_receipts/stage0.json.result.reasons`. **Available now**, but currently free text,
  not a structured code — **derivable now** with a small addition: have `policy.evaluate_stage0`
  tag each reason with a stable gate identifier (it already knows which check produced it).
- Unit: count. Scope: batch.
- Type: Diagnostic. Direction: n/a.
- Threshold: none proposed — this is for pattern-spotting, not alerting.
- Limitations: free-text reasons that are *almost* identical but not byte-identical (a company
  name interpolated into the string) will fragment counts until the reason is tagged with a gate
  ID, not just grouped by raw string.

---
**M0.4 — Confidence vs. later-stage outcome** · *Next*
- Question: Is Stage 0's self-reported `confidence_score` actually predictive of anything?
- Why: An LLM's stated confidence is not ground truth (explicit constraint in the design brief) —
  this metric exists specifically to check whether it's *worth trusting at all*, not to trust it
  by default.
- Formula: for opportunities where Stage 2/3 outcome is known, compare `confidence_score` buckets
  against downstream rework rate (M2.x) or Stage 3 override rate (M3.2).
- Source: `stage0_fit_gate.json.confidence_score` joined against later-stage metrics across the
  same slug. **Derivable now** once a per-opportunity join exists (§4); needs enough opportunities
  to be meaningful — do not compute this on fewer than ~15-20 opportunities.
- Unit: correlation/bucketed rate, not a single number.
- Type: Diagnostic. Direction: n/a.
- Threshold: none — small-sample warning applies directly here.
- Limitations: correlation, not causation, and the brief explicitly forbids claiming causation
  from it. Report it as "confidence bucket X had rework rate Y," never as "confidence predicts
  quality."

---
**M0.5 — Stage 0 duration** · *MVP, requires new instrumentation*
- Question: How long does Stage 0 actually take, and is local-model load a bottleneck?
- Why: `build_stage0_fit_gate` does real work (NLP inference, possibly an LLM fallback call, a
  per-requirement local-model call via `evidence_scale.py`) — duration tells you where time goes
  as you replay a batch.
- Formula: `stage1_prompt_start_time − stage0_start_time` per run (see §4.1 for where to capture
  `stage0_start_time`).
- Source: **requires new instrumentation** — capture `time.time()` at the top of
  `runner.py::run_stage0`, store in the receipt's `result`.
- Unit: seconds. Scope: per-run and batch (p50/p95).
- Type: Efficiency. Direction: lower is better, but not at the cost of quality (do not let this
  metric alone justify skipping the LLM fallback, for example).
- Threshold: baseline first.
- Limitations: includes local-model VRAM load time if the model wasn't already resident
  (`_prepare_stage0_score_model`) — a "slow" run right after a cold start is not comparable to a
  warm one without also recording whether the model was already loaded.

---
**M0.6 — Local-evidence-model failure rate** · *Next, requires new instrumentation*
- Question: How often does the hard-locked local evidence classifier (`evidence_scale.py`) fail
  outright (no fallback exists, by design)?
- Why: This is a structurally different failure than an LLM cascade — it stops Stage 0 cold. Worth
  distinguishing from every other failure type.
- Formula: count(`EvidenceClassificationError` raised) / count(Stage 0 attempts).
- Source: **requires new instrumentation** — this exception is currently caught (if at all) by
  whatever calls `classify_requirement`; verify it surfaces to a countable event rather than a bare
  crash.
- Unit: %. Scope: batch.
- Type: Guardrail. Direction: lower is better.
- Threshold: any non-zero rate on a healthy local Ollama setup is worth investigating immediately
  — this is closer to an infra-health signal than a pipeline-quality one.
- Limitations: conflates "model genuinely can't answer" with "Ollama wasn't running" — the error
  message distinguishes these but a raw count doesn't; keep the message in the record, not just
  the count.

---
**M0.7 — Input characteristics** · *Next*
- Question: Does JD length, `thin_jd` flag, or requirement count correlate with any Stage 0-3
  outcome?
- Why: Needed to disambiguate M0.2 and M0.4 — "this batch behaved differently" is not useful
  without knowing whether the *inputs* were different.
- Formula: not a single metric — a set of input tags (JD char count, `thin_jd`, required-item
  count) attached to every per-opportunity record so later analysis can cut by them.
- Source: `stage0_fit_gate.json` already has `thin_jd`; JD char count is trivially derivable from
  `Original_JD.txt`. **Available now / trivially derivable.**
- Scope: per-run, joined at batch-report time.
- Type: Diagnostic.
- Limitations: none of these are metrics on their own — they're covariates for interpreting
  everything else, and the report should present them as such, not as findings in themselves.

### Stage 1

---
**M1.1 — Verify-only pass rate (first attempt vs. eventual)** · *MVP*
- Question: How often does a draft pass verify on the first try, and how often does it eventually
  pass at all?
- Why: This is the single clearest Stage 1 quality signal that already has data behind it.
- Formula: (a) count(`attempt == 1 and passed == true`) / count(opportunities); (b)
  count(any attempt `passed == true`) / count(opportunities).
- Source: `stage1_first_draft/verify_history.json`. **Available now.**
- Unit: %. Scope: per-run (trivial pass/fail) and batch (rate).
- Type: Quality. Direction: higher is better for both.
- Threshold: baseline first.
- Limitations: "eventually passes" says nothing about how many manual fix rounds it took — see
  M1.2.

---
**M1.2 — Fix-round count** · *MVP*
- Question: How many verify attempts did it take, and does that exceed the documented 2-round
  escalation policy?
- Why: `run_verify_only`'s own docstring states "Maximum 2 fix rounds before escalating to Jason"
  — this metric measures compliance with an existing, already-agreed policy, not a new invented
  threshold.
- Formula: `len(verify_history) - 1` per opportunity (attempts beyond the first).
- Source: `stage1_first_draft/verify_history.json`. **Available now.**
- Unit: count. Scope: per-run and batch (distribution).
- Type: Guardrail. Direction: lower is better.
- Threshold: **derived from existing policy, not invented**: >2 fix rounds is already
  out-of-policy per the docstring.
- Limitations: a high round count could mean Stage 1 authored badly, or that the packet Stage 0
  handed it was hard to work with — attribute using M1.4 before concluding it's a Stage 1 problem.

---
**M1.3 — Recurring rule violations** · *MVP (already built)*
- Question: Which `LR-xxx`/`LW-xxx` rules recur across submissions?
- Why: Exactly what `authoring_defect_ledger.json` + `scan_authoring_defects.py::format_report`
  already answer. **This design's job is to surface it in the per-opportunity/batch report, not
  rebuild it.**
- Source: `data/authoring_defect_ledger.json`. **Available now.**
- Scope: batch (that's what the existing tool already does).
- Type: Diagnostic.
- Limitations: covers Stage 1 + Stage 2 only (by the existing tool's own design) — Stage 0/3
  defects need this design's new instrumentation.

---
**M1.4 — Wall-clock time-to-draft** · *MVP, requires new instrumentation (a join, not new capture)*
- Question: How long between Stage 0 PASS and a validated draft?
- Why: This is real elapsed time, useful for planning a replay session, but must **not** be
  labeled "LLM latency" — see §1 gap 5. It includes whatever the external authoring session took.
- Formula: `stage1_complete.issued_at − waiting_for_llm_receipt.issued_at` (or, if no intermediate
  receipt is retained, `stage1_complete.issued_at − stage0_complete.issued_at`).
- Source: existing receipt timestamps, joined. **Derivable now** — no new capture needed, just a
  join two receipts don't currently get.
- Unit: minutes/hours. Scope: per-run and batch.
- Type: Efficiency. Direction: n/a — this is descriptive, not something to optimize blindly (a
  fast draft that fails verify twice is worse than a slower one that passes first try — always
  report this alongside M1.1/M1.2, never alone).
- Limitations: **explicitly not a proxy for LLM performance.** Name it "time-to-draft," never
  "authoring latency," in any report.

---
**M1.5 — Provenance coverage** · *Next*
- Question: What % of resume bullets / cover-letter proof points cite a real, non-disabled Fact ID?
- Why: Direct measure of the truth-grounding discipline `claim_provenance.py` (CR-075) exists to
  enforce.
- Formula: count(bullets/sentences with ≥1 valid citation) / count(all bullets/sentences requiring
  one).
- Source: `claim_provenance.json` findings, already generated at compose time for submissions
  authored after CR-075. **Available now** for recent submissions; older folders "correctly report
  the file missing" per `AGENTS.md` — expect incomplete historical coverage.
- Unit: %. Scope: per-run and batch.
- Type: Quality. Direction: higher is better.
- Threshold: baseline first.
- Limitations: a citation existing doesn't mean it's used *honestly* (a technically-valid but
  weak citation would still count) — this is a coverage metric, not a truthfulness metric.

---
**M1.6 — Ground-truth utilization** · *Next*
- Question: Of the strongest available evidence for JD-relevant gaps, how much actually got used?
- Why: Directly implements `AGENTS.md`'s own stated bar: "'Done' is not 'clears the number.' Done
  is: every required JD item and every Stage 0 soft gap... is engaged with the single strongest
  available piece of ground truth for it." This metric measures exactly that bar, which the
  project has already articulated but never scored.
- Formula: 1 − (count(`jd_relevant_claims_possibly_unused`) / count(mapped soft-gap + required
  claim IDs in the packet)).
- Source: `ground_truth_coverage.json` (`check_ground_truth_coverage.py`'s output), joined against
  `authoring_packet.json`'s `claim_constraints`. **Derivable now**, with the caveat the source tool
  is explicitly documented as heuristic with real false positives ("check each ATTENTION flag
  against the actual document").
- Unit: %. Scope: per-run and batch.
- Type: Quality. Direction: higher is better, **but not blindly** — the same doc explicitly warns
  against padding to raise this number.
- Limitations: false positives are expected and documented by the source tool itself; do not
  auto-flag a submission as bad purely on this number without a human glance.

### Stage 2

---
**M2.1 — Findings by severity, per subphase** · *MVP*
- Question: How much did each of Truth/ATS/HM/Mech actually find, and at what severity?
- Why: Raw finding counts alone are the exact "vanity metric" the brief warns against — cutting by
  severity and subphase is what makes it useful. A subphase with lots of WARN and zero BLOCK is a
  very different signal from the reverse.
- Formula: count grouped by (`phase`, `severity`).
- Source: `reviews/{truth,ats,hm,mech}_findings.json`. **Available now** per-run; **requires new
  instrumentation to retain across runs** (currently overwritten each attempt — see §4.2).
- Unit: count. Scope: per-run and batch.
- Type: Health + Diagnostic.
- Limitations: counts alone don't say whether findings were true defects or accepted as fine —
  pair with M2.2.

---
**M2.2 — Disposition-type distribution** · *MVP, requires new instrumentation to retain (data exists per-run)*
- Question: Of all findings disposed, how many were real fixes (`RESOLVED_EDIT`) vs.
  accepted/dismissed?
- Why: Directly requested in the brief ("How many findings were true defects versus
  accepted-as-correct"). A phase that's ~100% `ACCEPTED_AS_CORRECT` is either genuinely clean
  input or a rubber-stamping pattern — this number alone can't tell you which (see limitations),
  but it's the first place to look.
- Formula: count grouped by disposition enum value, per phase.
- Source: `reviews/dispositions.json`. **Available now** per-run; batch aggregation requires
  retaining a copy per run (§4.2), since this file too is overwritten.
- Unit: count and %. Scope: per-run and batch.
- Type: Quality + Diagnostic.
- Threshold: baseline first — do not assume a "healthy" ratio without replay evidence.
- Limitations: **cannot verify a `RESOLVED_EDIT` actually resolved anything** — the disposition is
  an agent's self-report, not a re-check. A genuinely robust version of this metric would re-run
  the same check after the edit and confirm the finding is gone (worth doing — see Implementation
  Plan Next phase) — until then, treat the count as "claimed resolutions," not "verified fixes."

---
**M2.3 — Time-to-disposition** · *MVP, requires new instrumentation*
- Question: Once a subphase lands at `NEEDS_DISPOSITION`, how long until it's resolved and
  `--resume`d?
- Why: This is the direct, measurable test of whether CR-107's rename actually changed behavior —
  "resolve and retry immediately" is now a testable claim, not just a rule in `AGENTS.md`.
- Formula: `resume_timestamp − needs_disposition_timestamp`.
- Source: **requires new instrumentation** — `workflow_state.json` is mutated in place, so the
  moment a subphase *entered* `NEEDS_DISPOSITION` is lost once it clears. Needs an append to a
  per-opportunity event log (§4) at the point `_apply_subphase_verdict`/`run_stage2_truth` sets
  that status, and again when it clears.
- Unit: seconds/minutes. Scope: per-run and batch.
- Type: Guardrail. Direction: lower is better; **near-zero is the expected value** if CR-107 is
  working (same-session resolution).
- Threshold: anything spanning a session boundary (practically: minutes to hours, not seconds) is
  exactly the anti-pattern CR-107 was written to prevent — flag it, don't just average it.
- Limitations: "session boundary" isn't directly observable from timestamps alone; a >5 minute
  gap is a reasonable proxy but is a judgment call, not a measured fact — label it as such in
  reports.

---
**M2.4 — Duplicate/cross-subphase findings** · *Next*
- Question: Do Truth and ATS (or others) flag the same underlying gap independently?
- Why: Directly requested ("duplicates or conflicting across reviewers"); also a real
  reviewer-noise signal — findings that always co-occur might mean one collector's check is
  redundant with another's.
- Formula: not a ratio — a report section listing findings from different phases whose `detail`
  fields reference the same claim/project ID within one run.
- Source: `reviews/*_findings.json`'s `detail.project_id`/`detail.claim_id` fields, joined
  within a run. **Derivable now.**
- Scope: per-run (surfaced), batch (frequency of the pattern).
- Type: Diagnostic.
- Limitations: this is pattern-matching on `detail` field shape, which differs by collector —
  expect to special-case truth/ats's shared `project_id` field rather than a fully generic join.

---
**M2.5 — Root-stage attribution** · *Next — the causal-attribution deliverable, see §6*
- Question: Of Stage 2's findings, how many are genuinely Stage 2's own concern vs. attributable
  to Stage 0 or Stage 1?
- Why: Directly required by the brief: "Reports must not automatically count every Stage 2 finding
  as a Stage 2 failure." This is the single metric most likely to change how you read every other
  Stage 2 number.
- Formula: count grouped by an `attributed_stage` tag (see the defect taxonomy in §6) rather than
  the collecting phase.
- Source: **requires new instrumentation and a judgment call at disposition time** — see §6 for the
  proposed mechanism (a lightweight tag added alongside the disposition, not a new heavy process).
- Type: Diagnostic. Scope: batch.
- Limitations: attribution is inherently a judgment call, not a mechanical fact — report it as
  "attributed," never "proven," and expect disagreement at the margins.

### Stage 3

---
**M3.1 — Finalize completion rate** · *MVP*
- Question: Of opportunities reaching Stage 2 COMPLETE, how many finalize cleanly?
- Formula: count(Stage 3 COMPLETE*) / count(Stage 2 COMPLETE).
- Source: `stage_receipts/stage3.json`. **Available now.**
- Unit: %. Scope: batch. Type: Health. Direction: higher is better.
- Threshold: baseline first.
- Limitations: none significant — this is a clean, well-defined completion metric.

---
**M3.2 — Override rate and reasons** · *MVP*
- Question: How often does finalize require `COMPLETE_WITH_OVERRIDE`, and why?
- Why: Directly requested ("Why was each override needed") and explicitly flagged as a real
  quality signal, not a formality, in §2's Stage 3 model.
- Formula: count(`integrity == OVERRIDDEN`) / count(all Stage 3 completions); reasons grouped from
  whichever disposition(s) actually caused the override (`HUMAN_ACCEPTED_RISK` entries).
- Source: `workflow_state.json.stages.stage3.integrity` (rate, available now) joined against
  `reviews/dispositions.json` entries with value `HUMAN_ACCEPTED_RISK` (reasons — available now,
  but again with no free-text "why," only which finding IDs were overridden).
- Unit: %. Scope: batch. Type: Quality + Guardrail. Direction: lower is better.
- Threshold: baseline first.
- Limitations: "reasons" here means "which finding IDs," not narrative reasoning — same
  disposition-schema limitation as M2.2.

---
**M3.3 — End-to-end duration** · *MVP, requires new instrumentation (join)*
- Question: Stage 0 start to Stage 3 finish, and where did the time actually go?
- Formula: sum of per-stage durations (M0.5, inferred Stage 1/2 durations once instrumented) —
  **not** a single black-box number; always reported as a breakdown.
- Source: derived from per-stage start/end timestamps once §4.1's instrumentation lands.
- Unit: hours. Scope: per-run and batch. Type: Efficiency.
- Limitations: for the historical submissions being replayed, the *original* run's timing spans
  real calendar days (waiting on Jason, external sessions) — not comparable to a tight, back-to-back
  replay. Always label which kind of duration a number represents.

---

## 4. Proposed event and record model

### 4.1 Where "start time" must actually be captured

Confirmed by tracing `runner.py`: `build_receipt` (in `receipts.py`) is called *once*, at the end
of each `run_stageN` function, after the real work (`build_stage0_fit_gate(...)`,
`collect_truth_findings(...)`, etc.) has already run. It has no way to know when that work began.
**The fix is at the call site, not the receipt builder**: capture `started_at = utc_now()` as the
first line of each `run_stageN`/`collect_*_findings` function, and pass `duration_seconds` into
`build_receipt`'s `result` dict once the work returns. This touches ~8 functions in `runner.py`
(`run_stage0`, `run_stage1_prompt`, `run_stage1_validate`, `run_stage2_truth`, `run_stage2_ats`,
`run_stage2_hm`, `run_stage2_mech`/`collect_mech_findings`, `run_stage2_policy`,
`run_stage3_finalize`) — small, mechanical, and testable one function at a time.

### 4.2 Should receipts carry this data, or should observability live separately?

**Recommendation: keep receipts as proof-of-completion; add a parallel, append-only observability
record.** Reasoning:
- Receipts are hash-chained and part of `check_workflow_complete`'s trust contract — every field
  added to `result` is a field a future receipt-format change has to stay compatible with, or
  `check_workflow_complete` and every test asserting on receipt shape breaks. Today's `result`
  blocks are already stage-specific and thin *on purpose*.
- Receipts are **overwritten on retry** by design (the hash-chain reflects the *current* state,
  not history). Observability explicitly needs history (every attempt, not just the last).
- These are different contracts: receipts answer "is this stage's current output trustworthy,"
  observability answers "how did we get here and how is the pipeline doing over time." Blurring
  them risks both: receipts become unstable, and observability can't retain history without
  fighting the overwrite-on-retry behavior.

Proposal: one new append-only file per opportunity,
`data/submissions/{slug}/observability/run_events.jsonl` (JSON Lines — one event object per line,
trivially append-only, trivially greppable, no read-modify-write race). Each stage-runner function
appends one event on start and one on completion/failure. This is the same pattern
`verify_history.json` already proved out for Stage 1 — this design generalizes it to all four
stages rather than inventing a new shape.

**Example event record** (illustrative, real field names drawn from what's actually available):

```json
{"schema_version": 1, "run_id": "run_2026-08-30T21:03:11Z_7f3a", "slug": "exterro", "stage": "stage0", "event": "start", "timestamp": "2026-08-30T21:03:11Z", "workflow_version": "8aa43e4"}
{"schema_version": 1, "run_id": "run_2026-08-30T21:03:11Z_7f3a", "slug": "exterro", "stage": "stage0", "event": "complete", "timestamp": "2026-08-30T21:03:17Z", "duration_seconds": 6.1, "outcome": "PASS", "tier": "Tier 2", "fit_score": 52, "confidence_score": 95, "extraction_source": "llm"}
{"schema_version": 1, "run_id": "run_2026-08-30T21:03:11Z_7f3a", "slug": "exterro", "stage": "stage2.truth", "event": "needs_disposition", "timestamp": "2026-08-30T21:04:02Z", "open_finding_ids": ["truth.coverage.unused.ACC-101"]}
{"schema_version": 1, "run_id": "run_2026-08-30T21:03:11Z_7f3a", "slug": "exterro", "stage": "stage2.truth", "event": "resolved", "timestamp": "2026-08-30T21:04:19Z", "resolution_seconds": 17}
```

**`run_id`**: generated once per `run_submission.py` invocation (timestamp + short random suffix),
threaded through every event that invocation produces — this is what lets a batch report group
events by "one replay attempt" even across multiple `--resume` calls for the same opportunity.

**Schema versioning**: the existing convention (`"schema_version": 1` on every findings/receipt
file) is reused, not reinvented. A future breaking change bumps this field; readers check it.

**Reruns don't overwrite evidence**: because this is JSONL and append-only, a second full replay
of the same opportunity just appends more lines with a new `run_id` — old evidence is never lost,
and "compare original run vs. replay" (question 7 in the brief) becomes a filter on `run_id`
against the same `slug`, not a diff of overwritten files.

### 4.3 Retention and naming

- Location: `data/submissions/{slug}/observability/run_events.jsonl` — lives with the
  submission, travels with it if the folder archives, is gitignored the same way the rest of
  `data/` is (this is operational data, not code).
- No retention deletion proposed at MVP — these are small text files; a naming/rotation policy is
  a **Later** concern only if volume ever becomes real (hundreds of opportunities × many replay
  passes).
- Naming: `run_id = f"run_{utc_now_compact()}_{secrets.token_hex(2)}"` — sortable by time, unique
  enough for a single-operator local tool (collision risk is not a real concern at this scale).

---

## 5. Reporting specification

### 5.1 Immediate run summary (console, during a run)

Compact, one line per stage-completion event, printed by `run_submission.py` right where it
already prints status today (it already prints receipt status — this adds the metrics, not a new
print call site):

```
Stage 0  PASS   tier=Tier 2  fit=52  confidence=95  via=llm      6.1s
Stage 1  READY  packet built, prompt written -> WAITING_FOR_LLM  0.4s
        [paste authoring_prompt.md into a fresh session; re-run --resume when Resume.md/CoverLetter.md exist]
Stage 1  COMPLETE  verify: pass on attempt 2/2 (1 fix round)     2h 28m since WAITING_FOR_LLM
Stage 2  truth   COMPLETE  0 BLOCK, 8 WARN (8 accepted)          1.2s
Stage 2  ats     COMPLETE  0 BLOCK, 2 WARN (2 accepted)          0.6s
Stage 2  hm      NEEDS_DISPOSITION  1 WARN (LW-032, company bleed) -> see reviews/hm_findings.json
Stage 2  hm      COMPLETE  1 WARN (1 accepted, resolved in 4m)   0.3s
Stage 2  mech    COMPLETE  mechanically_verified=true, pages ok  3.4s
Stage 2  policy  COMPLETE  rubric present (resume 78, cover 71)  0.1s
Stage 3  COMPLETE  integrity=CLEAN                                0.2s
--- exterro: COMPLETE end-to-end (excl. external authoring wait) in 10.7s ---
Full record: data/submissions/exterro/observability/run_events.jsonl
```

Not flooded with raw findings text (that stays in the existing findings files) — just result,
key signal, duration, and where to look for detail.

### 5.2 Per-opportunity report

**Format: Markdown, one file, human-readable, linking out to the real JSON artifacts rather than
duplicating them.**

**Path**: `data/submissions/{slug}/observability/report.md`, regenerated (overwritten — this one
*is* meant to reflect current state, unlike the append-only event log) each time the opportunity
reaches a terminal state or is explicitly asked for.

**Generation command** (proposed): `python scripts/observability_report.py {slug}` — reads
`run_events.jsonl` + the existing artifacts (receipts, findings, dispositions, verify_history,
stage0_fit_gate) for that one slug, writes `report.md`.

Outline, with a realistic worked example using the real `exterro` submission:

```markdown
# Observability Report — exterro

Forensics Product Manager · replayed 2026-08-30 · workflow @ 8aa43e4
Compared against original run: 2026-08-28 → 2026-08-30 (see "Comparison" below)

## Stage-by-stage outcome

| Stage | Result | Duration | Retries/Fallbacks | Notes |
|---|---|---|---|---|
| 0 Fit Gate | PASS · Tier 2 | 6.1s | extraction fell back to LLM | fit=52, confidence=95 |
| 1 Authoring | COMPLETE | 6.1s mechanical + 2h28m external | 1 fix round (LW-009-PAIR) | see verify_history.json |
| 2 Truth | COMPLETE | 1.2s | 8 findings, all accepted | ACC-101 etc. — coverage-unused, judged fine |
| 2 ATS | COMPLETE | 0.6s | 2 findings, all accepted | Governance/Legal terms judged not applicable |
| 2 HM | COMPLETE | 0.3s (+4m to disposition) | 1 WARN, resolved | LW-032 company-name bleed, fixed |
| 2 Mech | COMPLETE | 3.4s | — | mechanically_verified, pages OK |
| 2 Policy | COMPLETE | 0.1s | — | rubric: resume 78, cover 71 |
| 3 Finalize | COMPLETE | 0.2s | — | integrity CLEAN, no override |

## Decisions and evidence
- Stage 0: Tier 2 on "soft gap(s) — Domain Expertise... Technical Aptitude..." (stage0_fit_gate.json)
- Stage 2 Truth: 8 WARN, all ACCEPTED_AS_CORRECT — [reviews/truth_findings.json](../reviews/truth_findings.json)

## Warnings, failures, retries, fallbacks, overrides
- Stage 0 used the LLM extraction fallback (not the free NLP path).
- Stage 1 needed one fix round (rule LW-009-PAIR) before verify passed.
- No BLOCK findings anywhere in this run. No override.

## Defects introduced / detected / corrected / escaped
(See §6 taxonomy) — none tagged as escaped in this run.

## End-to-end timeline
2026-08-28 20:43 Stage 0 start → 20:44 Stage 0 PASS → [WAITING_FOR_LLM] → 23:20 Stage 1 COMPLETE
→ 2026-08-30 20:21 Stage 2 COMPLETE → 20:21 Stage 3 COMPLETE.

## Comparison to earlier run
First run for this opportunity under the new observability instrumentation — no prior
`run_events.jsonl` to compare. (For a genuine replay-vs-original comparison, see §6.)

## Needs manual inspection
- None flagged this run.

## Artifacts
- [stage0_fit_gate.json](../stage0_fit_gate.json) · [verify_history.json](../stage1_first_draft/verify_history.json)
- [truth](../reviews/truth_findings.json) · [ats](../reviews/ats_findings.json) · [hm](../reviews/hm_findings.json) · [mech](../reviews/mech_findings.json)
- [dispositions.json](../reviews/dispositions.json) · [workflow_state.json](../workflow_state.json)
```

### 5.3 Batch report

**Format: Markdown (human-readable) backed by a machine-readable CSV/JSON sidecar** — not HTML,
not a dashboard. Reasoning: this is a single local operator reading a report after a replay
session, not a shared multi-viewer artifact; Markdown renders fine in an editor/terminal, and a
sidecar CSV makes "did metric X change" answerable by a spreadsheet pivot without re-parsing
Markdown. A dashboard is explicitly not justified yet per the brief's own instruction ("not
required unless it provides material value beyond reports") — revisit only if batch size or
comparison frequency grows enough that re-reading Markdown becomes the bottleneck.

**Path**: `data/reports/observability/batch_{batch_id}.md` +
`data/reports/observability/batch_{batch_id}.csv` (one CSV row per opportunity, one column per
per-opportunity metric — the raw data behind every rate/percentage in the `.md`).

**Generation command** (proposed): `python scripts/observability_batch_report.py --slugs
exterro,harnham,amphenol_rf ...` or `--all-submissions`, `--since <date>` for filtering; `--batch-id`
optional (defaults to a timestamp) so a specific replay batch can be named and re-referenced (e.g.
`--batch-id pre-cr107-baseline`).

Outline:

```markdown
# Batch Report — pre-cr107-baseline (2026-08-30, 14 opportunities)
Workflow @ 8aa43e4 · included: allcares_3af2ed54, alphasense, ... (14 total)

## Completion & failure rates by stage
| Stage | COMPLETE | FAILED | SKIPPED | NEEDS_DISPOSITION (unresolved) |
|---|---|---|---|---|
| 0 | 12 (86%) | 0 | 2 (14%) | — |
| 1 | 11 | 1 | — | — |
| 2 | 10 | 0 | — | 1 |
| 3 | 10 | 0 | — | — |

⚠ Small sample: 14 opportunities is not enough to treat any single-digit percentage as
statistically stable — read these as directional, not conclusive.

## Timing (p50 / p95)
| Stage | p50 | p95 |
|---|---|---|
| 0 | 5.8s | 11.2s |
| 1 (mechanical only) | 0.5s | 1.1s |
| 1 (WAITING_FOR_LLM elapsed — NOT LLM latency) | 1h 40m | 6h 20m |
| 2 (all subphases) | 6.1s | 14.3s |
| 3 | 0.2s | 0.4s |

## Retry / fallback / override rates
- Stage 0 LLM-extraction-fallback rate: 4/14 (29%)
- Stage 1 fix-round rate (>0 rounds): 6/14 (43%); >2 rounds (out of policy): 1/14
- Stage 3 override rate: 1/14 (7%) — reason: HUMAN_ACCEPTED_RISK on hm.lint.warn.* (see slug: X)

## Findings by severity / rule / phase (facts, from reviews/*_findings.json across the batch)
[table by phase × severity, and top 5 recurring rule_ids from authoring_defect_ledger.json]

## Most common recurring problems (interpretation, not raw fact)
- LR-015 (forbidden punctuation) recurred in 4/14 cover letters — pre-existing pattern per
  authoring_defect_ledger.json, not new to this batch.

## Outliers
- `bcforward_59f881fa`: Stage 1 needed 3 fix rounds (exceeds documented 2-round policy).

## Data-quality / instrumentation warnings
- 3/14 opportunities predate CR-075's claim_provenance.json — provenance-coverage metric (M1.5)
  unavailable for those.

## Before/after comparison
(Only populated when `--compare-to <earlier batch_id>` is passed — see §6.)

## Evidence-backed improvement candidates
- [Hypothesis, not fact] Stage 0's LLM-fallback rate (29%) may indicate the NLP extractor
  under-trained on JDs shaped like these 4 — needs the specific JD shapes checked before
  concluding anything.

## Suggested next investigations
- Re-run this same batch after any Stage 0 NLP retrain and compare `batch_id`s.

## Cautions
- This is the first instrumented batch — no historical baseline exists yet for any threshold
  claimed above. Treat every number here as the baseline being established, not a judgment.
```

---

## 6. Baseline, comparison, and causal attribution

### Establishing a baseline

The first full Stage 0-3 replay of the existing `data/submissions/*` folders (once §4/§7's MVP
instrumentation lands) **is** the baseline. Tag that batch report with an explicit `--batch-id`
(e.g. `baseline-2026-08-3x`) and do not treat any single number in it as a threshold — it exists to
be compared *against*, not to be judged in isolation (this directly implements the brief's "baseline
first" instruction and the small-sample-size caution).

### Comparing a later change

Every batch report records `workflow_version` (git short SHA at generation time — trivially
available via `git rev-parse --short HEAD`) alongside the batch. A `--compare-to <batch_id>`
flag on the batch report generator reads two CSV sidecars and produces a diff section covering,
per the brief's exact list: per-metric before/after, defects fixed, new regressions, findings that
moved to a different stage (via the `attributed_stage` tag — see below), and cost/duration/effort
deltas — explicitly **not** collapsed into one score. If quality metrics improved but a duration
metric got worse (or vice versa), both rows are shown side by side; the report does not decide
which one "wins."

**No composite health score is proposed.** The brief is explicit that a single score can hide
real tradeoffs, and this pipeline's own history already shows why: a fast Stage 0 that skips the
LLM fallback might score better on M0.5 (duration) while quietly regressing M0.2 (fallback rate,
which exists precisely because the fallback catches real misses). A composite would need weights
someone has to defend, and none are defensible yet with zero baseline data.

### Causal attribution — a minimal defect taxonomy

The brief specifically warns against every Stage 2 finding being counted as a Stage 2 failure, and
against over-complicating attribution. Proposal: **one additional field, `attributed_stage`**, set
at disposition time (alongside the existing enum, not replacing it), with exactly four values:

- `stage0` — the finding traces to a Stage 0 extraction/scoring gap (e.g. a real JD requirement
  Stage 0 never surfaced into the packet at all).
- `stage1` — Stage 1 had what it needed and used it badly, missed it, or overclaimed.
- `stage2` — the finding is Stage 2's own collector being noisy/wrong (a real false positive in
  `check_ground_truth_coverage.py`, for instance).
- `unknown` — genuinely can't tell without deeper investigation; **this is a valid, expected
  answer**, not a failure to fill in the field. Forcing a guess would be worse than an honest
  "unknown."

This is a judgment call made once, by whoever is already disposing the finding (no new review
step) — it just captures a decision that's currently being made implicitly (an agent already
decides whether to fix Stage 1's output or dispose Stage 2's finding as noise) and writes it down
instead of losing it. Stored alongside the disposition:

```json
{
  "by_finding_id": {
    "truth.coverage.unused.ACC-101": {"disposition": "ACCEPTED_AS_CORRECT", "attributed_stage": "stage2"}
  }
}
```

This is a schema change to `dispositions.json` (currently a bare string per finding_id) — flagged
explicitly in §7's migration section, since existing tooling (`policy.py::evaluate_truth_findings`)
reads `by_id.get(fid)` expecting a string. The migration must keep reading a bare string as
"disposition value, `attributed_stage: unknown`" so existing dispositions files don't break.

**"First introduced / first detectable / actually detected / corrected / escaped"** (the brief's
five-point lifecycle): only the last three are mechanically observable today (detected = a finding
exists; corrected = disposition is `RESOLVED_EDIT` and, per M2.2's own limitation, unverified as
actually fixed; escaped = shipped to Stage 3 with an open BLOCK is structurally impossible today
since the policy gate prevents it — so "escaped" in practice means "shipped as an
`ACCEPTED_AS_CORRECT`/`HUMAN_ACCEPTED_RISK` WARN that a human later regrets," which can only be
identified by *comparing a later human observation back to this record*, not automatically).
"First introduced" and "first detectable" require knowing which stage *could have* caught
something before it actually did — that's exactly what `attributed_stage` approximates, not a
separate, more precise timestamped concept. Do not build more than this for MVP; it would be
inventing precision the underlying process doesn't actually have yet.

---

## 7. Implementation plan

Constraint carried through every phase: **preserve existing receipt/findings/disposition contracts
unless explicitly noted as a schema change with a migration path.**

### Epic A — Duration instrumentation (MVP)
- **A1**: Capture `started_at`/`duration_seconds` in `run_stage0`. Add to receipt `result`
  (additive field, no contract break). Test: assert `duration_seconds` present and `>0` on a real
  run; existing `test_workflow_authority.py` assertions on `result` keys must not need loosening
  (additive fields don't break `==` comparisons only if those tests use subset checks — verify and
  fix any exact-dict-equality assertions first).
- **A2**: Same for `run_stage1_prompt` / `run_stage1_validate` (two numbers: packet-build time,
  verify time — never a combined "Stage 1 time" that hides the external-wait problem from §1).
- **A3**: Same for each of the four Stage 2 collectors + `run_stage2_policy`.
- **A4**: Same for `run_stage3_finalize`.
- Files: `scripts/workflow/runner.py` only (every `run_stageN` function), no changes to
  `receipts.py`'s function signature needed beyond accepting the already-generic `result` dict it
  takes today.
- Acceptance: a fresh `run_submission.py` invocation on one real submission shows non-zero
  `duration_seconds` in every stage receipt's `result`; full existing test suite green
  (`run_all_tests.py`).

### Epic B — Append-only event log (MVP)
- **B1**: `scripts/workflow/observability.py` (new file) — `append_event(folder, event: dict)`,
  writes one JSON line to `observability/run_events.jsonl`, creates the directory if missing.
  Small, single-purpose, easy to unit test in isolation (write N events, read back N lines).
- **B2**: Wire `append_event` calls into the same `run_stageN` functions touched in Epic A — one
  `start` event, one `complete`/`failed`/`needs_disposition`/`resolved` event per call, carrying
  the stage-specific fields from §3's metric catalog (fit_score, extraction_source, finding
  counts, disposition counts, etc.) plus `run_id`.
- **B3**: `run_id` generation — one per `run_submission.py` process invocation, passed down through
  `state` (a natural, already-threaded-through parameter) rather than regenerated per stage.
- Files: new `scripts/workflow/observability.py`; edits to `runner.py` (same functions as Epic A)
  and `run_submission.py` (generate + thread `run_id`).
- Acceptance: replaying one real submission produces a `run_events.jsonl` with a `start`/`complete`
  pair per stage reached, correctly ordered, all sharing one `run_id`.
- Tests: unit tests for `append_event` (isolated, temp dir); one integration-style test replaying
  a small fixture submission through Stage 0 only and asserting the expected two events exist.

### Epic C — Per-opportunity report (MVP)
- **C1**: `scripts/observability_report.py {slug}` — reads `run_events.jsonl` + existing artifacts
  for one slug, renders `observability/report.md` per §5.2's outline.
- Files: new script only; no changes to existing pipeline code.
- Acceptance: running it on `exterro` (a real, already-complete submission — works even before any
  events exist, degrading gracefully to "no run_events.jsonl found, showing receipt-only view") produces
  a readable report matching §5.2's structure.
- Tests: run against 2-3 real submission folders in different states (COMPLETE, one with an
  unresolved `NEEDS_DISPOSITION`, one Stage 0 SKIP) and confirm it doesn't crash and renders the
  right sections for each state.

### Epic D — Console summary (MVP)
- **D1**: Extend the existing per-stage print statements in `run_submission.py` (it already prints
  status after each phase) to include the §5.1 one-liner, pulling from the same data Epic A/B
  already compute — no new computation, just formatting at an existing print site.
- Files: `scripts/run_submission.py` only.
- Acceptance: a real `run_submission.py` invocation's console output matches §5.1's shape.

### Epic E — Batch report (MVP, depends on B+C)
- **E1**: `scripts/observability_batch_report.py` — accepts `--slugs`/`--all-submissions`/`--since`,
  reads each slug's `run_events.jsonl` + artifacts, writes `data/reports/observability/batch_{id}.md`
  + `.csv`.
- **E2**: `--compare-to <batch_id>` diff mode (§6).
- Files: new script; `data/reports/observability/` is a new gitignored directory (operational
  output, like `data/` generally).
- Acceptance: running against the real submissions already in `data/submissions/` (even with zero
  historical `run_events.jsonl` — degrade to receipt/findings-only aggregation) produces a report
  matching §5.3's structure; small-sample warning renders when batch size <20.
- Tests: run against the full real `data/submissions/` directory once and manually review the
  output for plausibility (this is inherently a reporting tool — the meaningful test is "does the
  output make sense against known-real data," not just unit-level assertions).

### Epic F — Disposition attribution schema (Next, not MVP)
- **F1**: Extend `dispositions.json`'s schema to `{finding_id: {disposition, attributed_stage}}`,
  with backward-compatible reads (a bare string still means `attributed_stage: unknown`).
- Files: `scripts/workflow/policy.py` (`evaluate_truth_findings`'s `by_id.get(fid)` read path),
  `scripts/workflow/runner.py` (`sync_dispositions_for_phase`), any script that writes
  dispositions directly.
- **Migration**: existing `dispositions.json` files across all current submissions remain valid as
  read (backward-compat parsing); no bulk rewrite required, though a one-time migration script
  that adds `attributed_stage: "unknown"` to all existing entries would make batch reports cleaner
  immediately rather than showing "unknown" forever for pre-F1 data. Optional, not required.
- Acceptance: `test_workflow_authority.py`'s existing disposition-shape tests still pass;
  new tests cover both the old bare-string and new object shape being read correctly.
- This is **Next**, not MVP, because it changes a schema other tooling reads — do it once Epic
  A-E's simpler, purely-additive instrumentation has already proven the reporting loop is useful,
  not before.

### Later (only if replay volume/complexity justifies it)
- Re-verification of `RESOLVED_EDIT` dispositions (actually re-run the check post-edit and confirm
  the finding cleared) — real, valuable, but a bigger behavioral change than "add logging."
- Token/cost instrumentation for the LLM call sites that genuinely go through `call_llm`
  (Stage 0's LLM-fallback extraction; NOT Stage 1's default authoring, which is structurally
  outside this codebase) — parse `usage`/`usageMetadata` fields already present in provider
  responses today, just unread.
- A rotation/retention policy for `run_events.jsonl`, if any single opportunity accumulates enough
  replay history to matter.
- A dashboard, only if the Markdown+CSV batch report genuinely becomes the bottleneck in practice.

---

## 8. Open decisions (need your judgment)

1. **Naming the new report script(s).** I proposed `observability_report.py` /
   `observability_batch_report.py`, matching this file's own name and keeping "observability" as a
   consistent, greppable prefix. Alternative: fold batch reporting into `scan_authoring_defects.py`
   since it already does cross-submission aggregation for a related purpose. *My recommendation*:
   keep them separate — `scan_authoring_defects.py` is scoped to Stage 1/2 *defect recurrence*
   specifically and already has its own promote/decline review workflow; conflating it with
   Stage 0/3 coverage and timing would widen a tool that currently does one job well. The batch
   report can (and should) *read* the existing ledger as one input, not absorb its responsibility.

2. **How aggressively to replay for the baseline.** All 14 current `data/submissions/*` folders in
   one batch, or a smaller first pass (3-4) to validate the instrumentation itself before trusting
   a 14-opportunity baseline. *My recommendation*: instrument (Epics A-D), replay 2-3 opportunities
   by hand to confirm the reports look right and aren't lying about anything, *then* do the full
   batch as the actual baseline — cheaper to catch an instrumentation bug on 3 opportunities than
   to discover it after generating a "baseline" you now can't trust.

3. **Whether `attributed_stage` (Epic F) is worth the schema change at all**, versus doing causal
   attribution entirely in the human-written per-opportunity report prose (§5.2's "Decisions and
   evidence" section) without touching `dispositions.json`. *My recommendation*: start with
   prose-only attribution in the MVP report (free, no schema risk) and only build Epic F if, after
   a few batches, you find yourself wanting to query "how many findings are attributed to Stage 0"
   across many opportunities rather than reading it in each individual report.

4. **Whether Stage 0's `confidence_score` calibration check (M0.4) is worth building at all** given
   it needs real downstream-outcome data to mean anything, and outcome here (interview/rejection)
   is mostly *external* to this pipeline (an actual employer's response, tracked elsewhere in
   `jobs.status`, not in submission folders at all). *My recommendation*: defer past even "Next" —
   this needs a join against `jobagent.sqlite`'s outcome data that's out of scope for a Stage 0-3
   *authoring pipeline* replay and belongs with a different analysis if you ever want it.

---

## Summary answers

**1. Recommended MVP observability package**: Epics A-D from §7 — per-stage duration captured at
the correct call site (not inside `build_receipt`), an append-only per-opportunity event log
generalizing the pattern `verify_history.json` already proved, a per-opportunity Markdown report
that reads across existing artifacts (receipts, findings, dispositions, the existing defect
ledger) plus the new duration/event data, and a batch report with CSV backing. All additive to
existing contracts; nothing existing changes shape.

**2. What you'd see during one run**: a compact console line per stage (result, key signal,
duration, retries/fallbacks/overrides, a pointer to the detailed record) — never raw finding text
flooding the terminal, matching §5.1's example.

**3. What you'd read after a batch**: one Markdown file with completion/failure rates per stage,
timing percentiles, retry/fallback/override rates, findings by severity/rule/phase (reading the
existing defect ledger, not duplicating it), outliers, explicit small-sample cautions, and — once
you have two batches — a before/after diff that never collapses into one score.

**4. The five most important questions this data could answer**:
   1. Which stage is actually where time and rework concentrate, versus where you assume it does?
   2. Is Stage 0's LLM-extraction-fallback rate trending down as the NLP model matures, or stuck?
   3. Are Stage 2 findings mostly real catches (`RESOLVED_EDIT`) or mostly noise
      (`ACCEPTED_AS_CORRECT` every time) — and is that ratio stable across submissions?
   4. Did CR-107's rename actually change `NEEDS_DISPOSITION` resolution behavior (M2.3), or is
      that still happening slowly?
   5. When a change lands (a prompt tweak, a rubric update, a gate fix), did it move a metric in
      the intended direction, and did anything downstream get worse?

**5. What this system still would not tell you reliably**: whether Stage 0's confidence score is
actually calibrated (needs real outcome data this design deliberately doesn't reach into); whether
a `RESOLVED_EDIT` disposition actually fixed anything (self-reported, not re-verified, until the
Later-phase re-verification work is built); the true cost/quality of Stage 1's default authoring
path (that LLM call happens in a separate session this codebase cannot see into, by design); and
anything about real-world outcome (interviews, offers) — this design instruments the *authoring
pipeline*, not the job search's actual results.
