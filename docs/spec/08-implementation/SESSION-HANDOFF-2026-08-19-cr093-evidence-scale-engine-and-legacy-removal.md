# SESSION HANDOFF — 2026-08-19 — CR-093 evidence-scale fit engine, calibration research, and legacy-fit removal

Read this before touching anything fit-scoring-related. This was a long session (picking up from
the earlier same-day `SESSION-HANDOFF-2026-08-19-stage0-diagnosis-and-fit-rubric.md`) that built a
whole new fit-scoring engine, ran a real pressure test against it, did real primary-source
research to replace an unfounded threshold, and then — on Jason's explicit instruction — deleted
the entire superseded fit-scoring system rather than leaving it running in parallel. Nothing from
today is committed yet as of this handoff; that's this session's last action, not skipped.

## Git state — read this first

**Uncommitted, on `main`, on top of 8 already-unpushed commits from the earlier same-day session.**
A new branch should be cut before committing today's work (per this repo's own convention: don't
commit large work directly to `main`). If you're reading this after that commit already landed,
this paragraph is stale — check `git log` and `git status` for the real current state before
assuming anything below is still uncommitted.

Two pre-existing untracked files from the earlier session remain, both intentional, neither needs
action: `data/Resume_Generic_Indeed.docx` (never investigated, ask Jason if relevant), and this
session's own research artifact `data/fit_rubric_spec.html` (the rubric design spec CR-093
implements — kept in `data/` per repo convention for `data/*.json`-adjacent files, not committed).

## What this session actually built (read before assuming anything is missing)

Full detail, evidence ledgers, and the complete pressure-test log live in
**`docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md`** — treat that as the primary
source of truth for the new engine's design and status; this handoff summarizes and points at it,
it doesn't replace it.

1. **A new fit-scoring engine (`scripts/evidence_scale.py`)** — one LLM judgment per JD requirement
   line, rating a 0-4 behaviorally-anchored evidence scale against retrieval-scoped
   `workExperience.md` excerpts (chunked by heading, ranked by token overlap with the specific
   requirement — not a blind prefix truncation). Hard-gates only for unbridgeable degree, named
   regulated-domain-with-years, or role-category exclusion; named tools/skills never gate (a real,
   confirmed miss last session: a JD was rejected sight-unseen over one Tableau mention).
   `compute_fit_score()` turns per-item judgments into one 0-100 score via a deterministic weighted
   formula, no second LLM call.
2. **Wired into the sole live Stage 0 gate** (`scripts/build_stage0_fit_gate.py`'s `classify_gaps`/
   Step 5.5) — the regex classifier that used to live there (`_item_has_anchor`,
   `_is_unbridgeable_advanced_degree`, `_unbridgeable_domain_requirement`, `_classify_single_clause`,
   `_split_compound_item`, etc.) is deleted, not kept as a fallback. Confirmed live end-to-end
   against real archive JDs for all three tier outcomes (score-driven Skip, score-driven Pass,
   hard-gate disqualification).
3. **A real pressure test found and fixed 5 bugs**, each re-verified live, not just logged: a
   counting bug in the golden-set checker itself, the evidence-context truncation issue above, an
   LLM prompt gap that let `gate="HARD"` pair with an empty `gap_source` (crashed a real
   `pending_review` JD), an "adjacent evidence" literalism bug (the model scored real product-
   ownership experience as zero because the specific product name didn't match), and an
   OR-alternative "worst-match" bias (a line offering "product management OR banking experience"
   was scored against banking, which Jason lacks, instead of PM, which he has).
4. **Real primary-source research replaced the unfounded 70-point floor** (Cascio/Alexander/Barrett
   1988's seminal cutoff-score paper, a 2024 standard-setting-methods comparison, OPM's own
   admission that job-fit-as-screen-out validity research is "still in its infancy," TalentWorks
   real-outcome data). Result: `data/fit_rubric_calibration.json` — **tracked in git on purpose**
   (unlike the rest of `data/*.json`, gitignored for personal-data privacy — this is a
   scoring-algorithm calibration constant, not a personal preference, so its history should be
   visible). Holds `score_bands.skip_floor: 40` / `tier1_floor: 65`, explicitly labeled provisional,
   plus a `weighting_model` section flagging that `evidence_scale.py`'s weight table
   (`_REQUIRED_WEIGHT`/`_PREFERRED_WEIGHT`/`_CONFIDENCE_MULTIPLIER`) has the same "not actually
   calibrated" status and should move into this same file on the next recalibration pass.
   `evidence_scale.load_score_bands()` is the sole reader.
5. **The entire superseded fit-scoring system was deleted, not deprecated** — this was the
   explicit, repeated instruction this session, not a default: *"We need to get out of the habit
   of replacing things and keeping the old stuff — it causes confusion later. Harden that we are
   using the new rubric and fit score and erase any mention of the old fit."* See "Already
   resolved" below for the specific list — do not re-investigate these as if they might still
   exist; verify they're still gone (a resurrection search, per the audit task below), don't
   re-decide whether to remove them.

### Already resolved this session — verify still gone, don't re-litigate

- `scripts/structured_fit.py`, `scripts/fit_policy.py`, `scripts/fit_judgment_io.py` — deleted.
- `batch_pipeline.py`'s `evaluate_job_fit()` / `_call_fit_llm()` / `_call_fit_scoring_only()` /
  `process_single()` / `process_batch()` and its `--mode single|batch` CLI entry point — deleted.
  The file is now a pure DB/JD helper library, not directly executable.
- The "Find New Jobs" page (`src/pages/FindNewJobsView.tsx`, `src/hooks/usePipeline.ts`, the
  "Add Job" sidebar tab) and its `POST /api/evaluate` SSE route (`server/routes/pipeline.ts`) —
  deleted. Confirmed dead by Jason directly (not assumed) — this was flagged "do not touch yet,
  not investigated" in a 2026-08-04 handoff, and that investigation is what happened this session.
- `candidate_preferences.json`'s `min_fit_score` field (was `72`), `utils.get_min_fit_score()` /
  `utils.MIN_FIT_SCORE`, and the TypeScript-side `readMinFitScore()` / `DEFAULT_MIN_FIT_SCORE`
  (`server/domain/jobSearchPrefs.ts`, `server/shared.ts`) — deleted. Also removed from
  `data/candidate_preferences.example.json`. The real fit-scoring floor is
  `data/fit_rubric_calibration.json` (40/65), which is a different file for a deliberate reason —
  see point 4 above.
- The old Stage 0 tier thresholds (hardcoded `80`/`70` literals in `build_stage0_fit_gate.py`) —
  replaced by `evidence_scale.load_score_bands()`.
- Dead maintenance scripts with no live caller and no purpose beyond the deleted system:
  `re_score_jobs.py`, `regenerate_backlog.py`, `cleanup_pending_backlog.py` — deleted.
- Test files that only tested the deleted system: `test_structured_fit.py`,
  `test_structured_fit_claude_native.py`, `test_fit_policy.py`, `test_fit_judgment_io.py`,
  `test_audit_convergence.py`, `test_batch_gate.py` — deleted. `test_audit_convergence.py`'s one
  genuinely valuable regression (CR-054 non-convergence transparency) has independent coverage in
  `test_audit_improve_native.py`, confirmed unaffected.
- `README.md`, `PRODUCT_CAPABILITIES.md`, `CHANGELOG.md` updated to describe only the new engine.
- **Verified clean, not assumed:** `npx tsc --noEmit` zero errors; full `npx vitest run` 292/292
  passing across 32 files; `python scripts/run_all_tests.py --python-only` clean apart from the two
  items in the very next section.

## What's outstanding — the real next-step list

This is the actual task for the next session. Two parts: (1) a few concrete, already-diagnosed
items from this session that just ran out of room, and (2) a full repository-audit task — adapted
from a prompt Jason supplied, corrected for Applyr's actual architecture — to catch anything this
session's necessarily-improvised sweep missed. Do **not** skip straight to the audit prompt without
reading the concrete items first; they're faster to fix and some of them feed directly into the
audit's own "Phase 8 — Tests" work.

### 1. `test_build_stage0_fit_gate.py` — 13 real test failures, not yet triaged one-by-one

Running the file directly (`python -m unittest scripts.test_build_stage0_fit_gate -v`) takes
**~17-18 minutes** now — it's making a real LLM call per test that reaches `classify_gaps()`, not
the instant offline run it used to be. This is the already-known Epic 2 Story 2.7 gap (see the CR
doc), now actually measured for the first time rather than estimated: **106 tests ran, 93 passed,
13 failed, 16 skipped** (skips are this session's own decorators on tests that directly exercised
now-deleted regex functions or asserted now-false invariants — those are correctly retired, not
part of this outstanding item).

Only 3 of the 13 failures were visible (the harness truncated the very long captured output to its
tail) — **the other 10 were never actually seen and need a real look, not an assumption.** The 3
that were seen all fit one of two patterns, and it's a reasonable bet (not a confirmed fact) that
the rest do too:

- **Stale invariant, not a bug**: `test_guidewire_now_hard_blocked_not_silently_clear` asserts
  `gap_class == "HARD"` for a named tool. Per the spec this engine implements, named tools never
  hard-gate (§9) — this assertion is definitionally false now, same category as the tests already
  skipped this session (`test_fhir_is_hard_gap` etc.) in the same file. This test method just
  wasn't found during that earlier sweep — it's in `TestUnconfirmedToolAllowList`, a class name
  that didn't obviously read as "tests the old hard-gate mechanism" from its name alone.
- **Stale implementation-detail assertion**: `test_unlisted_named_tool_becomes_soft_gap_despite_generic_word_match`
  asserts the literal string `"unconfirmed tool"` appears in the reasoning text — that was
  old-regex-specific terminology (`_looks_like_named_tool`); the new engine's `anchor` field is
  free-text LLM reasoning that will never contain that exact phrase.
- **Fixture too thin for the new model, not a logic bug**: `test_domain_in_preferred_bucket_stays_soft`
  uses a minimal synthetic JD built for the old keyword-heuristic scorer. Under the new per-item
  evidence model, a fixture with almost no real content naturally produces `fit_score: 0` across
  the board (nothing to credit), which now Skips via the score floor — an unrelated side effect
  masking whatever the test's own actual assertion (domain-in-preferred shouldn't gate) would show
  with a more realistic fixture.

**Action needed**: get real visibility into the other 10 (re-run with output redirected to a file
you control, not the harness's `.output` capture, since that one truncates long runs — e.g.
`python -m unittest scripts.test_build_stage0_fit_gate -v > /tmp/full_test_output.txt 2>&1`, run in
background given the ~18min runtime), then do the real Story 2.7 work this points at: either fix
each test's fixture/assertion to match the new design (where the underlying behavior it's
protecting is still real and correct), or delete it if the whole test was purpose-built for the
deleted mechanism (matching the "regex-era tests" already retired this session). Do not just
delete all 13 without reading each one — some may be surfacing a real bug, not a stale assumption;
the 3 seen so far all turned out to be the fixture/assertion problem, but that's not proof the
other 10 are too.

**Longer-term, separate from the triage above**: this whole file's "no real DB, no LLM" design
premise (its own docstring) is now false for any test that reaches `classify_gaps()` — the ~18min
runtime is the real cost of that. The actual fix (mocking `evidence_scale.classify_requirement()`
per test case so this runs fast/offline again) is real, separate engineering work, not something
to do as part of the triage above. Track it, don't silently attempt it inline.

### 2. `batch_pipeline.py` — a scoped-out general dead-code sweep

This session removed everything traceable specifically to fit-scoring from `batch_pipeline.py` and
verified it (imports, env-var side effects, `GPU_LOCK`, the whole CLI entry point). It did **not**
do an exhaustive dead-code sweep of the file's *remaining* ~350 lines — DB/JD helper functions like
`_mark_job_needs_retry`, `_mark_job_rejected`, `_update_job_row`, `_set_backlog`, `save_pre_score`,
`save_jd_vector`, `check_is_duplicate_and_get_vector`, `extract_and_save_salary`,
`ensure_jobs_schema`, `_repair_jobs_fts`, `_find_staging_jd`, `_load_job_title`,
`_cleanup_staging_file`, `safe_print` were confirmed to have **zero external callers** during this
session's audit, but weren't traced further to confirm whether anything *within* the surviving code
calls them internally either. They may be fully orphaned (a `STATUS_NEEDS_RETRY`/backlog-tracking
mechanism whose only real caller, `process_single()`, was deleted this session) or may still be
load-bearing in a way a quick grep missed. This is real, separate hygiene work — lower priority
than item 1, explicitly out of scope for "erase the old fit" specifically (these aren't fit-scoring
functions), but worth finishing so `batch_pipeline.py` doesn't become a second confusing
half-legacy file.

### 3. Pre-existing, unrelated, confirmed-not-caused-by-this-session

`test_audit_claims_coverage.py::test_live_catalog_error_tier_clean` fails — 54 real
`we_unclaimed` findings (`ACC-XXX` codes in `workExperience.md` with no matching `project_id` in
`master_claims.json`). Confirmed via the test's own imports that this has nothing to do with
fit-scoring (`audit_claims_coverage.py`, CR-088's claim-catalog hygiene tool) — this session never
touched `workExperience.md` or `master_claims.json`. Real, but a different owner's problem; don't
fix it as part of fit-engine work, just don't be alarmed it's failing.

### 4. Explicitly flagged but not started this session

- **Extraction-quality bug** (pre-existing, separate system): several real `pending_review` JDs
  produced garbled or empty required-item lists (a full opening paragraph, or the literal job
  title, instead of real requirement bullets) from `_extract_sections_llm`/`_extract_sections` in
  `build_stage0_fit_gate.py`. This is section *extraction*, not the evidence-scale engine this
  session built — confirmed by inspecting the actual extracted items, not inferred. Worth its own
  focused session; not a CR-093 story.
- **Full 402/416-JD archive-corpus sweep** (CR-093 Epic 3 Story 3.1): only a 15-JD spread sample
  ran, not the full corpus — each JD is several real LLM calls, infeasible to complete in one
  sitting. The 5 that reached real classification (out of 15) scored 40/53/55/56/63, a real spread
  with no crashes — reassuring but a genuinely small sample.
- **Floor recalibration against real outcomes** (CR-093 Epic 4's own stated upgrade path): 40/65 is
  design-inference grounded in real research, not yet checked against real interview outcomes under
  *this* engine, because none exist yet. Revisit once Jason has applied to jobs scored under it and
  real callback/no-callback data exists — that's a genuine Contrasting-Groups-method opportunity
  the calibration file itself documents.

---

## Part 2 — Repository-wide legacy-fit resurrection audit (adapted from a prompt Jason supplied)

Jason supplied a detailed audit prompt (below) written by an external LLM with no access to this
repository. It's a genuinely good, rigorous methodology — the phase structure, failure-mode list,
and "resurrection search" framing all match real work already done this session — but it was
written generically and assumes the audit is starting from zero. **It mostly isn't.** Section 1
above already is Phase 1-6 and most of Phase 9's real work, done and verified. Treat the prompt
below as the **verification and completeness pass**, not a from-scratch investigation — its actual
job now is to catch whatever this session's necessarily time-boxed sweep missed, not to
re-discover `structured_fit.py`.

**Corrections made to the prompt for Applyr's actual context** (the original is preserved verbatim
below this note for completeness, since editing it in place risked losing intent — read the
corrections first, then the prompt with these substitutions in mind):

- "the old numeric threshold such as `72`" — imprecise. There were **two** old thresholds: `72`
  (`candidate_preferences.json`'s `min_fit_score`, read by the now-deleted `structured_fit`/
  `batch_pipeline.py` path) and `80`/`70` (hardcoded literals in `build_stage0_fit_gate.py`'s Step
  5.5, the live Stage 0 gate's own tier logic — a *second*, different, unrelated-until-this-session
  number). Both are confirmed removed this session. The new number is **40/65** in
  `data/fit_rubric_calibration.json`, not a single value.
- "the new research-backed rubric" / "the new fit score" — concretely: `scripts/evidence_scale.py`
  (the engine), `data/fit_rubric_spec.html` (the research spec it implements),
  `data/fit_rubric_calibration.json` (the calibration constants), wired into
  `scripts/build_stage0_fit_gate.py` (the sole live Stage 0 gate, itself reached only via
  `scripts/run_submission.py`). There is no separate "rubric" artifact beyond these — don't go
  looking for a distinct rubric-definition file that isn't one of these three.
- The "Known Example to Investigate" list's items (`structured_fit.py`, `batch_pipeline.py`,
  `evaluate_job_fit()`, `/api/evaluate`, `pipeline.ts`, `FindNewJobsView.tsx`,
  `candidate_preferences.json`'s `min_fit_score`) are **already handled this session** per the
  "Already resolved" section above — the prompt frames these as things to *investigate and decide
  on*; they've already been investigated and decided (delete). Phase 10's "resurrection search"
  is the right lens for these now — confirm they stay gone and nothing new references them — not
  Phases 1-6's original discovery framing.
- "`run_submission.py`" in the same list is **not** a legacy item — it's the current canonical
  entry point (per `AGENTS.md`), already correctly identified as such. Don't classify it as
  something to investigate for removal.
- Phase 1 ("Establish the Current Intended Architecture") is already answered by Section 1 above
  and `docs/spec/05-change-requests/CR-093-evidence-scale-fit-engine.md` — use those as the answer,
  don't re-derive from scratch, but do sanity-check them against real code before trusting them
  blindly (the same discipline this session applied to the 2026-08-04 handoff's claims, which
  turned out accurate but were verified, not assumed).
- The prompt's audit-table deliverable and Phase 2-6 discovery work should focus on **what this
  session didn't already cover**: item 2 above (`batch_pipeline.py`'s remaining orphaned
  functions), a genuine semantic sweep for terminology/comments this session's targeted greps might
  have missed (the prompt's Phase 7/10 "resurrection search" framing), and the `.claude/`,
  `.agent/`, and any other AI-instruction surfaces this session did not specifically check for
  stale fit-scoring guidance (this session checked `AGENTS.md`/`CLAUDE.md` only incidentally, not
  as a deliberate pass).
- Ignore the prompt's implication that a full "pre-migration vs post-migration" audit table is
  needed for components already migrated this session (Section 1's list) — build that table only
  for genuinely new findings, not to re-document what's already in the CR-093 doc.

### The original prompt, verbatim, for full context

<details>
<summary>Click to expand — the full external audit prompt as supplied, unedited</summary>

# Applyr Current-Process Consolidation, Legacy Pruning & Hardening Audit
## Persona
Act as a combination of:
* **Senior Software Architect** responsible for eliminating architectural ambiguity and ensuring there is one authoritative implementation of each workflow responsibility.
* **Senior Staff Engineer** experienced in migrations, dependency analysis, dead-code removal, refactoring, and deterministic workflow systems.
* **QA / Reliability Engineer** responsible for proving that removing obsolete paths does not remove required behavior or introduce regressions.
* **Repository Archaeologist** capable of tracing historical implementations, configuration, tests, documentation, UI routes, scripts, imports, schemas, and indirect dependencies across the entire repository.
Your objective is **not merely to make the new process work**.
Your objective is to ensure Applyr has **one clear current process**, with obsolete implementations removed so that future humans and AI agents cannot accidentally discover and reuse superseded behavior.
---
# Mission
We recently replaced parts of Applyr's old job-fit system with a new **research-backed rubric and fit-scoring process**.
The migration is incomplete if the repository still contains old scoring mechanisms, old configuration values, old documentation, old entry points, old terminology, obsolete tests, compatibility paths, or misleading comments that make the superseded process appear valid.
We have already experienced this failure mode.
Example:
> `candidate_preferences.json` is back to genuinely just being your preferences — `min_fit_score` reset to its original 72, which is still real and still used by the separate legacy scoring path, untouched by any of this.
That is precisely what we do **not** want.
If the new rubric and fit-score system replaces the old fit mechanism, then the repository should not leave behind another apparently legitimate fit-scoring system simply because something still references it.
This creates:
* multiple sources of truth;
* inconsistent outcomes depending on entry point;
* AI-agent confusion;
* accidental resurrection of retired logic;
* hidden configuration dependencies;
* future maintenance burden;
* tests protecting behavior we no longer want;
* documentation describing workflows that no longer exist;
* UI or API routes silently executing obsolete code.
The goal of this task is therefore:
> **Audit the entire repository, identify every trace and consumer of the superseded fit-scoring architecture, determine what required behavior must be preserved, migrate that behavior into the current architecture where necessary, remove the obsolete architecture, and harden the repository so that the new rubric-based process is unmistakably authoritative.**
---
# Core Principle
## One responsibility → one authoritative implementation
Do not preserve two implementations simply because both currently work.
If Process B supersedes Process A:
**Process B becomes authoritative.**
Process A should normally be:
1. fully disconnected,
2. migrated away from,
3. deleted,
4. removed from configuration,
5. removed from tests,
6. removed from documentation,
7. removed from agent instructions,
8. removed from UI/API entry points,
9. removed from examples and fixtures,
10. removed from terminology suggesting it remains supported.
Do **not** solve migration problems by leaving the old implementation available "just in case."
Backward compatibility is not automatically desirable inside this repository.
---
# Important Distinction: Preserve Capabilities, Not Legacy Implementations
Before deleting an old component, identify whether it performs any behavior the current system still requires.
For example, an obsolete fit scorer might also contain:
* location validation;
* exclusion-zone enforcement;
* remote/hybrid checks;
* retry handling;
* data normalization;
* required/preferred requirement parsing;
* evidence validation;
* anchor detection;
* logging;
* persistence;
* error handling;
* workflow receipts;
* UI response formatting.
Those capabilities must **not disappear accidentally** merely because the scorer containing them is obsolete.
For every legacy component, ask:
> "Is this behavior obsolete, or is only this implementation obsolete?"
If the behavior is still required:
1. identify where it belongs in the current architecture;
2. migrate or consolidate it there;
3. test the current implementation;
4. then remove the legacy implementation.
Do not retain the entire old system simply to preserve one useful helper or behavior.
---
# Scope
Perform a repository-wide investigation.
Do not limit the audit to files we already suspect.
Trace the old and new fit systems through:
* Python
* TypeScript / JavaScript
* frontend code
* backend/API routes
* CLI scripts
* orchestration
* configuration
* JSON
* schemas
* models
* tests
* fixtures
* mocks
* snapshots
* documentation
* README files
* comments
* prompts
* `AGENTS.md`
* `CLAUDE.md`
* AI/reference files
* workflow documentation
* examples
* migration artifacts
* shell scripts
* package scripts
* CI
* logging
* generated artifacts where applicable
* database/storage fields
* historical compatibility adapters
* feature flags
* environment variables
Search by **concept**, not only exact filename.
---
# Known Example to Investigate
We already know that historical code has included things such as:
* `structured_fit.py`
* `batch_pipeline.py`
* `evaluate_job_fit()`
* `/api/evaluate`
* `pipeline.ts`
* `FindNewJobsView.tsx`
* `candidate_preferences.json`
* `min_fit_score`
* the old numeric threshold such as `72`
* older location / anchor / scoring logic
* older UI Draft / Find New Jobs workflows
* `run_submission.py`
* the new research-backed rubric
* the new fit score
These are **starting points only**.
Do not assume this list is complete.
---
# Phase 1 — Establish the Current Intended Architecture
Before changing anything, reconstruct the process that is intended to survive.
Determine:
1. What is the authoritative fit-evaluation entry point?
2. What component owns the new research-backed rubric?
3. How is the new fit score calculated?
4. What inputs does it consume?
5. What artifacts does it produce?
6. Where is the score persisted?
7. What thresholds or decision rules exist?
8. What workflow stage consumes the result?
9. What CLI/UI/API paths are expected to invoke it?
10. Which configuration values influence it?
11. Which tests establish its contract?
12. Which documentation describes it?
Produce a concise architecture description.
Do not infer architecture from filenames alone.
Trace actual execution.
---
# Phase 2 — Build a Complete Consumer Map
Search the repository for every implementation and reference related to job fit.
Start with known names, but expand outward through imports, calls, configuration keys, returned fields, routes, schemas, tests, and terminology.
Search for concepts including variants of:
* fit
* fit score
* scoring
* scorer
* threshold
* minimum score
* `min_fit_score`
* evaluate
* evaluation
* rubric
* Tier 1
* Tier 2
* Skip
* recommendation
* qualification
* match
* match score
* required qualifications
* preferred qualifications
* anchor
* exclusion
* location gate
* hard gap
* soft gap
For each discovered component, trace both:
### Upstream
Who invokes it?
### Downstream
What does it invoke or modify?
Continue recursively until you understand the complete dependency graph.
Do not conclude something is dead merely because there are no direct imports.
Look for:
* subprocess execution;
* dynamically constructed paths;
* HTTP calls;
* route names;
* shell execution;
* configuration-driven references;
* lazy imports;
* string-based module loading;
* frontend → API dependencies;
* scripts invoked externally;
* package scripts;
* documentation telling users or agents to execute it.
---
# Phase 3 — Classify Every Relevant Component
Place every discovered item into exactly one category.
### A. CURRENT — KEEP
Part of the intended new architecture.
### B. CURRENT — HARDEN
Belongs to the new architecture but needs changes so the current process becomes explicit or safer.
### C. MIGRATE CAPABILITY THEN DELETE
Legacy implementation contains behavior still needed by the current system.
Extract or reimplement the required behavior in the correct current location, prove it works, then remove the legacy implementation.
### D. LEGACY — DELETE
Superseded behavior with no legitimate consumer in the current process.
Remove it.
### E. AMBIGUOUS
Its purpose cannot yet be established from repository evidence.
Investigate further before modifying it.
Do not automatically classify something as CURRENT merely because something calls it.
A live caller may itself be obsolete.
Trace the entire branch before deciding.
---
# Phase 4 — Identify Parallel Sources of Truth
Explicitly search for cases where the repository can answer the same business question in multiple ways.
Especially identify multiple implementations of:
> "Is this job a good enough fit to pursue?"
Look for parallel:
* scoring algorithms;
* fit thresholds;
* rubric definitions;
* qualification parsers;
* Tier classification rules;
* location rules;
* exclusion-zone rules;
* configuration values;
* UI calculations;
* backend calculations;
* API calculations;
* CLI calculations.
For every duplication, identify the authoritative owner.
The desired end state is:
> **One canonical decision mechanism, with callers delegating to it rather than independently reproducing the logic.**
---
# Phase 5 — Configuration Audit
Audit configuration aggressively.
A setting should not remain merely because old code still knows how to read it.
For every fit-related configuration property, determine:
1. What currently reads it?
2. Is that reader part of the intended architecture?
3. Does the new architecture require the value?
4. Does the property represent a user preference or an implementation detail?
5. Would leaving the setting behind imply that obsolete functionality still exists?
Specifically investigate:
`candidate_preferences.json`
and:
`min_fit_score`
If `min_fit_score` belongs exclusively to the superseded scorer, remove it rather than restoring or preserving it.
Do not keep obsolete configuration because:
> "It still has a consumer."
If the consumer is obsolete, remove the consumer too.
After deletion, search again to prove no unresolved references remain.
---
# Phase 6 — Entry-Point Audit
Identify **every way a user, UI, script, agent, test, API, or automation can initiate fit evaluation.**
Examples may include:
* `run_submission.py`
* UI buttons
* Find New Jobs
* Draft
* API routes
* batch commands
* test utilities
* development commands
* helper scripts
For each entry point determine:
**Entry Point → Handler → Service → Scorer → Persistence → Next Stage**
Compare them.
There should not be separate business logic depending on how the workflow was initiated.
Where multiple valid entry points remain, make them converge on the same authoritative implementation.
Where an entry point belongs to an abandoned workflow, remove the entire branch cleanly.
---
# Phase 7 — Documentation and AI Instruction Audit
This is extremely important because AI coding agents use repository text as evidence.
Search:
* `AGENTS.md`
* `CLAUDE.md`
* README files
* architecture docs
* workflow docs
* comments
* examples
* prompts
* test descriptions
* inline documentation
* reference files
for descriptions of the old fit process.
Remove or update statements implying that the old scorer, old threshold, old route, or old workflow remains supported.
Do not leave comments such as:
> legacy scorer
> old scoring path
> previous fit implementation
unless there is a compelling technical reason that future maintainers must know about it.
Ordinarily, source code should describe **what exists now**, not preserve archaeological layers of systems we intentionally retired.
Historical information belongs in version control, not active operational documentation.
---
# Phase 8 — Tests
Audit tests with the same rigor as production code.
Tests can accidentally preserve obsolete architecture.
Classify relevant tests as:
* verifies current required behavior;
* verifies behavior that should migrate;
* protects obsolete implementation;
* fixture/helper used only by obsolete tests.
If a valuable behavior test belongs to the legacy system:
1. migrate the test to the current implementation;
2. verify the new implementation satisfies it;
3. remove the obsolete test.
Do not leave tests whose only purpose is proving deleted architecture continues to behave as before.
Add regression tests specifically ensuring:
* the new rubric is used;
* the new fit score is authoritative;
* obsolete scoring cannot be invoked accidentally;
* old configuration values are unnecessary;
* all supported entry points converge onto the current mechanism.
---
# Phase 9 — Execute the Cleanup
Once the dependency analysis is complete, perform the migration.
The sequence should generally be:
1. preserve required behavior in the new system;
2. redirect legitimate callers;
3. verify those callers;
4. remove obsolete callers;
5. remove obsolete implementations;
6. remove obsolete configuration;
7. remove obsolete schemas/types;
8. remove obsolete tests and fixtures;
9. remove obsolete documentation;
10. remove obsolete comments;
11. remove obsolete terminology;
12. clean imports and dependencies.
Prefer deletion over deprecation when we have intentionally replaced the process.
Do not create:
* `_legacy`
* `_old`
* `_deprecated`
* compatibility aliases
* passthrough wrappers
* dormant feature flags
unless an external compatibility requirement can be demonstrated.
---
# Phase 10 — Repository-Wide Resurrection Search
After implementation, perform another fresh search as though you were an AI agent entering the repository for the first time.
Try to discover the obsolete architecture.
Search for:
* old function names;
* old filenames;
* configuration fields;
* thresholds;
* API endpoints;
* UI labels;
* imports;
* comments;
* test names;
* documentation phrases;
* old JSON fields;
* old output schema fields;
* legacy terminology.
The standard is not merely:
> "Nothing calls the old scorer."
The stronger standard is:
> **A future developer or AI agent inspecting the repository should not reasonably conclude that the old fit-scoring architecture still exists or should be used.**
Document anything intentionally retained and why.
---
# Phase 11 — Architectural Hardening
Now make the desired architecture difficult to accidentally bypass.
Look for opportunities such as:
* one canonical fit-evaluation service;
* centralized rubric ownership;
* centralized score calculation;
* shared schemas/types;
* explicit workflow-stage contracts;
* assertions validating required artifacts;
* fail-closed behavior when rubric outputs are missing;
* removal of duplicated thresholds;
* tests proving supported entry points use the canonical service;
* clear naming that distinguishes user preferences from scoring policy.
Do not introduce unnecessary abstraction.
The goal is **clarity and enforcement**, not architecture for architecture's sake.
---
# Failure Modes You Must Actively Prevent
## Failure Mode 1 — "It's still used, so keep it"
Incorrect reasoning.
First determine whether the **consumer should exist**.
---
## Failure Mode 2 — Parallel Mechanisms
Do not leave:
Old Scorer + New Rubric Scorer
simultaneously available for different entry points.
---
## Failure Mode 3 — Configuration Archaeology
Do not leave old configuration values because deleting them feels risky.
Trace them, migrate legitimate behavior, then remove them.
---
## Failure Mode 4 — Wrapper Instead of Removal
Do not leave the obsolete implementation and merely put the new implementation in front of it.
Remove the replaced mechanism.
---
## Failure Mode 5 — Comments as Tombstones
Do not litter active code with explanations of everything that used to exist.
Version control preserves history.
---
## Failure Mode 6 — Deleting Useful Behavior With Old Architecture
Separate capabilities from implementation before deleting.
---
## Failure Mode 7 — Searching Only Known Names
The obsolete implementation may have spread into unrelated filenames, schemas, UI components, tests, and configuration.
Search semantically and follow dependencies.
---
## Failure Mode 8 — Asking the User Whether Internal Code Is "Still Used" Too Early
Repository evidence should answer most questions.
Do not immediately ask:
> "Do you still use this?"
Instead determine:
* whether the route is reachable;
* whether the UI exposes it;
* whether current documented workflow uses it;
* whether tests depend on it;
* whether another supported entry point supersedes it;
* whether recent architecture establishes a replacement.
Only escalate a question when repository evidence genuinely cannot resolve a consequential product decision.
---
# Decision Rule for Ambiguity
When encountering something that appears live but contradicts the current architecture:
**Do not assume live = valid.**
Investigate the entire dependency branch.
Ask:
> "Is this intentionally part of the current product, or is this simply an incompletely removed historical pathway?"
Use repository architecture and the current workflow specification as the primary evidence.
---
# Required Deliverables
Before editing, produce an audit table:
| Component | Location | Current Consumer | Responsibility | Classification | Required Behavior to Preserve | Action |
| --------- | -------- | ---------------- | -------------- | -------------- | ----------------------------- | ------ |
Then provide:
## 1. Current Architecture
Describe the authoritative fit workflow.
## 2. Legacy Surface Area
Everything belonging to the superseded architecture.
## 3. Hidden Couplings
Required behaviors currently trapped inside obsolete components.
## 4. Migration Plan
Exact order of operations.
## 5. Risk Assessment
For each destructive change explain:
* what could break;
* how we know whether it is safe;
* what test proves it.
Then implement the migration.
---
# Post-Implementation Verification
After changes, report:
### Files Deleted
List them.
### Files Modified
List them and why.
### Configuration Removed
List obsolete settings removed.
### Callers Migrated
Show old → new ownership.
### Tests Added/Changed/Removed
Explain what contract each relevant test now protects.
### Legacy Search Results
Show the final repository search for obsolete identifiers and terminology.
Any remaining hit must have an explicit explanation.
### Supported Fit Execution Paths
Show every remaining valid entry point and trace it to the canonical scorer.
For example:
```text
run_submission.py
    ↓
Stage 0
    ↓
canonical fit evaluator
    ↓
research-backed rubric
    ↓
fit result
    ↓
stage0_fit_gate.json
```
If a UI entry point remains:
```text
UI
    ↓
API
    ↓
same canonical fit evaluator
    ↓
same rubric
```
There should be no second scoring implementation.
---
# Final Architecture Test
At the end, answer these questions explicitly:
1. **How many fit-scoring implementations now exist?**
2. **What is the single source of truth?**
3. **Can any supported workflow bypass the new rubric?**
4. **Does `min_fit_score` or the old numeric scoring threshold still exist anywhere?**
5. **Does any production code still invoke the old scorer?**
6. **Does any UI/API route still expose the old scorer?**
7. **Do any tests still protect the old scorer?**
8. **Does any active documentation instruct an AI or human to use the old scorer?**
9. **What behavior was migrated out of the old implementation before deletion?**
10. **What evidence proves the migration did not remove required behavior?**
For questions 3–8, the intended answer should normally be **No**.
If it is not, explain exactly why and whether that contradicts the desired architecture.
---
# Definition of Done
This task is **not complete** when:
> "The new rubric works."
It is complete when:
> **The new rubric is the single authoritative fit-evaluation system, every legitimate workflow reaches it, all required capabilities from superseded code have been preserved where appropriate, obsolete implementations and configuration have been removed, tests protect the new contract rather than the old architecture, and repository-wide searches provide no misleading evidence that another fit-scoring system remains supported.**
Optimize for **one clear system, one source of truth, and zero architectural ambiguity.**

</details>

## Suggested priority order for the next session

1. Item 1 above (the 13 test failures) — bounded, already half-diagnosed, directly protects the
   engine this session built from bit-rotting silently.
2. The audit's Phase 10 "resurrection search" specifically (a fresh grep sweep for the identifiers
   in "Already resolved" above, plus a genuine semantic pass through `.claude/`, `.agent/`, and any
   AI-instruction surface this session didn't deliberately check) — cheap, high-confidence, closes
   the loop on the actual instruction that started this whole thread.
3. Item 2 (`batch_pipeline.py`'s remaining orphaned functions) — real but lower-stakes hygiene.
4. Items 4's sub-items (extraction-quality bug, full corpus run, real-outcome recalibration) — each
   is its own real piece of work, not a quick follow-up; sequence by what's actually blocking a
   real application cycle for Jason.

## Things worth knowing that aren't obvious from the code alone

- **Live-LLM test runtime is now a real cost, not a rounding error.** Any test file that reaches
  `evidence_scale.classify_requirement()` (directly or via `build_stage0_fit_gate()`) makes a real
  Ollama call per requirement line. `test_build_stage0_fit_gate.py`'s full run is ~18 minutes now,
  not instant. Budget background-task time accordingly; don't expect a quick foreground run.
- **The harness's captured `.output` file truncates long-running background commands to the tail.**
  If you need full output from a long live-LLM test run, redirect to a file you control and `Read`
  that file directly — don't rely on the background-task notification's linked `.output` file for
  anything beyond the last ~2-3KB of a multi-minute run.
- **`data/fit_rubric_calibration.json` is intentionally the one `data/*.json` file that's tracked in
  git** (a `.gitignore` exception was added specifically for it). If you add more calibration
  constants there later (the weighting-model migration this file's own `_description` field already
  flags), that stays tracked too — don't accidentally add it back to the gitignored pattern.
- **Ollama is not running by default between sessions** — `model_manager.ensure_ollama_running()`
  handles this automatically (auto-starts, ~12s cold) but the first real Stage 0 call of a new
  session will be slightly slower for that reason alone.
