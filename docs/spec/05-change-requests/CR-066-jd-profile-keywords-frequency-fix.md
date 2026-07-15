# CR-066: JD-Profile `keywords` Fix — Alphabetical to Frequency-Sorted (`build_jd_profile_deterministic`)

## Metadata
- **Epic**: Local-LLM Drafting Pipeline (see `docs/reports/local-llm-builder-architecture-options.md`)
- **Status**: Not started — this is the handoff brief for the session that starts it
- **Date**: 2026-07-14
- **Source**: Direct follow-up to CR-065 (`docs/spec/05-change-requests/CR-065-jd-profile-extraction-diagnostic.md`
  + tracker `docs/spec/08-implementation/CR-065-jd-profile-extraction-diagnostic-tracker.md`), Round 1
  complete 2026-07-14, finding **(a)**: JD profiles are measurably too generic, with the `keywords`
  field's alphabetical selection as the dominant, universal driver (13/13 companies in Part B) and
  `requirements`' boilerplate-capture as a real but secondary, JD-layout-dependent contributor (4/13,
  see Out of Scope). Both Security Review and QA independently reproduced the load-bearing numbers
  against real code (`pipeline-log.md`, "Security Review — CR-065 Round 1" and "QA — CR-065 Round 1").
- **This is a PRODUCTION code change**, unlike CR-063/064/065, which were all diagnostic-only against
  standalone scripts. This CR edits `scripts/jd_tailoring.py:build_jd_profile_deterministic` directly —
  a function with real call sites in the live drafting pipeline (`local_draft_stages.py`,
  `cover_jd_needs.py`, `cover_letter_compiler.py`, `cover_plan_builder.py`, plus test/measurement
  scripts). That changes the risk profile from CR-065: this CR requires re-running the full CR-064-era
  guardrail set (pytest baseline, cover-letter-side hand-check, a full eval-set re-measurement), not
  just a `git diff --stat` check that nothing changed.

## Global Constraints

(Pulled verbatim from `docs/spec/00-project-constitution.md` — every downstream role inherits this block
unmodified.)

### Goals
- `GOAL-001`: Automate multi-source job scouting (BuiltIn, APIs, OpenPostings; LinkedIn decommissioned per CR-010).
- `GOAL-002`: Implement deterministic fit scoring to minimize LLM token waste.
- `GOAL-003`: Generate application materials (Resume, Cover Letter) grounded in verified `workExperience.md`.
- `GOAL-004`: Maintain absolute data privacy by running the core engine on `localhost`.
- `GOAL-005`: Provide a real-time dashboard for monitoring the automation pipeline.

### Non-goals
- `NG-001`: Cloud hosting or multi-user access (privacy violation).
- `NG-002`: Direct ATS submission (requires human-in-the-loop for safety).
- `NG-003`: "General purpose" career coaching (focused strictly on PM roles).

### Global quality bar
- Performance: Sub-second UI response; sub-15-minute end-to-end job evaluation.
- Accessibility: Standard WCAG compliance for internal use.
- Security: Zero-knowledge architecture; API keys restricted to local `.env`.
- Reliability: 100% "Context Firewall" success between job iterations.
- Maintainability: SDD-compliant code with full requirement traceability.
- Documentation: Spec-first workflow enforced for all changes.

### Agent constraints
- Agents must update specs before code.
- Agents must cite requirement IDs in tasks and implementation summaries.
- Agents must preserve existing accepted behavior unless a change request says otherwise.
- Agents must record open questions instead of guessing when the decision changes product behavior.

## Problem
`build_jd_profile_deterministic` (`scripts/jd_tailoring.py:124-153`) builds the `.keywords` field like
this (lines 139-140, unmodified as of this writing):

```python
words = set(re.findall(r"[a-z]{5,}", jd_lower))
keywords = sorted(w for w in words if w not in {"about", "their", "would", "should", "other"})[:12]
```

The top-12 JD words of length >=5 are selected by **alphabetical order** — `sorted()` on a `set`, which
also discards frequency information entirely. This has no relationship to what a JD is actually about;
it systematically favors whatever generic vocabulary happens to sort early (`ability`, `across`,
`adoption`, `background`) over the JD's own defining nouns (`platform`, `identity`, `healthcare`,
`dealership`, `fhir`), which only appear if they happen to fall in the alphabetical top 12.

CR-065 Round 1 measured this directly, not hypothetically:
- **13/13 companies (Part B):** every single company's alphabetical `keywords` output is dominated by
  generic function/adjective words carrying near-zero company-specific signal.
- **6/6 sampled companies (Part C):** a same-shape frequency-sorted comparison (same length>=5 filter,
  same 5-stopword filter, same `_jd_body_for_themes()` source text, same `[:12]` cutoff, only the sort
  key changed) recovers ground-truth-relevant JD-defining nouns the alphabetical version discards, in
  every sampled company. Sharpest case: SailPoint's frequency list recovers `identity`, `security`,
  `cloud`, `certification` — the literal words used in that company's own human-verified ground-truth
  theme description — none of which the alphabetical output contains at all.
- **The ranking-impact spike (Part E, the load-bearing measurement):** scoring a corrected `JdProfile`
  (same themes, frequency-sorted keywords, section-scoped requirements) through the unmodified,
  shipped `score_all_claims()` moves `ACC-105-EXECUTION`'s rank materially in 4/6 sampled companies,
  dropping it fully out of the top-5 in 2 (Redox: rank 3->6; DataGrail: rank 1->6). Because
  `requirements` was byte-identical (unchanged) in 5 of those 6 companies while rank still moved in 3 of
  those 5 (Redox, Covideo, DataGrail), the `keywords` field's alphabetical->frequency change alone is
  directly responsible for the bulk of the observed movement — this is a clean, isolated result, not
  confounded by the `requirements` field. This directly contradicts CR-064's five-round null result on
  the same metric, because CR-064 varied only the downstream ranking arithmetic, never the input profile.

Both the Part E load-bearing companies (Redox, DataGrail) and 5/6 Part C companies were independently
reproduced against real, unmodified code by both Security Review and QA the same day (`pipeline-log.md`,
"Security Review — CR-065 Round 1" and "QA — CR-065 Round 1"). One data caveat carries forward from
that verification pass: `data/archive/submissions/sailpoint/` was present during CR-065 Round 1's
execution (its rows are real, measured output) but was confirmed **gone from disk** by QA's
verification pass hours later the same day. **Whoever executes this CR must re-run an `ls` /
`available_eval_set()`-style check against `data/archive/submissions/` at the start of work and record
the actual company count and membership found** — do not assume 13/13, and do not assume SailPoint is
present, without checking first.

## Decision
Change `build_jd_profile_deterministic`'s `keywords` selection from alphabetical to descending
in-JD-frequency, using the exact mechanism CR-065's tested comparison already validated
(`scripts/measure_jd_profile_extraction.py:96-108`, `keywords_frequency_sorted()`), moved into
production:

```python
from collections import Counter   # new import at top of jd_tailoring.py

# inside build_jd_profile_deterministic, replacing lines 139-140:
tokens = re.findall(r"[a-z]{5,}", jd_lower)
counts = Counter(t for t in tokens if t not in {"about", "their", "would", "should", "other"})
keywords = [w for w, _c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]
```

1. **Only the `keywords` field's sort mechanism changes.** Same length->=5 regex (`r"[a-z]{5,}"`), same
   5-word stopword set, same `_jd_body_for_themes(jd_text)` source text (the 72%-of-JD body the function
   already tokenizes over), same `[:12]` cutoff, same tie-break-alphabetically-for-determinism rule
   CR-065's tested version used. `priority_themes` and `requirements` are **not** touched by this CR (see
   Out of Scope).
2. **`build_jd_profile_deterministic`'s signature and return type are unchanged** —
   `(jd_text: str, fit_summary: str = "") -> JdProfile`. No call site requires any change. Confirm this
   against all real call sites before closing: `local_draft_stages.py:377`, `cover_jd_needs.py:397`,
   `cover_letter_compiler.py:129`, `cover_plan_builder.py:50`, plus the test/measurement files
   (`measure_semantic_rerank.py`, `measure_theme_extraction.py`, `smoke_draft_compiler.py`,
   `test_ai_signal_routing.py`, `test_cover_claim_picker.py`) that call it directly.
3. **Re-confirm the eval-set company count and membership at execution time**, before measuring
   anything. CR-065's Round 1 measured against 13/16 eval-set companies; QA's verification pass the same
   day found SailPoint had since gone missing (12/13). Log whatever the actual count is at the start of
   this CR's own work — do not carry forward "13/13" without re-checking.
4. **Re-run a full eval-set measurement, not just the 6-company Part C/E sample.** CR-065's Part C/E
   sample of 6 was deliberately chosen to demonstrate the mechanism cleanly with a manageable amount of
   hand review; this CR ships to production and needs the full available archive sample (12 or 13
   companies, per item 3) measured both for `ACC-105-EXECUTION`'s top-5 appearance count (the specific
   metric this CR targets) and for the broader should-surface aggregate hit rate
   (`measure_theme_extraction.py`'s `code_hits_top5` style accounting) so a regression on some other
   claim's correct surfacing does not slip through unmeasured. `scripts/measure_jd_profile_extraction.py`
   already has the needed comparison functions (`keywords_frequency_sorted`, `ranking_spike`) but only
   its `main()` runs Part A end-to-end today (QA's CR-065 finding: Parts C/D/E have no single-command
   entry point). Extend that script's `main()` (or add a `--full` mode) to run the frequency-keywords
   ranking spike across the full available sample and print the aggregate hit-rate accounting — this is
   the natural, minimal extension of an already-reviewed script, not new measurement infrastructure.
5. **Establish the pre-fix baseline on the same sample this CR will measure against, not an old number
   from a different sample.** Two numbers exist already and should both be cited for context, but neither
   is the correct apples-to-apples baseline for this CR's own re-run:
   - CR-064-era baseline (14-company `data/submissions/` set, now stale/unstable): 10/14.
   - CR-065 Part C's same-day live measurement against the full 13-company archive sample (current,
     unfixed code): **9/13**.
   Before implementing the fix, re-run the full-sample measurement in item 4 against the **current**
   (unfixed) code, using whatever company count item 3 confirms, and record that number as this CR's own
   pre-fix baseline. That is the number the post-fix acceptance criterion compares against.
6. **Cover-letter-side hand-check, per the CR-064-established discipline.** `keywords` also feeds
   `pick_cover_bullets`/`cover_claim_picker.py`'s `_proof_score` (both consume the same `JdProfile`
   `score_claim_for_jd` scores against). Hand-verify which claims get selected as cover-letter proof
   points, and their relative order, for at least 2-3 eval-set JDs before and after the fix — the same
   check CR-064's acceptance criteria required and that `measure_theme_extraction.py` alone does not
   exercise.
7. **New unit test(s) pinning the frequency-sort behavior directly** against
   `build_jd_profile_deterministic` (or an extracted keyword-selection helper, implementer's choice) —
   none currently exist that would catch a regression back to alphabetical sorting or a change to the
   stopword set/cutoff/length filter.
8. **Follow the same checkpointing/round protocol CR-063/064/065 used**: write a tracker doc
   (`docs/spec/08-implementation/CR-066-jd-profile-keywords-frequency-fix-tracker.md`) with the plan as
   checkboxes before executing, check off and log real before/after numbers as you go, stop at clean
   boundaries, fill in a Session Handoff block before ending any session.

## Acceptance Criteria
1. `build_jd_profile_deterministic`'s `keywords` field is computed by descending in-JD-frequency
   (ties broken alphabetically), replacing the current alphabetical `sorted(set(...))` selection, with
   the same length>=5 filter, same 5-word stopword set, same `_jd_body_for_themes()` source text, and
   same `[:12]` cutoff as today. No other field (`priority_themes`, `requirements`) changes.
2. `build_jd_profile_deterministic`'s signature (`(jd_text: str, fit_summary: str = "") -> JdProfile`)
   and all real call sites (listed in Decision item 2) require zero changes.
3. A full-sample eval-set measurement (all archive companies confirmed present at execution time, per
   Decision item 3 — 13 if SailPoint has returned, 12 if not, logged either way) shows
   `ACC-105-EXECUTION`'s top-5 appearance count drop from this CR's own logged pre-fix baseline
   (Decision item 5 — expected in the 9/13 range, exact number confirmed at execution time on the
   actual sample available).
4. The same full-sample measurement's aggregate should-surface hit-rate accounting
   (`code_hits_top5`-style, per company and in total) shows **zero regressions beyond what CR-065 already
   documented** — specifically, `ACC-105-EXECUTION` dropping out of top-5 for companies where it was an
   over-representation (expected, not a regression) is acceptable; any *other* claim that correctly
   surfaced in top-5 under the current profile and stops surfacing under the corrected profile, for a
   company where CR-065 did not already document that exact effect, must be logged and explained before
   this CR is considered done, not silently absorbed into "the fix worked."
5. Cover-letter-side proof-point selection (`pick_cover_bullets`/`_proof_score`) is hand-checked for at
   least 2-3 eval-set JDs before and after the fix, with the actual selected claims and their order
   logged for both, per Decision item 6.
6. Full `scripts/` pytest suite (`python -m pytest -q --ignore=test_domain_gate.py
   --ignore=test_fit_policy.py --ignore=test_llm.py`) shows the same pass/fail/skip counts as the
   CR-064/065 baseline (28 failed / 190 passed / 1 skipped as of 2026-07-14) plus any new tests added
   under Acceptance Criterion 7, all passing. Any count that differs beyond the new tests must be
   explained before close-out, not assumed benign.
7. At least one new unit test exists that directly pins the frequency-sort `keywords` behavior (would
   fail if the code reverted to alphabetical sorting, or if the stopword set/length filter/cutoff
   silently changed).
8. Zero changes to `priority_themes` construction, `extract_req_section()`, `THEME_KEYWORDS`,
   `score_claim_for_jd`, or `data/master_claims.json`. Confirm via `git diff --stat`, same verification
   style CR-064/065 used — the diff should show exactly the `keywords`-selection lines (and the new
   `Counter` import) changed in `scripts/jd_tailoring.py`, plus new test file(s) and the tracker/spec
   docs.
9. The eval-set company count and membership actually available at execution time is logged explicitly
   in the tracker (not assumed from CR-065's "13/13" language, which QA already found stale for
   SailPoint) — both the pre-fix and post-fix measurements must run against the same, named set of
   companies so the before/after comparison is apples-to-apples.

## Out of Scope
- **The `requirements`/`extract_req_section()` boilerplate-capture defect.** This is a distinct root
  cause from the `keywords` fix — CR-065 Part D found the tested fix (section-scoping the same line-scan
  through `extract_req_section()`) only resolved 1 of the 4 confirmed-broken companies (Cresta); Covideo
  and Ontra remain broken even after that correction, pointing at a second, compounding defect inside
  `extract_req_section()` itself (its own heading-regex not matching some JDs' heading styles, and the
  line-scan's 20-120-character window). **Explicit call: this is a separate CR (reserve CR-067), not
  bundled into this one.** It has not been diagnosed to the same rigor as `keywords` — the tested
  correction doesn't reliably work, which means the real fix (heading-regex coverage, the character-length
  window, or something else) hasn't been identified yet, only the fact that the current tested fix is
  insufficient. Bundling an unresolved, differently-rooted defect into this CR would also make it harder
  to cleanly attribute any regression this CR's own measurement (Acceptance Criterion 4) finds. This CR
  does not touch `extract_req_section()` or the `requirements` line-scan in any way.
- **The under-scoring `ACC-401-AITOOLS`/`ACC-204` problem.** CR-065's own ranking-impact spike found the
  corrected profile (frequency keywords + section-scoped requirements) did **not** pull these claims into
  the top-5 anywhere in its 6-company sample — they were False before correction and stayed False after,
  in every company where they were tracked. There is no measured evidence a `keywords` fix addresses this
  half of the original CR-063/CR-064 problem statement. Scoping a fix for it here would mean designing
  against an unmeasured hypothesis — the exact anti-pattern this session's CR-063->064->065 arc has been
  explicitly disciplined about avoiding. If this remains a priority after CR-066 ships, it needs its own
  diagnostic phase first, same as extraction did.
- **`priority_themes` / `THEME_KEYWORDS` / `THEME_KEYWORDS[:4]` truncation-order behavior.** CR-063's
  territory, already worked across three rounds there, re-confirmed-but-not-relitigated in CR-065 Part B.
  Not reopened here, even though CR-065's Part B note flagged a real SailPoint/Ontra truncation-order
  interaction — that is a `priority_themes` question, not a `keywords` question, and this CR's evidence
  base doesn't cover it.
- **Loosening or special-casing the `keywords` field's `[a-z]{5,}` length filter** to let short tokens
  like `AI`, `ML`, `UX` through. CR-065 flagged this as a structural limitation of any keywords-only fix
  (Part B note) but it was not tested, and loosening it changes the field's shape beyond what CR-065's
  tested comparison validated. Not part of this CR.
- **Any edit to `data/master_claims.json`** (claim tags, bodies, or `ACC-105-EXECUTION`'s own breadth) —
  this is a code-side extraction fix, not a catalog-content change. Any catalog edit requires Jason's
  explicit sign-off as its own separate follow-up, same rule CR-063/064/065 operated under.
- **Retuning `cover_claim_picker.py`'s flat additive bonuses.** Still the open, Jason-gated item deferred
  from CR-064's close-out; unrelated to this CR's fix and not addressed here.
- **Resolving the `data/submissions/`/`data/archive/submissions/` eval-set sync instability.** This CR
  works around it by re-confirming whatever company set is actually present at execution time (Decision
  item 3, Acceptance Criterion 9); fixing the underlying sync/archiving process is a separate operational
  task, flagged again here (first flagged CR-064 Round 5, repeated CR-065) but not this CR's job.

## Open Questions
CR-065's evidence for this specific fix is strong and cleanly isolated (universal in Part B, isolated
in 5/6 Part E companies), so this CR has genuinely few open design choices left — unlike CR-064 Round 1,
which had real unresolved architecture decisions. The two below are narrow and operational, not
architectural:

1. **Where the new unit test(s) required by Acceptance Criterion 7 should live** — directly against
   `build_jd_profile_deterministic`'s `keywords` output (simplest, matches how the function is actually
   called in production), or against an extracted, separately-testable keyword-selection helper function
   (marginally more refactoring, but keeps `build_jd_profile_deterministic` itself shorter). This is a
   normal implementation decision for whoever picks this up, not a product-behavior question — flagged
   here only so the tracker records the choice explicitly rather than it happening silently.
2. **Whether `scripts/measure_jd_profile_extraction.py` should be extended in place** (a `--full` mode
   or expanded `main()`, per Decision item 4 and QA's CR-065 finding that Parts C/D/E currently lack a
   single-command entry point) **or whether this CR's full-sample measurement should be a new, separate
   script** to avoid touching a script CR-065 already reviewed and signed off on. Either satisfies
   Acceptance Criteria 3/4; this is a minor implementation-sequencing choice, not gated on Jason.

Neither of these changes what ships or what the fix does — they are left to whoever executes this CR to
resolve and log, not blocking items for Jason.

## Traceability Mapping

| File | Action |
|------|--------|
| `scripts/jd_tailoring.py` | Add `from collections import Counter` import. Replace lines 139-140 (`keywords` selection) with frequency-sorted, alphabetically-tie-broken selection per Decision item 1. No other lines in this file change. |
| `scripts/measure_jd_profile_extraction.py` | Extend `main()` (or add a `--full` mode) to run the frequency-keywords ranking spike and aggregate hit-rate accounting across the full available archive sample, per Decision item 4 and Open Question 2. |
| `scripts/test_*.py` (new or existing, implementer's choice per Open Question 1) | Add unit test(s) pinning the frequency-sort `keywords` behavior, per Acceptance Criterion 7. |
| `docs/spec/08-implementation/CR-066-jd-profile-keywords-frequency-fix-tracker.md` | New tracker doc, same checkpointing/round protocol as CR-063/064/065, per Decision item 8. |
| `docs/spec/05-change-requests/README.md` | Update the CR-066 registry row's status as work proceeds (already added at scoping — see this CR's own registry row). |
