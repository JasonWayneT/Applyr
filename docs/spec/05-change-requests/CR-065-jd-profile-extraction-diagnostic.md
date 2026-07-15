# CR-065: JD-Profile Extraction Diagnostic (Keywords/Requirements/Themes Discriminability)

## Metadata
- **Epic**: Local-LLM Drafting Pipeline (see `docs/reports/local-llm-builder-architecture-options.md`)
- **Status**: Round 1 (the whole diagnostic) complete, 2026-07-14. Finding **(a)**: profiles are
  measurably too generic, `keywords`' alphabetical selection is the dominant driver (universal across
  13/13 companies, cleanly isolated in the ranking-impact spike), `requirements`' boilerplate-capture is a
  real secondary, JD-layout-dependent contributor. Full evidence and per-company tables in
  `docs/spec/08-implementation/CR-065-jd-profile-extraction-diagnostic-tracker.md`'s "Round 1 results" and
  Session Handoff. No fix designed here (out of scope by design) — next step (a hypothetical CR-066) is
  gated on Jason's review of this finding.
- **Date**: 2026-07-14
- **Source**: Direct follow-up to CR-064 (`docs/spec/05-change-requests/CR-064-claim-score-formula-rework.md`
  + tracker `docs/spec/08-implementation/CR-064-claim-score-formula-rework-tracker.md`), closed
  `closed_partial` 2026-07-14. CR-064 implemented and measured three independently-designed, individually
  hand-verified-correct scoring-formula mechanisms inside `score_claim_for_jd` (dedup, IDF-style rarity
  weighting, a DCG breadth dampener) across 5 rounds. None moved the CR's own target metric:
  `ACC-105-EXECUTION`'s cross-JD top-5 over-representation stayed at **10/14 top-5 appearances**, same
  count and same company membership, before and after all three mechanisms, on the fullest measurement
  the CR ever achieved. Jason's decision at close-out was to stop chasing this defect inside
  `score_claim_for_jd`'s aggregation arithmetic and redirect investigation one layer upstream, to the
  JD-profile extraction step that feeds it — a candidate CR-063 flagged in passing (see below) but never
  root-caused with a targeted, direct test of the extraction step's own output quality.

## Problem
`scripts/jd_tailoring.py:build_jd_profile_deterministic` (lines 124-153) is what turns a raw
`Original_JD.txt` into the `JdProfile` (`.priority_themes`, `.requirements`, `.keywords`) that
`score_claim_for_jd` scores every claim against. Three CRs' worth of downstream ranking-arithmetic work
(CR-063's `THEME_KEYWORDS` rounds, CR-064's dedup/rarity/dampener rounds) have all assumed this input is
adequately discriminating between JDs and focused entirely on what happens to it afterward. That
assumption has never been directly tested. Two pieces of indirect evidence exist, both inconclusive on
their own:

1. **CR-063's Final round found `jd_profile_mode="llm"` produces byte-identical top-5 claim rankings to
   the deterministic path on 3 worst-performing JDs, even when the LLM extracted a theme (`"AI"` for
   Ontra) the keyword table had missed entirely.** This was read at the time as proof the bottleneck is
   downstream of profile quality, in the ranking arithmetic — and CR-064's five rounds bear that out for
   the *ranking* step specifically. But that comparison never checked whether the *deterministic*
   profile's `keywords`/`requirements` fields (as opposed to `priority_themes`, the only field
   `measure_theme_extraction.py` actually logs) are themselves generic or mis-targeted; it only compared
   final rankings, which CR-064 has since shown don't move much regardless of what feeds them.
2. **Reading `build_jd_profile_deterministic` directly this session surfaced two concrete, code-level
   candidates that have never been measured, only now noticed:**
   - `keywords` (line 140): `sorted(w for w in words if w not in {...5 stopwords...})[:12]` — the top 12
     JD words of length ≥5 are selected by **alphabetical order**, not frequency, position, or relevance
     to any theme. Alphabetical truncation has no reason to correlate with what a JD is actually about;
     it will systematically favor whatever generic-vocabulary words happen to sort early, the same
     failure shape (favor common words that show up everywhere) CR-063/CR-064 diagnosed at the ranking
     layer, but potentially happening a step earlier, at extraction.
   - `requirements` (lines 132-137): built by scanning `jd_text.splitlines()` — the **entire raw JD**, in
     document order — for the first 6 lines between 20-120 characters that start alphanumeric. It does
     **not** call `extract_req_section()` (lines 100-116), a function that exists in this same file for
     exactly this purpose (isolating the requirements/qualifications subsection) and is actively used
     elsewhere (`local_draft_stages.py:1229`, `resume_rubric.py:49`). Depending on a given JD's layout,
     `build_jd_profile_deterministic`'s `requirements` field may be capturing "About the company" or
     "About the role" boilerplate paragraphs instead of actual requirements, simply because those often
     appear earlier in the document than the requirements section.

Neither of these has been measured against real JDs. Both are plausible, both are cheap to check, and
CR-063/CR-064's own governing discipline — measure before fixing, one hypothesis at a time — applies here
exactly as it did to `THEME_KEYWORDS` and `score_claim_for_jd`.

**A third, load-bearing complication found this session, not previously documented anywhere:** the
eval-set data source has degraded further since CR-064 closed. `data/submissions/` (the live,
Google-Drive-synced location CR-063/CR-064 originally measured against) currently contains only 2 of the
16 eval-set companies' `Original_JD.txt` (`sailpoint`, plus `test_co`, which isn't in the eval set at
all) — worse than CR-064 Round 5's already-alarming 7/16. `data/archive/submissions/` (which CR-064's QA
reviewer used at close-out as a more stable source, reconstructing a "14-company set including
sailpoint/group_1001") currently has **13 of the 16** eval-set companies present (`cresta`, `sailpoint`,
`group_1001`, `onestream_software`, `buyers_edge_platform`, `ontra`, `remote`, `covideo`, `datagrail`,
`mytime`, `pointclickcare`, `redox`, `lumos` — missing `tilt`, `par`, `parkingpass_com`). This CR should
source from `data/archive/submissions/` and treat 13/16 as the working sample, per the precedent QA
already set, rather than attempt to restore the missing 3 or wait on the live sync — see Out of Scope.

## Decision
Run a diagnostic-only phase — no fix, no code change to the extraction or scoring path — that directly
measures whether `build_jd_profile_deterministic`'s output is too generic/non-discriminating to support
correct downstream claim ranking, and if so, isolates which of its three fields (or which specific
mechanism inside a field) is responsible.

1. **Instrument, don't modify.** Write a new standalone script (same precedent as CR-063's
   `measure_semantic_rerank.py` — a parallel measurement tool, not a change to `jd_tailoring.py` or any
   production call path) that, for each of the 13 available eval-set companies (source:
   `data/archive/submissions/{slug}/Original_JD.txt`), calls `build_jd_profile_deterministic(jd_text)`
   and logs the full profile — `priority_themes`, `requirements`, AND `keywords` together. (
   `measure_theme_extraction.py` already logs `priority_themes` per company at line 78/87 but never
   `requirements` or `keywords` — this is the concrete gap in existing instrumentation that motivates a
   new script rather than reusing the old one as-is.)
2. **Hand-review against ground truth.** For each of the 13 companies, compare the logged
   `priority_themes`/`requirements`/`keywords` against that company's "Real JD themes (human-verified)"
   column in `docs/reports/jd-theme-claim-eval-set.md`. Record, per company, a plain judgment: does the
   extracted profile contain enough of the real theme(s) to plausibly support correct downstream ranking,
   or is it missing, diluted by generic terms, or actively wrong (e.g. requirements field capturing
   boilerplate instead of real requirements)?
3. **Directly test the two concrete candidate mechanisms named in Problem, not just eyeball the output:**
   - **Keywords-alphabetical-truncation test:** for a sample of at least 5 of the 13 companies (chosen to
     include at least 2 where CR-064's close-out data showed `ACC-105-EXECUTION` over-representation and
     at least 2 where an under-scoring rare-match claim like `ACC-401-AITOOLS`/`ACC-204` should have
     surfaced but didn't), compute what `keywords` would be if selected by raw in-JD frequency instead of
     alphabetical order, using the same length-≥5, same-stopword-filter, same `[:12]` cutoff as the
     current code — a same-shape comparison, changing only the sort key. Diff the two 12-word lists per
     company and record whether the alphabetical version is measurably discarding words that appear in
     that company's ground-truth theme description and the frequency version would have kept.
   - **Requirements-section test:** for the same sample, run the JD text through the existing
     `extract_req_section()` and compare its output to what `build_jd_profile_deterministic`'s current
     line-scan actually captured as `requirements`. Record whether the current code's `requirements` field
     is capturing lines from inside the true requirements section, or from earlier in the document (About
     Us / role summary / company boilerplate).
   - **Ranking-impact spike (extended scope, resolved from Open Question 2 — Jason, 2026-07-14):** the two
     tests above stop at diffing the *inputs*; this bullet closes the loop by measuring whether a corrected
     profile actually changes the *ranking output* — the real question one level upstream of CR-064's
     dead-end. For the same ≥5-company sample, the standalone script constructs a second, *corrected*
     `JdProfile` object in-script — identical `priority_themes` to the current deterministic profile (themes
     are not one of the two candidate defects; CR-063 already worked that field), but with `keywords` set to
     the frequency-sorted list from the keywords test above and `requirements` set to the
     `extract_req_section()`-scoped, same-line-scan list from the requirements test above — then calls the
     **already-shipped, unmodified** `score_all_claims(corrected_profile, catalog, jd_text)` and compares
     the resulting ranking against `score_all_claims(current_profile, catalog, jd_text)`. Report, per
     company, `ACC-105-EXECUTION`'s rank and top-5 membership under both profiles, with the actual
     before/after rank numbers. This is the measurement that tells us whether the extraction defects (if
     any) are even load-bearing on the metric CR-063/CR-064 spent three CRs chasing — a corrected profile
     that leaves `ACC-105-EXECUTION`'s rank unchanged points at finding (b), one that moves it points at
     finding (a). It is still measurement-only: the corrected profile is built and scored inside the
     standalone script; `build_jd_profile_deterministic` and `score_claim_for_jd` in `jd_tailoring.py` are
     not modified.
4. **Write an explicit, evidence-backed finding — one of three, not a hedge between them:**
   - **(a) Profiles are measurably too generic/non-discriminating**, with a specific attribution to which
     field(s) — `keywords`' alphabetical selection, `requirements`' section-scoping miss, `priority_themes`'
     `THEME_KEYWORDS` coverage (already partially addressed by CR-063, re-confirm rather than re-litigate),
     or an interaction between them — is the dominant driver, backed by the per-company comparisons above.
   - **(b) Profiles are adequately discriminating** for the 13 measured companies, and the defect
     responsible for `ACC-105-EXECUTION`'s over-representation must live somewhere CR-063/CR-064 haven't
     yet tested — the leading untested candidate, per CR-063 Round 2's own flagged-but-never-actioned
     finding, is `ACC-105-EXECUTION`'s own tags/body text in `master_claims.json` having unusually broad
     generic overlap with other claims' tag vocabulary (a catalog-content issue, not a code issue).
   - **(c) Inconclusive** given the 13/16 (not 16/16) sample and/or other data limitations found during
     the work, with a specific statement of what data or measurement would be needed to resolve it.
5. **No code changes to `scripts/jd_tailoring.py`'s `build_jd_profile_deterministic`, `build_jd_profile`,
   `extract_req_section`, or `score_claim_for_jd`, and no edits to `master_claims.json`, in this phase.**
   This is measurement and a written finding only. Whether and how to fix anything this phase surfaces is
   a separate, future decision (a hypothetical CR-066), gated on Jason reviewing this phase's finding —
   same two-step discipline CR-064's Round 1 (design, gated) → Round 2+ (implementation, gated on Round 1
   approval) used, applied one level earlier: diagnose (this CR), gated review, then decide whether to
   design a fix at all.

   **Scope clarification for the extended ranking-impact spike (Open Question 2, resolved 2026-07-14):**
   the spike constructing a *corrected* `JdProfile` and re-running ranking (Decision item 3, third bullet)
   does NOT violate this constraint. The "corrected" profile is built as a plain `JdProfile(...)` instance
   *inside the standalone measurement script* — the frequency-sort and `extract_req_section()`-scoping
   logic lives in the script, not in `jd_tailoring.py`. The script imports and calls the production
   `JdProfile` dataclass, `build_jd_profile_deterministic`, `extract_req_section`, `score_all_claims`, and
   `score_claim_for_jd` **exactly as they ship today**, passing them the corrected profile object as data.
   No production function's body is altered, no default pipeline path changes behavior, and
   `git diff --stat` at close-out must still show zero lines changed in `scripts/jd_tailoring.py`. This is
   the same "parallel measurement tool, production code untouched" pattern `measure_semantic_rerank.py`
   already established — that script likewise imports `score_claim_for_jd` and layers a comparison on top
   without modifying it.
6. **Follow the exact checkpointing/round protocol CR-063/CR-064 used**: write a tracker doc
   (`docs/spec/08-implementation/CR-065-jd-profile-extraction-diagnostic-tracker.md`) with the plan as
   checkboxes before executing, check off and log real findings as you go (not reconstructed from memory
   at the end), stop at clean boundaries, and fill in a Session Handoff block before ending any session.

## Acceptance Criteria
- A new standalone measurement script exists (e.g.
  `scripts/measure_jd_profile_extraction.py`) that logs `priority_themes`, `requirements`, and `keywords`
  together for all 13 available eval-set companies, sourced from `data/archive/submissions/`. It is not
  wired into any production pipeline path.
- A per-company hand-review table exists (in the tracker doc) comparing extracted `keywords`/
  `requirements`/`priority_themes` against `docs/reports/jd-theme-claim-eval-set.md`'s human-verified
  themes for all 13 companies — not a subset, not a summary without the underlying per-company detail.
- The alphabetical-vs-frequency `keywords` comparison (Decision item 3, first bullet) is run and logged
  for at least 5 companies with the specific word-list diffs shown, not just a qualitative impression.
- The `extract_req_section()`-vs-current-`requirements`-scan comparison (Decision item 3, second bullet)
  is run and logged for the same sample, with the actual captured line(s) shown for both methods per
  company.
- The ranking-impact spike (Decision item 3, third bullet) is run for the same ≥5-company sample and
  reports, per company, whether `ACC-105-EXECUTION`'s rank and top-5 membership differ between the current
  deterministic profile and the corrected profile (frequency-sorted keywords +
  `extract_req_section()`-scoped requirements), with the actual before/after rank numbers shown — not a
  qualitative "changed / didn't change" summary. The corrected `JdProfile` is constructed inside the
  standalone script and scored via the unmodified `score_all_claims`/`score_claim_for_jd`; `git diff --stat`
  at close-out still shows zero lines changed in `scripts/jd_tailoring.py`.
- A single, explicit finding — (a), (b), or (c) as defined in Decision item 4 — is written, with the
  evidence it rests on cited by company and by the specific comparison that produced it. A finding that
  hedges between (a) and (b) without picking one, or that asserts (a) without naming which field is
  responsible, does not satisfy this criterion.
- Zero changes to `scripts/jd_tailoring.py`, `scripts/score_claim_for_jd`'s call sites, or
  `data/master_claims.json`. Confirm via `git diff --stat` at close-out, same verification style
  CR-064's Close-out section used.
- Full `scripts/` pytest suite (`python -m pytest -q --ignore=test_domain_gate.py
  --ignore=test_fit_policy.py --ignore=test_llm.py`) shows the same pass/fail/skip counts before and
  after this CR's work, since no production code changes — a mismatch here means something outside this
  CR's intended scope was touched and needs explaining before close-out.

## Out of Scope
- **Any fix to `build_jd_profile_deterministic`, `extract_req_section`, `THEME_KEYWORDS`, or
  `score_claim_for_jd`.** This is diagnosis only. If finding (a) is reached, designing the actual fix is a
  separate, future CR gated on Jason's review of this CR's finding — not an automatic next round of this
  same CR. Note: the ranking-impact spike (Decision item 3, third bullet) is NOT a fix — it constructs a
  corrected `JdProfile` as *data* inside the standalone measurement script and scores it through the
  unmodified production functions. No production code is changed; it measures what a fix *would* buy,
  which is precisely the input to the gated fix/no-fix decision above.
- **Editing `master_claims.json` claim tags or bodies** (e.g. investigating or tightening
  `ACC-105-EXECUTION`'s own tag breadth, which finding (b)'s leading candidate points at) — this is
  measurement-and-finding only; any catalog edit requires Jason's sign-off as its own explicit follow-up,
  same rule CR-063/CR-064 both operated under.
- **Reopening embeddings-based semantic re-ranking or broadening the `jd_profile_mode="llm"` pilot as a
  fix.** CR-063's Final round already ruled both out for the *ranking* question with real measured data.
  If this CR's finding is (a) — the deterministic *extraction* step itself is the defect — LLM-mode
  profiling becomes a legitimately different question (extraction quality, not ranking quality) and could
  become relevant again, but only as a scoped decision in a future CR, not something to pilot inside this
  diagnostic phase.
- **Retuning `cover_claim_picker.py`'s flat additive bonuses.** Still an open, Jason-gated item deferred
  from CR-064's close-out (2 known pytest regressions); unrelated to this CR's question and not addressed
  here.
- **Resolving the `data/submissions/` eval-set data-instability infrastructure problem** (restoring the
  Google Drive sync, pausing it, or snapshotting a permanent frozen eval copy). This CR works around it by
  sourcing from `data/archive/submissions/` and accepting the 13/16 sample; fixing the underlying sync
  issue is a separate operational task, flagged again here as still open (first flagged in CR-064's
  Round 5 Session Handoff) but not this CR's job.
- **Restoring the 3 missing companies (`tilt`, `par`, `parkingpass_com`)** to reach a full 16-company
  sample before starting. Proceeding on the 13 available, per the CR-064 Round 5 QA precedent of working
  with the data actually present rather than pausing — see Open Questions for the explicit flag on this
  choice.

## Open Questions
1. **Eval-set sample size.** This CR proceeds on the 13 of 16 companies available in
   `data/archive/submissions/` rather than pausing to restore `tilt`/`par`/`parkingpass_com`. This mirrors
   the precedent CR-064's Round 5 already set (measuring against whatever's actually present, logged
   honestly as a caveat) rather than a fresh decision — flagging in case Jason wants the missing 3
   restored first for a cleaner measurement before this CR starts.

   **RESOLVED (Jason, 2026-07-14): proceed now on the 13 companies present in `data/archive/submissions/`.
   Do not wait on `tilt`/`par`/`parkingpass_com` archiving.** The 13/16 sample is the working set; log the
   3 missing companies as a caveat on the finding, same as CR-064 Round 5 did, rather than pausing. This
   is no longer an open question.
2. **Whether Phase 1 should touch fix candidates even informally.** Decision item 3 asks for a same-shape
   *comparison* (alphabetical vs. frequency keyword selection; current requirements-scan vs.
   `extract_req_section()`) as a measurement, not a proposed fix — I've scoped it as "diff and report,"
   not "implement and re-measure ranking impact." If Jason wants this phase to go one step further and
   actually re-run `score_claim_for_jd`/`measure_theme_extraction.py`-style ranking with a corrected
   profile as a quick spike (still without touching production code — a parallel script, same as the
   comparison itself), that's a larger scope than what's written here and should be an explicit decision,
   not an assumption I make mid-work.

   **RESOLVED (Jason, 2026-07-14): extend Phase 1 beyond diff-and-report to include the ranking-impact
   spike.** The diagnostic does NOT stop at diffing keywords/requirements and reporting; it ALSO re-runs
   `score_claim_for_jd`-style ranking (via `score_all_claims`) using a *corrected* profile (frequency-sorted
   keywords + `extract_req_section()`-scoped requirements) for the ≥5-company sample, and reports whether
   `ACC-105-EXECUTION`'s rank and top-5 membership actually change with a corrected profile — the real
   question this whole investigation exists to answer, one level upstream of CR-064's dead-end. This stays
   a parallel/standalone script that constructs the corrected `JdProfile` object *inside the script* and
   calls the already-shipped, unmodified `score_all_claims`/`score_claim_for_jd` against it. The
   "zero changes to `jd_tailoring.py`" constraint (Acceptance Criteria + Out of Scope) still holds — see
   the updated Decision items 3 and 5. This is now in scope.
3. **What happens on finding (b).** If profiles turn out to be adequately discriminating and the defect is
   elsewhere, the leading untested candidate is `ACC-105-EXECUTION`'s own tag/body breadth in
   `master_claims.json` (CR-063 Round 2 flagged this and never actioned it, same as this CR's own
   Out-of-Scope item). Does Jason want that to become the next diagnostic thread automatically, or does he
   want to reassess whether continuing to chase `ACC-105-EXECUTION`'s over-representation specifically is
   still worth a fourth investigation, given CR-063 and CR-064 combined represent a substantial amount of
   work already spent on this one metric without resolution.

   **RESOLVED (Jason, 2026-07-14): continue the investigation — "focus on JD extraction and work our way
   down the pipeline."** This CR is committed to, and is explicitly the *first* investigation phase of a
   pipeline-wide effort (extraction first, then whatever the finding points at next), not a one-off
   diagnostic. What happens after finding (a)/(b)/(c) is still gated on Jason reviewing this phase's
   written finding — but the sequence itself (keep working down the pipeline from extraction) is decided.
   The tracker's Session Handoff frames this CR as Investigation Phase 1 of that sequence.
