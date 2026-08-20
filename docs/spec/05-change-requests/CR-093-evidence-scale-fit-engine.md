---
status: in_progress
created: 2026-08-19
supersedes: CR-053 Epic 2 (structured_fit.py 5-criterion scorer), build_stage0_fit_gate.py's
  regex classification chain (_item_has_anchor, _is_unbridgeable_advanced_degree,
  _unbridgeable_domain_requirement, _get_hard_tool_pattern dispatch, _classify_single_clause,
  _split_compound_item)
related: data/fit_rubric_spec.html (the research/design spec this implements),
  data/fit_rubric_golden_set.json, scripts/check_fit_rubric_golden_set.py,
  scripts/fit_rubric_examples.py (self-healing plan infra this reuses)
---

# CR-093 — Evidence-Scale Fit Engine: Replace Regex Gate + 5-Criterion Scorer with a Unified Per-Requirement LLM Judgment

**Handoff doc.** Read this before touching Stage 0 fit-scoring code. This CR replaces two
separate mechanisms that currently decide job fit with one: a single LLM judgment call per
requirement line, scored 0-4 on the evidence scale from `data/fit_rubric_spec.html` §7, combined
via the deterministic weighted formula in §10-11.

## Why this exists (do not re-litigate without re-reading this)

The 2026-08-19 session's fit-rubric research (see
`docs/spec/08-implementation/SESSION-HANDOFF-2026-08-19-stage0-diagnosis-and-fit-rubric.md`)
found the regex-based gap classifier in `build_stage0_fit_gate.py` (`_item_has_anchor` and the
functions around it) is "keyword matching wearing a qualification-matching costume" — it checks
whether a claim tag appears near a phrase, not whether real evidence supports the requirement.
The spec designed a proper fix (§7-12) but did not implement it in code.

Investigating where to plug the fix in surfaced a second, related finding not written down
anywhere before this doc: **in live production runs, the regex-based `classify_gaps` chain
does not decide Tier 1/Tier 2 at all.** Since the 2026-08-19 score-driven-tier redesign, real
runs (`use_llm=True`) get their score from `structured_fit.evaluate_structured_fit()` — a
separate, coarser 5-criterion (`title_seniority_fit`, `pm_craft_overlap`, `team_structure_fit`,
`execution_depth`, `transition_potential`) yes/partial/no judgment — which overrides the
regex-derived tier in `build_stage0_fit_gate.py` Step 5.5. The regex chain only still matters for:
(a) the absolute degree/domain HARD-gap Skip (Step 5, never overridden by score), and (b) the
gap-based Tier 1/2 fallback used only in deterministic/offline mode. Jason, asked directly
whether to keep the regex layer as a fallback (per the spec's own §19 KEEP/MODIFY verdict) or
remove it outright: **"if the new system we are building will replace it then get rid of it,
regex wasn't working and we have been bypassing it completely either way."** Confirmed decision,
not a default — this doc exists so a future session doesn't reopen the fallback question.

**Net effect: this CR replaces both mechanisms** — the item-level regex classifier AND the
5-criterion holistic scorer — with one engine: a per-requirement 0-4 evidence judgment (spec §7),
gated first by hard-gate category (spec §9), combined by the weighted formula (spec §10-11).
Hard-gate detection (degree/domain/role-exclusion) moves from regex pattern-matching into the
same LLM call, instructed by system-prompt rules and few-shot examples drawn from the real
confirmed cases the regex used to hard-code (Bamboo Health's "master" false-positive, OneSource
Virtual's payroll-tax gate, the axos_bank/central_bank/accertify domain-alternative false
positives, the Decisiv Pendo/Amplitude alt-list case) — the hard-won lessons aren't lost, they
move from pattern code into judgment-call instructions and the golden set's few-shot bank.

**No regex fallback on LLM failure, by design.** A silent fallback to weaker logic is the
exact failure mode that produced the "every job scores ~60" bug this session started by
diagnosing (Ollama not auto-starting, silently degrading every call). If the evidence-scale
LLM call fails, Stage 0 must fail loud (raise `EvidenceClassificationError`, surfaced as
`WorkflowError`/CLI `ERROR`), never silently produce a plausible-looking wrong answer.

## Scope boundary — what does NOT change

- **`_get_hard_tool_pattern()` / `HARD_BLOCKED_TOOLS`** (the deny-list of tools Jason cannot
  honestly claim) stays. It's ground-truth data consumed by `build_authoring_packet.py` for a
  different purpose (excluding claim attachment to a line about a tool Jason doesn't have) —
  unrelated to gap/tier classification, out of scope here.
- Per spec §9's own table: **named tools never hard-gate** in the new engine either (same
  real-world conclusion the 2026-08-19 session already reached by hand: Bamboo Health's Tableau
  mention should never auto-Skip). The evidence-scale engine scores tool requirements 0-4 like
  any other item; only degree, named-regulated-domain-with-tenure, and role-category exclusion
  gate absolutely.
- `data/candidate_preferences.json` exclusion-zone checks (people management, 0-to-1, AI/ML
  ownership, revenue/billing) and the DB gate (`stage0_db_gate.py`) are untouched — those are
  independent of this engine and already run before it (Step 1-4 of `build_stage0_fit_gate`).

---

## Epic 1 — Core Evidence-Scale Classifier Module

**Goal:** one function, `classify_requirement()`, that takes a JD requirement line + candidate
ground truth and returns a `gate`/`gap_source`/`evidence_level`/`confidence`/`reasoning` judgment
via a single LLM call — spec §7-9 implemented as code for the first time.

- [x] **Story 1.1 — Data model + module.** `scripts/evidence_scale.py`: `EvidenceJudgment`
      dataclass (gate, gap_source, evidence_level 0-4, confidence, reasoning), with a
      `to_legacy_dict()` / `gap_class` / `gap` / `domain_soft` property bridge so
      `build_stage0_fit_gate.py`'s existing `classify_gaps()`/`_determine_tier()` downstream
      consumers need zero changes on wiring (Epic 2).
- [x] **Story 1.2 — Prompt + schema.** System prompt encodes spec §7's five behavioral levels,
      §8's forbidden-inference list, §9's gate-category rules — instructions plus retrieval-
      augmented few-shot (reuses `fit_rubric_examples.retrieve_examples()`, the self-healing
      plan infra already built 2026-08-19) drawn from the golden set's confirmed cases, across
      all categories, not just `internal_term`.
- [x] **Story 1.3 — Loud failure, no fallback.** `EvidenceClassificationError` raised (not
      caught internally) on missing/malformed LLM output — see "No regex fallback" above.
- [x] **Story 1.4 — Validate against the golden set.** Ran live against local Ollama
      (llama3.1:8b-instruct-q5_K_M, this machine's selected primary) across 16 of the 21 golden
      entries, spanning every category: domain_gate HARD (domain-001/002/003) and its
      false-positive guards (domain-fp-001/002/003), degree_gate HARD (degree-001/002/003) and
      its false-positive guard (degree-fp-001), tool_nongate (tool-001/002), clean_evidence_match
      (clean-001/002), preferred_nongate (preferred-001/002), hedge_nongate (hedge-001).
      **16/16 correct on gate + gap_source; evidence_level matched or was within 1 of the golden
      value in every case** (the one off-by-one, clean-001, was caused by a bad evidence-context
      choice below, not the classifier's judgment — fixed and re-verified as exact).
    - **Two real bugs found and fixed during validation, not just confirmed passing:**
      (1) The model initially emitted `gate="HARD", gap_source="tool"` for tool-002 despite an
      explicit system-prompt instruction that tools never gate — a local 7-8B model doesn't
      follow that rule with full reliability at temp 0. Since `gap_source="tool"` paired with
      `gate="HARD"` is invalid by construction (not in `_GATE_SOURCES`), added a narrow
      deterministic coercion (gate→"NONE") for exactly this combination rather than treating it
      as a hard failure — this isn't a fallback guess, the correction is already true by the
      schema's own design. (2) `WORK_EXP_SUMMARY_FILE` (the evidence context originally passed)
      turned out to be a meta-description of the document's structure, not real accomplishment
      content — useless as evidence, and the cause of clean-001 under-scoring (level 2 vs
      expected 3). Switched to the real `WORK_EXP_FILE`, truncated to 8000 chars as a **known
      placeholder** — see Epic 2 Story 2.1 for the real fix (retrieval-scoped evidence context
      per requirement, not a blind prefix of a 70K+ char document).

---

## Epic 2 — Weighted Formula + Wiring (BUILT, NOT PRESSURE-TESTED)

Built end-to-end and smoke-tested against real archive JDs (Story 2.3's note). Jason's explicit
instruction after Epic 1: **"build everything, we will pressure test after"** — so this epic
was completed as a build pass, not validated against the golden set or archive corpus the way
Epic 3 calls for. Two known, deliberately-deferred gaps going into pressure-testing: the
evidence-context truncation placeholder (Story 2.1) and the unrewritten `test_build_stage0_fit_gate.py`
coverage (Story 2.7) — both explicitly flagged in their stories below, not silently skipped.

**Goal:** replace `structured_fit.compute_fit_report()`'s 5-criterion math with the spec
§10-11 weighted formula over real per-requirement evidence judgments, and replace
`build_stage0_fit_gate.py`'s `_classify_one_item`/`classify_gaps` internals to call
`evidence_scale.classify_requirement()` instead of the regex chain.

- [~] **Story 2.1 — Extract structured requirements — deliberately simplified, not the full
      spec.** Required/preferred item lists already existed from Stage 0's section parsing;
      reused as-is. **Did NOT build** `requirement_type` sub-classification (Core Duty / Named
      Tool-Skill / Named Domain / General Knowledge) from spec §5-6 — the weight table (Story
      2.2) assigns the same weight (3) to every required-bucket subtype regardless, so the only
      distinction that actually changes the formula's output is required-vs-preferred bucket,
      which was already available. If a future story adds the repetition/hedge modifiers (both
      still unimplemented, see Story 2.2), sub-type classification becomes necessary and this
      story reopens. **Also did NOT fix the evidence-context sizing placeholder**: every call
      still sends a blind 8000-char prefix of the 73K-char `WORK_EXP_FILE`, repeated on every one
      of a JD's 5-10 calls — confirmed still causing real misses live (Instructure: Jason's real
      Pendo/Amplitude analytics experience, ACC-117/118, didn't surface because it isn't in the
      first 8000 characters). Real fix is retrieval-scoped context per requirement line (same
      token-overlap pattern as `fit_rubric_examples.py`'s few-shot retrieval) — flagged as the
      single highest-value remaining accuracy fix, explicit pressure-test-phase work.
- [x] **Story 2.2 — Weighted formula.** `evidence_scale.compute_fit_score()` implements
      `RawFit = 100 × Σ(wᵢ×sᵢ×cᵢ)/Σwᵢ` (spec §10-11): required items weight 3, preferred weight
      1, confidence multipliers 1.00/0.85/0.65 (spec §12), hard-gate items short-circuit to a
      `disqualified` result before the formula runs at all (spec §11's "hard gates run first,
      entirely outside this computation"). **NOT implemented**: the repetition (+1, capped) and
      hedge-language (-1) weight modifiers — both explicitly flagged in the spec itself as design
      inference awaiting calibration, not settled numbers, so deferred rather than guessed at.
- [x] **Story 2.3 — Wire into `build_stage0_fit_gate.py`.** `_classify_one_item`'s body now
      calls `evidence_scale.classify_requirement()`; `classify_gaps()`/`_determine_tier()`'s
      downstream contract unchanged (Epic 1 Story 1.1's bridge properties did their job — zero
      changes needed in `_determine_tier` or any output-building code past Step 5.5).
      `work_exp` now loaded once at Step 4 (moved up from the old Step 5.5) and threaded through
      `classify_gaps(..., work_exp=...)`. Smoke-tested live end-to-end against two real archive
      JDs (1uphealth, Instructure) — ran clean, correct Skip/Tier decisions, no crashes.
- [x] **Story 2.4 — Replace `structured_fit.evaluate_structured_fit()`'s call site** in Step 5.5
      with `compute_fit_score(classified_required, classified_preferred)` — reads the evidence
      judgments Step 4 already produced, **no second LLM pass**. `structured_fit.py` itself is
      untouched (see Story 2.5's correction below) — only this one call site changed. Also fixed
      two now-dead branches this created: the `skip_reason` "Hard gap(s)" message now cites
      `compute_fit_score`'s own `disqualifying_item` directly instead of re-deriving from
      `flagged_gaps`, and added a defensive coercion (`evidence_scale.py`) forcing
      `gate="NONE"` whenever `is_required=False`, matching spec §9's "Preferred bucket never
      gates" — found live that the system-prompt instruction alone didn't reliably hold on a
      local 7-8B model.
- [x] **Story 2.5 — Remove the superseded regex.** Deleted `_item_has_anchor`,
      `_is_unbridgeable_advanced_degree`, `_unbridgeable_domain_requirement`,
      `_classify_single_clause`, `_split_compound_item`, `_is_soft_familiarity_hedge`,
      `_alt_list_anchor`, `_unanchored_domain_qualifiers`, `_GENERIC_TAG_WORDS`,
      `_DOMAIN_QUALIFIER_RE`, `_load_skills_catalog_terms`/`_SKILLS_CATALOG_TERMS` (the
      `_alt_list_anchor`-only consumer), and every other regex constant that fed only these.
      **Correction found live while doing this**: `structured_fit.py`'s 5-criterion scorer is
      NOT superseded-and-deletable the way this story originally assumed — its own module
      docstring says it's still imported by `batch_pipeline.py` (the separate UI Draft path) and
      `fit_judgment_io.py` (CR-070's Claude-native fit path), explicitly "do NOT archive until
      CR-070 Epic 3+ retires this path." Left completely untouched — this CR only replaces
      `build_stage0_fit_gate.py`'s own call site (Story 2.4), not the module itself. Kept
      `_get_hard_tool_pattern`/`HARD_BLOCKED_TOOLS`, `_is_administratively_satisfied`,
      `_BACHELORS_SATISFIED_RE`, `_HIGHER_DEGREE_MANDATORY_RE`, `_YEARS_EXPERIENCE_LEADIN_RE` —
      **restored after an initial pass deleted them by accident**: `build_authoring_packet.py`
      imports all of these directly for its own non-claimable-item detection at packet-build
      time, unrelated to Stage 0 gate classification. Caught by re-running
      `build_authoring_packet`'s import before calling this done, not by inspection alone —
      worth remembering next time a "delete the superseded regex" story touches a shared file.
- [x] **Story 2.6 — Rewrite `check_fit_rubric_golden_set.py`.** No longer LLM-free/instant —
      runs live against Ollama for every active golden-set entry (all 21, not just the 16
      gate-checkable ones), reports per-category pass rate, grades evidence_level agreement
      within +-1 rather than requiring an exact match (a judgment call, not a bit-exact fact).
      Syntax/import-checked; the full 21-entry live sweep itself is pressure-test-phase work
      (each run is real LLM calls), not run to completion in this build pass.
- [x] **Story 2.7 — `test_build_stage0_fit_gate.py`'s regex-specific unit tests — partial.**
      Skipped (not deleted, not rewritten) every test block that either imports a removed
      function directly or asserts an invariant the new design makes definitionally false (e.g.
      `gap_class=="HARD"` for a bare tool mention — tools never gate now, spec Sec. 9):
      `TestGapClassification` (whole class), `test_domain_qualified_preferred_is_soft_gap`,
      `TestUndergraduateSatisfied` (whole class), `TestFamiliarityHardToolIsSoft` (whole class),
      `TestCompoundClauseSplitting` (whole class) — each skip cites CR-093 and this story.
      **Not done**: a real rewrite (mocking `evidence_scale.classify_requirement` so these run
      fast/offline again) — that's genuine pressure-test-phase work, explicitly deferred per
      Jason's "build everything, we will pressure test after." Confirmed via `unittest`
      collection that the file loads and non-skipped tests still run; did not run the full suite
      to completion (many remaining tests call `build_stage0_fit_gate()` end-to-end, which now
      makes real per-item LLM calls regardless of `STAGE0_SECTION_MODE` — that flag only ever
      controlled section *extraction*, not gap classification).

---

## Epic 3 — Corpus Validation Before Shipping (PRESSURE-TESTED, real bugs found and fixed)

**Run 2026-08-19, same session as Epic 2's build.** Jason: "build everything, we will pressure
test after" — this is that pass. Five real bugs found live, all fixed and re-verified, not just
logged:

1. **Checker reporting bug** (`check_fit_rubric_golden_set.py`): `passed = sum(1 for _, ok, _ in
   rows)` counted every row regardless of `ok` — every category showed PASS even when its own
   entries were listed FAIL underneath. One-line fix (`if ok` filter).
2. **Evidence-context truncation** (the Epic 2 Story 2.1 placeholder) — confirmed real, twice:
   Instructure under-scored a real Pendo/Amplitude match, and golden-set entry tool-004 (same
   Pendo case) missed expected_evidence_level 3, landing 0, because that evidence sits at char
   ~27,800 of the 73K-char document, past the old blind 8000-char prefix. **Fixed for real, not
   deferred further**: `evidence_scale.build_evidence_context()` now chunks `workExperience.md`
   on markdown headings and retrieves the top-k chunks by token overlap with the specific
   requirement line (same pattern as `fit_rubric_examples.py`'s few-shot retrieval), excluding
   PII-only sections (Contact Information/Professional References) from the candidate pool
   outright. `classify_requirement()`'s `work_exp` parameter now expects the **full, untruncated**
   document — all three call sites (`build_stage0_fit_gate.py`, `check_fit_rubric_golden_set.py`,
   `evidence_scale.py`'s own `__main__`) updated to stop pre-truncating. Verified live: tool-004
   went from level 0 to the expected level 3.
3. **`gate="HARD"` with an empty `gap_source`** — found live on a real `pending_review` JD
   (`bridge_technical_talent_c9ac7468`, a "provide mentorship to product managers, product
   owners..." line): the model recognized this should gate but didn't reliably pick
   `role_exclusion`, and the empty combination correctly hard-failed under the no-fallback design
   — but crashed a real Stage 0 run rather than classifying correctly. Fixed at the root: added
   an explicit `role_exclusion` example for "mentor/guide PEERS in the same discipline" to the
   system prompt, added JSON-schema `enum` constraints on `gate`/`gap_source`/`confidence`
   (closing off the invalid-empty-string path), and added an explicit "never empty when HARD, or
   the line doesn't actually gate" instruction. Re-tested live: now correctly returns
   `gate=HARD, gap_source=role_exclusion`.
4. **Adjacent-evidence literalism** — found live on `allcares_3af2ed54`: "Own the Operator
   product" scored evidence_level 0 with reasoning "candidate hasn't owned a product called
   Operator," failing to credit Jason's real, well-documented product-ownership experience as
   adjacent evidence (spec §7 level 1) just because the specific product name didn't match. Added
   an explicit instruction: rate the underlying capability a line is really testing, not this
   employer's specific name for it; reserve level 0 for when the *capability* itself is
   undocumented. Verified live: both failing lines went from level 0 to level 2.
5. **OR-alternative worst-match bias** — found via the golden-set sweep: `domain-fp-002`
   ("...product management or a relevant role within the banking industry") and `preferred-001`
   ("K-12 education, EdTech, SaaS, or enterprise software") both scored evidence_level 0 because
   the model evaluated against the domain-specific alternative Jason lacks (banking, K-12) instead
   of crediting the alternative he clearly has (product management, SaaS). Added an explicit
   OR-alternative rule: rate against whichever listed alternative the candidate matches *best*,
   never the worst. Fixed `preferred-001` to exact match (level 3); improved `domain-fp-002` from
   0 to 1 (expected 3) — genuinely ambiguous English ("a relevant role within banking" can
   reasonably read as coloring the whole alternative, not a clean escape hatch) — logged as the
   one remaining open item below, not force-fixed further.

**Golden set — final state after all fixes: 20/21 pass; 21/21 correct on gate + gap_source (the
disqualification-critical dimension) across every run this session, no exceptions.** The one
remaining miss (`domain-fp-002`) is an evidence_level-only discrepancy (1 vs expected 3) on a
line with genuine linguistic ambiguity, not a gate misclassification — logged as a real open item,
not swept under the rug. Also **superseded 3 stale-semantics golden-set entries**
(`tool-001/002/003`) whose `expected_gate: "HARD"` was authored against the OLD classifier's
severity label, not the new schema's literal "this disqualifies" meaning (their own
`expected_forces_skip: false` already said so) — replaced with schema-corrected `-v2` entries per
the file's append-only discipline (superseded, not edited in place).

**`pending_review/` batch (11 real folders, successor to the 2026-08-19 handoff's 15-row
batch) re-run twice** (once before the fixes above, once after) — **still 11/11 Skip both times,
but the real reason matters and is not what it looks like at a glance.** Inspecting item-level
output found most of these Skips are **not** fit-engine failures at all: several folders'
required-item extraction returned 0-1 items, and what it did return was garbled — a full opening
paragraph ("As a Technical Program Manager in Infrastructure, you will drive programs that span
multiple Stripe...") or the literal job title, not real requirement bullets, for `stripe_7fc30fab`
and `judge_group_inc_4b8c98e9`; zero required items at all for `ebanx_4d263dc3` (whose `role`
field also came back as literal `&lt;p&gt;` — this source JD's raw text is HTML-mangled). **This
is a pre-existing Stage 0 section-extraction problem** (`_extract_sections_llm`/`_extract_sections`
in `build_stage0_fit_gate.py`), **entirely outside CR-093's scope** — this CR only replaced gap
*classification*, not section *extraction*. `allcares_3af2ed54` is the one folder with clean,
real extracted requirements, and it now scores real partial-credit evidence (level 2 on both
items, post-fix-4) rather than flat 0 — still below the 70 floor, but for a defensible reason,
not a broken one. **Net read: the evidence-scale engine's classification is not what's failing
this batch — a separate, unfixed extraction-quality problem on messy/agency-sourced JDs is.**
That's a real, useful finding but a different CR's problem (see "Not in scope" below).

**Archive-corpus 15-JD sample: run after the fixes above landed** — see Story 3.1 below for the
real numbers. Unlike `pending_review`, this sample was NOT dominated by the extraction confound —
worth reading as a real (if small) signal, not dismissed.

**Not in scope for CR-093, flagged for a separate look:** the `pending_review` batch's
extraction-quality problem (garbled/empty required-item lists on agency-sourced, HTML-messy
JDs) is real and worth its own investigation — but it predates this CR and sits in
`_extract_sections_llm`/`_extract_sections`, code this CR never touched. Fixing it is a
different, focused piece of work, not a CR-093 story.

**Story status**, same discipline the domain-hard-gate rule got 2026-08-19 (402-JD archive corpus
sweep before shipping — don't trust golden-set pass rate alone for a change this central):

- [x] **Story 3.1 — Run the new engine against a real archive-corpus sample.** Not the full 402/416
      JDs (infeasible in one sitting — each item is a real LLM call). Ran the 15-JD spread sample.
      9 of 15 never reached the evidence-scale engine at all — a real, pre-existing, unrelated DB
      cooldown gate (`stage0_db_gate.py`, Step 0-2 of `build_stage0_fit_gate`, out of CR-093's
      scope) short-circuited them (`applause`, `business_wire`, `delinea`, `gigawatt`,
      `informdata`, `nava`, `pagerduty`, `roadie`, `spotify`, `veeva_systems` — Jason has prior
      application history on these, correctly cooling down). The 5 that reached real classification
      (`coinbase`, `everway`, `lasalle_network`, `qventus`, `the_judge_group`) all completed
      cleanly — **no crashes, no flat-zero pattern** (scores 40/53/55/56/63, a real spread) — but
      **0/5 cleared the 70-point floor.** Unlike the `pending_review` batch, these look like
      genuine score-driven reads on cleanly-extracted requirements, not extraction failures —
      worth a real look (see Story 3.3) rather than dismissed as another confound.
- [x] **Story 3.2 — Re-run the 2026-08-19 batch, successor found and run.** The original 15-row
      CSV batch itself wasn't recoverable this session, but its direct successor — 11 real JDs
      still sitting unresolved in `data/pending_review/` — was. Re-run twice (pre- and
      post-fixes), both 11/11 Skip. **Not a clean "still 0/N" repeat of the finding** — see the
      extraction-quality writeup above for why most of these Skips trace to a different, unfixed
      system, not this one.
- [ ] **Story 3.3 — Decide the floor** (Tier 1/2/Skip score bands). Not started, still needs
      Jason's explicit call per the spec's own framing (a judgment call, not inferable from data
      alone) — but there's now a real, if small, first data point: Story 3.1's 5 cleanly-scored
      archive JDs landed at 40/53/55/56/63, all below the 70 floor, none wildly off it. That's
      consistent with the spec's own citation (TalentWorks: real callback rates plateau around
      40-60% match, not 70-90%) suggesting the floor may be stricter than real outcomes justify —
      but 5 JDs is nowhere near enough to recalibrate on. Worth a real look once a larger sample
      exists (Story 3.1's full run, or real outcome data — did Jason apply, did he hear back).

---

## Epic 4 — Cutoff-Score Calibration Research (2026-08-19, real primary-source pass)

Jason's instruction after Epic 3's pressure test surfaced real, live evidence against the
70-point floor: bring the same rigor that produced `data/fit_rubric_spec.html` to the specific
calibration question that spec's own Section 14 left provisional. This is that pass — real
primary-source research on how cutoff scores get set in personnel selection generally (not just
more of the same applicant-outcome data already in hand), done before touching the number.

### Evidence ledger

| Principle | Implication | Source | Type | Strength | Limitations |
|---|---|---|---|---|---|
| No cutoff score is "correct" independent of the method and population used to set it — a 2024 comparison of 4 standard-setting methods (Angoff, Borderline Group, Contrasting Groups, Patient Safety) on the *same* assessment produced a 20.2-point spread (67.8%-86.1%) | A specific number can't be presented as objectively right without naming the method and data behind it — this applies to 70 exactly as much as to any replacement number | Cascio, Alexander & Barrett (1988), *Personnel Psychology* (the seminal legal/psychometric cutoff-score paper — confirmed "wide variation" in appropriate standards is the literature's own finding, not a gap in it); PMC 2024 comparison study | Peer-reviewed | Strong | PMC study is medical-licensing domain — methodology transfers, exact percentages don't |
| Item-focused methods (Angoff) need an expert panel judging a "minimally qualified candidate's" pass probability per item; outcome-focused methods (Borderline Group, Contrasting Groups) need real historical performance/outcome data at the border | Applyr has neither yet — no expert panel, and no real interview/no-interview outcome data under the new engine (it shipped today) | Angoff / Borderline Group / Contrasting Groups methodology (general I-O psych standard-setting literature) | Peer-reviewed methodology | Strong as description of what real calibration requires | Confirms *why* any number chosen now must stay explicitly provisional, not a gap to paper over |
| Job-fit measures used as a screen-**out** tool (exactly Applyr's use) are flagged by the U.S. Office of Personnel Management itself as an area where "research (validity, methodology, utility)... is still in its infancy" | The federal government's own personnel authority isn't confident this exact use case is well-validated at all | OPM (opm.gov), U.S. federal HR authority | Primary/authoritative | Strong as a caution | Doesn't supply a number — reinforces treating any cutoff as provisional and revisited |
| Real applicant-outcome data (not lab data): interview callback odds climb sharply starting ~40% requirement-match and plateau by ~50-60%; going higher adds little | A floor near "most requirements met" (70-90%) discards real opportunities the outcome data says are worth pursuing | TalentWorks (6,000+ real applications, 118 industries), corroborated by CNBC (already in `fit_rubric_spec.html`, re-confirmed here) | Applied research, large real-N, not peer-reviewed | Moderate-strong | Measures "% of listed requirements met" — Applyr's weighted evidence-scale score isn't a literal 1:1 equivalent to that construct |
| Applyr's own real data, collected today under the new engine: 5 archive JDs with cleanly-extracted requirements scored 40/53/55/56/63; a same-day 15-JD live batch (2026-08-18 session) scored predominantly in the 40-66 range | The closest thing to a real Contrasting/Borderline-Group data point Applyr has — a real score distribution from real JDs under the actual construct being calibrated, not a proxy | This session + prior session (Applyr, real submissions) | First-party, applied, N≈20 | Moderate | Real distribution, but not yet paired with outcome labels (no JD has been submitted at these scores yet to know if they'd have converted) |

### Recommendation

No expert panel and no real outcome data exist yet to run an actual Angoff or Contrasting-Groups
calibration — so, consistent with Constraint #2 (no number gets presented as more validated than
it is), this is a **design-inference recommendation grounded in the strongest available proxy
evidence (TalentWorks' real-outcome plateau point + Applyr's own real score distribution)**, not
a settled number:

- **Skip below 40** — below TalentWorks' inflection point where real callback odds start
  climbing; a score in this range reflects either a genuine hard gate already firing (handled
  separately, unaffected by this number) or evidence so thin across the board that pursuing it
  is a poor use of a real application.
- **Tier 2 (worth applying) from 40 up to the Tier 1 boundary** — matches the plateau region
  TalentWorks found real candidates already get real interviews in.
- **Tier 1 (strong) at 65+** — comfortably past the plateau where the research shows additional
  match stops producing better odds; a score here should read as "no real reason to doubt this
  is a good match," not "barely cleared a bar."

**This replaces 80/70 with 65/40** as the concrete recommendation, a meaningfully lower and wider
Tier 2 band than before — not a small nudge.

**What would upgrade this from provisional to real**: the moment Jason applies to jobs scored
under this engine and real interview/no-interview outcomes start coming back, that's a genuine
Contrasting-Groups-method opportunity — compare the score distribution of JDs that converted to
interviews against those that didn't, and set the floor at the real intersection point, the way
the PMC comparison study's methods actually work. Don't treat 65/40 as final; treat it as the
first defensible number, replaceable by real outcome data the moment it exists.

### Implementation

`build_stage0_fit_gate.py` no longer hardcodes 80/70 — Step 5.5 now reads the Skip/Tier 2
boundary from `get_min_fit_score()` (the same real, existing `candidate_preferences.json`
`min_fit_score` preference the legacy `structured_fit` decision path already used — this was a
second, different, unused-here floor of 72 silently coexisting with the hardcoded 70 before
today; consolidated onto one real setting instead of adding a third) and the Tier 1 boundary from
a new optional `tier1_fit_score` preference (defaults to `min_fit_score + 25` if unset).

**Applied 2026-08-19, then relocated same day on Jason's follow-up.** First landed in
`data/candidate_preferences.json` (`min_fit_score: 40`, `tier1_fit_score: 65`) on Jason's "use
the values the research supports." Jason then raised the right architectural question: *"if the
research bares out that these are the correct values for job fit I don't know if that should be
a preference that should live somewhere else."* Correct call — `candidate_preferences.json`
holds Jason's personal job-search preferences (location, blocked industries, min salary); a
score-band floor is a property of how the scoring *algorithm* interprets its own output, not a
preference about what job he wants. Same category error as if the weight table
(`_REQUIRED_WEIGHT`/`_CONFIDENCE_MULTIPLIER` in `evidence_scale.py`) had been dropped into that
file instead of living as engine constants.

**Final design**: new `data/fit_rubric_calibration.json` — tracked in **git**, deliberately
*not* gitignored like the rest of `data/*.json` (a recalibration should be a real, reviewable
diff, the same way a CR doc tracks a threshold change, not invisible inside gitignored personal
data). Holds `score_bands.skip_floor`/`tier1_floor` plus the full rationale/status/upgrade-path
text from the research above, and a `weighting_model` section flagging that
`evidence_scale.py`'s weight table has the *same* "design inference, not calibrated" status and
should move into this same file on the next recalibration pass, rather than being rediscovered
scattered again. `evidence_scale.load_score_bands()` reads it (falling back to 40/65, not the old
80/70, if the file is ever missing); `build_stage0_fit_gate.py` Step 5.5 calls it directly.
`candidate_preferences.json`'s `min_fit_score` was reset back to its original 72 — still real,
still used by the separate legacy `structured_fit`/UI-Draft path (`utils.get_min_fit_score()`,
confirmed via `server/domain/jobSearchPrefs.ts` to have zero live consumers of its own
`readMinFitScore()` beyond that), untouched and unaffected by this change. Verified live after
the move: `load_score_bands()` returns `(40, 65)` from the new file; Coinbase (fit_score 53)
still correctly lands Tier 2/PASS.

---

## Epic 5 — Erase the Old Fit Mechanism Entirely (2026-08-19)

Jason, after the calibration relocation: *"We need to get out of the habit of replacing things
and keeping the old stuff — it causes confusion later. Harden that we are using the new rubric
and fit score and erase any mention of the old fit."* This epic is that pass — not just "the new
engine is now used," but "the old one no longer exists to be confused with it."

**What made this bigger than it first looked**: `structured_fit.py`'s scorer wasn't only used by
the CLI path this CR had already rewired — it was also live behind a real, separate frontend page
("Find New Jobs" / `POST /api/evaluate`), explicitly flagged in a 2026-08-04 handoff as "not yet
investigated for whether it's live — do not touch yet." Confirmed with Jason directly (not
assumed) that this page is also dead before touching it — surfaced as a real fork via
`AskUserQuestion` rather than guessed either way, since a 2026-08-04 doc had explicitly told a
future session not to touch it without checking.

**Deleted outright**: `scripts/structured_fit.py`, `scripts/fit_policy.py`,
`scripts/fit_judgment_io.py`. `batch_pipeline.py`'s `evaluate_job_fit()` +
`_call_fit_llm()`/`_call_fit_scoring_only()`/`process_single()`/`process_batch()` + its
`--mode single|batch` CLI entry point (the file is now a pure DB/JD helper library — 27 dangling
imports and constants cleaned up alongside, including a `GPU_LOCK` and five `os.environ.setdefault`
calls that were silently mutating process-wide env vars on every import). `src/pages/
FindNewJobsView.tsx`, `src/hooks/usePipeline.ts`, the "Add Job" sidebar tab, and `POST
/api/evaluate` (`server/routes/pipeline.ts`, surgically removed — `/api/sync`/`/api/sync/stream`
in the same file are unrelated and untouched). `candidate_preferences.json`'s `min_fit_score`
field, `utils.get_min_fit_score()`/`MIN_FIT_SCORE`, and the TypeScript-side
`readMinFitScore()`/`DEFAULT_MIN_FIT_SCORE` — every remaining consumer traced back to the deleted
system, none left orphaned. Dead maintenance scripts (`re_score_jobs.py`, `regenerate_backlog.py`,
`cleanup_pending_backlog.py`) and their test-only files deleted too, after confirming
`test_audit_convergence.py`'s one genuinely valuable regression (CR-054 non-convergence
transparency) has independent coverage in `test_audit_improve_native.py` that doesn't route
through the deleted `process_single()`.

**Verified, not assumed clean**: `npx tsc --noEmit` — zero errors. Full `npx vitest run` — 292/292
passing, 32/32 files. `python scripts/run_all_tests.py --python-only` — clean except one
pre-existing, unrelated failure (`test_audit_claims_coverage.py`, a `master_claims.json`
project_id data-drift issue this session never touched — confirmed via the file's own imports,
not assumed) and one already-known, already-logged slow-suite timeout
(`test_build_stage0_fit_gate.py`, Epic 2 Story 2.7's still-open "needs a real mocked rewrite"
item, unaffected by today's deletions).

**Docs updated in the same pass** (per this repo's own doc-change checklist): `README.md`'s Fit
Scoring section, Drafting Assets section, project-structure map (3 lines), and server-routes line;
`PRODUCT_CAPABILITIES.md`'s job-fit-scoring section and the now-stale "Resilient Batch Drafting"
claim; `CHANGELOG.md` gets a real `[Unreleased]` entry for both the engine build and this removal
pass, not left to go stale like the Fit Scoring section had.

---

## Rollout note

Epic 1 is net-new code (a new module, nothing wired in yet) — safe to build and validate in
isolation. Epic 2 is the actual production cutover (touches the live Stage 0 path every future
`run_submission.py` call goes through) — do not start Epic 2 without Epic 1 Story 1.4's real
validation results in hand, and do not consider Epic 2 done without Epic 3's corpus check, same
standard as every other Stage 0 rule shipped this session.

**2026-08-19 update: Epic 2 is now built and live** — `build_stage0_fit_gate.py`'s Stage 0 path
runs entirely on the evidence-scale engine, the regex classifier is deleted, and
`run_submission.py`'s next real call will use this. Per Jason's explicit instruction, Epic 3
(golden-set full sweep + 402-JD archive corpus check + 15-row batch re-run) has **not** run
yet — that is the very next thing to do, before trusting this on a real application, and before
telling Jason a specific JD's Skip/Tier decision is reliable. Do not skip Epic 3 because Epic 2
"ran clean" on two smoke-test JDs; that was a wiring check, not a validation.
