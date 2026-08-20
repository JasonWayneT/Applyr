# SESSION HANDOFF — 2026-08-19 — Stage 0 diagnosis pass, score-driven tiers, and a research-grounded fit rubric

This was a long, single-day session that started as "walk Stage 0 step by step and watch for hiccups"
and grew into a real architecture pass on how job fit gets measured. Read this before doing anything else
in this repo — several defaults changed today (the fit-score floor semantics, what counts as an
auto-Skip, how the score gets computed at all), and picking up mid-thread without this context risks
re-litigating decisions Jason already made, or missing that a mechanism you're about to touch was just
rebuilt.

## Git state — read this first

**6 commits on `main`, ahead of `origin/main`, not pushed.** Confirm with Jason whether to push before
doing anything else — do not assume yes. (Earlier in the session, `git push origin main` was done twice
on explicit "push and merge" instructions; the last 6 commits from the fit-rubric work were not pushed on
request, just landed on local `main`.)

Two untracked files sitting in `data/` (both fine, both intentional, neither needs action):
- `data/fit_rubric_spec.html` — the full rubric design spec (see below). Lives in `data/` on purpose
  (Jason: "keep this report in the data folder for later"), not committed — matches how every other
  `data/*.json` in this repo already stays local.
- `data/Resume_Generic_Indeed.docx` — pre-existing, not part of this session's work, never investigated.
  Not touched, not explained. Ask Jason if it's relevant before doing anything with it.

## Part 1 — Stage 0 diagnostic walkthrough (the first ~60% of the session)

Jason wanted Stage 0 walked one real JD at a time, watching for real hiccups rather than trusting the
pipeline on paper. Real, confirmed bugs found and fixed, in the order they surfaced:

1. **`structured_fit.py`'s equivalence-judgment schema was too loose** — `criteria` was declared as a bare
   `{"type": "object"}`, so a flat `{criterion: "yes"}` map from the model satisfied it exactly as well as
   the nested `{judgment, justification}` shape the parser actually needed. Every real judgment was
   silently dropped, defaulting to `"partial"` — every job scored a uniform ~60/Low-confidence regardless
   of actual fit. This is **the root cause of the "every job score is 80 (then 60)" bug** from an earlier
   session's handoff. Fixed: schema now declares each of the 5 `CRITERION_WEIGHTS` keys explicitly;
   `_normalize_judgments()` also tolerates a flat string as a defensive fallback.
2. **Ollama never auto-started** — `model_manager.ensure_ollama_running()` existed in the working tree
   uncommitted, was supposed to land alongside the "Stage 0 defaults to local LLM" change from the day
   before, but got missed. Every local call silently fell back to the much weaker deterministic regex
   path with zero signal that had happened. Landed as its own commit.
3. **`run_until_stage1_complete()` used a stale folder path after Stage 0 promotion** — a real orchestrator
   bug, not cosmetic: every single JD that passed Stage 0 crashed with a misleading STALE/ERROR message
   instead of cleanly reporting `WAITING_FOR_LLM`, because a helper function moves the folder internally
   (`pending_review/` → `submissions/` on PASS, or → `archive/skipped/` on SKIP) but only returns `state`,
   not the new path. Fixed by re-resolving the folder by slug after that call, with a `SKIPPED` early-return
   mirroring an existing correct branch nearby.
4. **Two false-positive bugs found live-testing real archive JDs one at a time**: the LLM section-splitter
   never stripped a leading bullet marker (`"- Own and lead..."` instead of `"Own and lead..."`), and the
   unconfirmed-tool check had no way to know a JD's own company name isn't a tool (`"Clerkie's platform"`
   flagged `"Clerkie"` as an unconfirmed tool). Both fixed.
5. **Cleanup discipline**: a `unload_local_models()` call now runs at the end of every Stage 0 evaluation
   (gated on `stage0_section_mode() != "deterministic"` — an earlier unconditional version stalled the test
   suite with real network calls; caught and fixed same session). And two stray leftover
   `pending_review/{slug}/workflow_state.json` folders (byproducts of bug #3, before it was fixed) were
   deleted — confirmed real work already safely lived in `submissions/`.

**Real batch run against 12 fresh CSV-imported JDs** (a real `applyr_jobs (1).csv` Jason downloaded) surfaced
all of the above. Net result after every fix: **all 15 original CSV rows ended up Skip** — not a bug, a
real finding (see Part 2, the floor was miscalibrated).

## Part 2 — Score-driven tiers, hard-gate redesign, and the domain-requirement miss

Jason pushed back hard on one specific behavior: a single missing named tool (Bamboo Health, "Tableau")
was auto-Skipping a JD sight-unseen on everything else. That conversation produced a real redesign,
landed and verified:

- **Fit score now decides Tier 1 (≥80) vs Tier 2 (70-79) vs Skip (<70)**, not gap presence. The old
  gap-based Tier 1/2 split only remains as a **fallback** for when no real LLM score is available
  (deterministic test mode, or the LLM call failed) — production runs always get the score-driven read.
- **Hard gaps split into `gap_source: "degree"` vs `"tool"`.** Only degree-type (and, added later,
  domain-type) hard gaps still force an absolute Skip. A tool-only hard gap no longer auto-Skips — it
  becomes a flagged detail and the score decides the tier on its own merits.
- **A real regex bug found live verifying the above**: the degree check matched bare `"master"` as a
  whole word, which is also an ordinary verb (`"rapidly master a complex domain"`) — Bamboo Health was
  actually hard-Skipping on a phantom degree requirement, not the Tableau line. Fixed: requires the
  possessive/plural (`"master's"`/`"masters"`) or `"master of/degree"`, never bare `"master"`.
- **A genuinely new hard-gate category, found starting the actual Stage 1 authoring walkthrough**:
  OneSource Virtual's top two *required* items were payroll-tax-specific, one with **zero** documented
  evidence (`claim_ids: []` in the packet), yet the JD scored 80/Tier 1. Jason: *"those claims should have
  been found during stage 0 those are hard requirements i don't have."* Added a new check — a required
  line pairing a named, unanchored regulated-domain qualifier with its own explicit years threshold is now
  HARD (`gap_source: "domain"`), same absolute-Skip class as degree. **Ran the new check against the full
  402-JD archive corpus before shipping it**: a bare years+domain match alone hit 19 lines, but 18 of 19
  were false positives (`"X years of product management ... in banking, fintech, or SaaS"` — an OR-list
  where product management, Jason's real background, is itself an acceptable alternative). Added an
  exclusion on the literal `"product management/manager/owner"` phrase plus ordinary hedge language
  (`"ideally"`/`"a plus"`/etc.), which correctly cleared 18 of 19 while keeping the one genuine match.
- **Also found and fixed along the way**: `gap_source` was being silently dropped in a dict comprehension
  that only ever copied `item`/`gap_class`/`anchor`, which would have made the degree-vs-tool split
  invisible downstream if not caught. And the Skip `skip_reason` message now only cites gaps whose
  `gap_source` actually caused the Skip (degree/domain), not any co-existing tool gap that happens to also
  be present — a genuinely score-driven Skip used to get a misleading `"Hard gap(s)"` message instead of
  the real `"Fit score N is below the 70 floor"` one.

**Re-checked the whole 15-row batch after all of this landed: still 0/15 pass.** That's the real, current
state of today's fresh batch — not yet re-examined for whether the 70-point floor itself (see Part 3) is
part of why.

## Part 3 — The fit rubric research project (the last ~35% of the session)

Jason asked for genuine I-O psychology / personnel-selection research before tuning any more numbers by
feel, following a very detailed prompt he wrote himself specifying a 20-section deliverable format. Real
primary/peer-reviewed sources used (not blog summaries) — SIOP's 2018 Principles for Validation, EEOC
Uniform Guidelines (29 CFR §1607), DOL O*NET/KSAO framework, Schmidt & Hunter 1998 and Sackett et al.
2022/2023 meta-analyses, Lawshe's Content Validity Ratio, Hough's 1984 Accomplishment Record method (the
closest validated real-world analog to what Applyr's claim system already does), plus a large real-world
applicant-outcome study (TalentWorks/CNBC, used cautiously, not as a primary source).

**Two findings that actually matter for what happens next:**

1. **The current gap classifier is keyword matching wearing a qualification-matching costume.**
   `_item_has_anchor` checks whether a tag *appears near* a phrase, not how strongly evidence actually
   supports a requirement. The spec's proposed replacement: a 5-level behaviorally-anchored evidence scale
   (0 = no evidence, 4 = strong direct evidence with comparable-or-greater scope) — **designed in the spec,
   not implemented in code yet.**
2. **The 70-point floor has no research behind it that could be found anywhere.** Real applicant-outcome
   data (TalentWorks, 6,000+ applications, 118 industries) shows real interview callbacks plateau around
   40-60% requirement match, not 70-90%. The spec proposes provisional bands (Tier 1 ≥75, Tier 2 ≥50, Skip
   <35) but is explicit these are **design inference awaiting real calibration data**, not settled numbers
   — do not treat them as more validated than the honest 70 they'd replace until real outcome data exists
   to check against.

**Deliverable**: `data/fit_rubric_spec.html` — full 20-section spec (definition of fit, JD taxonomy,
evidence scale, transferability rules, hard-gate rules, weighting model, an implementation-ready formula,
confidence model, dedup rules, score bands, a decision table, worked examples, a 10-case adversarial
pressure test A-J, failure modes, and a section-by-section Keep/Modify/Replace verdict against the actual
current codebase). Also published as a Claude Artifact this session (link not durable across sessions —
re-open the local HTML file, or ask Jason for the artifact URL if he saved it).

### Self-healing plan — discussed, then built, not just designed

Jason's real question after the spec: regex-based enforcement has failed repeatedly all session (the
domain-qualifier list didn't have "payroll" until a real miss exposed it; the same root cause as the
original JD-extraction problem from the day before — closed-world pattern matching against an open-world
problem). The agreed design, researched against real few-shot-prompting and golden-dataset literature
before building anything (not guessed):

- **`data/fit_rubric_golden_set.json`** (gitignored, matches `data/*.json` convention) — 21 real entries,
  seeded entirely from today's confirmed cases plus a curated archive sample. 16 are mechanically
  checkable today (degree/domain/tool-nongate/internal-term categories); 5 wait on the evidence-scale
  code landing. **Append-only discipline**: never edit a baseline entry's `expected_*` fields in place —
  set `status: "superseded"` and add a fresh entry if a past judgment is reconsidered.
- **`scripts/check_fit_rubric_golden_set.py`** (committed) — runs the golden set against real code,
  reports pass/fail **per category**, not one aggregate number. Currently 16/16. Building this caught two
  real bugs in the golden set's own authoring before it caught anything in production code — worth reading
  the commit message for the full story if that mechanism gets extended.
- **`scripts/fit_rubric_examples.py`** (committed) — retrieval-augmented few-shot: a growing example bank
  (the golden set's `few_shot_eligible` entries — no separate file, one source of truth), ranked by
  token-overlap with the current input, top-3 injected per call. Wired into the **one** live LLM call this
  can actually help today: `_extract_sections_llm()`'s internal-terms detection. The degree/domain/tool
  gate logic is still deterministic regex, so few-shot examples have nowhere to plug in for those yet —
  that requires the evidence-scale/LLM-judgment work from the spec's Section 19 landing first.
- Verified end to end: the real prompt sent to the model now contains retrieved examples in the right
  spot (confirmed placement matters — Ollama's "lost in the middle" behavior, examples go right before the
  final instruction, not buried in the JD text), and Dark Matter Technologies' real JD still correctly
  returns `internal_terms=['Empower', 'Exchange']` through the live model with retrieval in the loop.

## What's NOT done — the real next-step list, in likely priority order

1. **Build the 0-4 evidence scale from the spec's Section 7 in actual code.** This is the big one — it's
   what the golden set's 5 skipped entries are waiting on, and it's what would let the degree/domain/tool
   *classification itself* (not just internal-terms) start using retrieval-augmented few-shot instead of
   regex. Everything else in the self-healing plan is scaffolding built ahead of this landing.
2. **Grow the golden set toward the researched 50-100 target** (currently 21). Every new confirmed miss
   from here forward should become an entry — that's the actual point of building the checker.
3. **Decide whether to recalibrate the 70-point floor.** The spec's provisional bands (75/50/35) are
   reasoned from real research but explicitly not empirically validated yet. Needs either real outcome
   data (did Jason apply, did he hear back) or a deliberate acknowledged-provisional decision from Jason.
4. **Re-run today's 15-row batch** once the floor question is settled, to see if the real number changes
   from 0/15 or if that batch was genuinely weak.
5. **Minor, never chased down**: `run_submission.py --force` doesn't correctly re-derive a Stage 0 result
   for a folder already sitting in `archive/skipped/` — it replays the stale cached skip-ledger reason
   instead of re-checking. Worked around by calling the underlying function directly with
   `ignore_skip_ledger=True`; the CLI-level bug itself is still open.
6. **`submissionFolders.ts`'s separate `job_scores.score_total` reconciliation path** (for `Drafted`-status
   jobs) was noted this session as a third score-representation mechanism, distinct from Stage 0's
   `fit_score` and the old scout pipeline's score — never investigated further. Worth checking whether it
   needs to be part of the "one fit score" consolidation Jason asked for.

## Things worth knowing that aren't obvious from the code alone

- **Ollama is not running by default on this machine between sessions** — `ensure_ollama_running()` handles
  this automatically now (auto-starts, ~12s cold), but don't be alarmed if the first Stage 0 call of a new
  session takes a few extra seconds.
- **VRAM is not a real constraint here** even with multiple models in play — qwen2.5:7b-instruct-q4_K_M is
  ~4.7GB, nomic-embed-text (available locally, unused so far beyond being confirmed present) is ~274MB,
  combined well under the ~8.5-9GB free VRAM this machine has shown all session.
- **The archive corpus (`data/archive/submissions/`, 402 real JDs) is the right tool for sanity-checking
  any new Stage 0 rule before shipping it** — every real fix this session that held up was checked against
  it first. The domain-hard-gate rule specifically would have shipped with an 18/19 false-positive rate
  without that check.
- **Company/JD folders sitting in `pending_review/` after a Stage 0 PASS is always a leftover bug, never
  expected state** — a real PASS promotes the whole folder to `submissions/`. If you see one, something
  didn't clean up correctly (see bug #3 above for the mechanism that used to cause exactly this).
