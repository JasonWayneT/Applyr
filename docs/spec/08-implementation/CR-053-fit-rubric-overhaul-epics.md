---
status: in_progress
created: 2026-06-30
supersedes_policy_from: CR-039 (transferable-skills-over-domain-gate)
related: CR-035 (fit-scoring-hardening), CR-036 (solo-pm-years-policy), CR-037 (required-domain-gate, superseded by CR-039), FR-401–405 (Cluster 4 Scoring Calibration, planned but never implemented)
contains: CR-053 (Fit Rubric Overhaul), CR-054 (Pipeline Integrity & Failure Transparency), CR-055 (Collection Gate Accuracy)
---

# CR-053 / CR-054 / CR-055 — Job-Fit, Pipeline Reliability & Collection Accuracy Overhaul: Epics & Stories

**Handoff doc, three change requests.** This is the resumable plan covering (a) the job-fit scoring
rebuild (CR-053), (b) pipeline integrity/failure-transparency hardening (CR-054), and (c) collection
gate accuracy — fixing jobs killed before they ever reach scoring (CR-055). All three were found in
the same diagnosis pass. Read top-to-bottom before doing anything; check off stories as completed; a
new session can pick up at the first unchecked story with no other context needed beyond this file +
the files it references. CR-053 is the original scoring-accuracy work. CR-054 was added after the
same session caught the pipeline reporting `passed: true` on two drafts that had actually failed
internal quality checks. CR-055 was added after pulling real `activity_log` production data and
finding two confirmed bugs (a years-gate parsing error, a title-blocklist false-positive pattern)
killing correctly-fitting jobs before scoring ever sees them — a failure class invisible to the
post-scoring outcome data CR-053 was calibrated against. See the combined rollout-priority note at
the very end of this file for how to sequence all three.

## Why this exists (do not re-litigate without re-reading this)

Session-origin diagnosis (2026-06-30) found:

1. **The fit score is a single opaque LLM call** (`batch_pipeline.py:719-835 evaluate_job_fit`,
   `_call_fit_scoring_only`/`_call_fit_llm`) that returns `Score: Integer (0-100)` directly from raw
   JD text in one shot. No per-criterion breakdown, no evidence citation, no tiering. This violates
   the personnel-selection research finding that structured/criterion-anchored evaluation roughly
   doubles predictive validity over holistic judgment (Schmidt & Hunter 1998; 2022 reanalysis
   preserves the ~2x gap even after correction).
2. **Domain/industry mismatch is explicitly excluded from scoring** by system-prompt instruction
   (`fit_policy.py:50-58 TRANSFERABLE_SKILLS_NOTE`, CR-039), with zero compensating signal. This is
   *not* the dominant real-world failure mode — see calibration data below — but it is a real,
   confirmed failure mode (TrellisWare: fit score 85, three straight failed cover-letter generation
   attempts because there were no real domain claims to draft from).
3. **`apply_anchor_floor` (`fit_policy.py:188-222`) force-overwrites LLM scores** to exactly
   `min_fit_score` when ≥2 of 4 nearly-universal keywords (`saas`, `platform`, `cross-functional`,
   `roadmap`) appear anywhere in the JD — a deterministic override using generic vocabulary as trigger.
4. **Years-of-experience is a hard gate** (`seniority_gate.py:69-100 parse_max_years_required`) using
   a body-wide regex with no requirement the matched number actually sits in a requirements section —
   confirmed root cause of the Civica false-reject ("21 years" parsed from unrelated JD text).

### Calibration evidence (ground truth, not opinion) — `data/jobagent.sqlite.jobs`

Real outcome data: 573 Rejected, 343 Closed, 69 Applied. Of the 62 jobs the pipeline scored ≥72
("good fit, draft it") that Jason then manually self-rejected, of the 52 with a logged reason:

| Cause | Count | % |
|---|---:|---:|
| Location/hybrid/onsite/hiring-state mismatch | 30 | 58% |
| Duplicate listing (re-scraped) | 8 | 15% |
| Domain/skill mismatch (fintech, IAM/RBAC, healthcare) | 3 | 6% |
| Wrong role type ("no longer looking for PM/PO roles") | 2 | 4% |
| Company-specific opt-out | 1 | 2% |
| Seniority, comp, contract-type | 3 | 6% |
| Other/unclear | 5 | 10% |

**Location-gate reliability is the dominant real-world leak, not domain.** `classify_onsite` /
`resolve_location_verdict` are supposed to be deterministic and already catch most cases at the gate
stage, but confirmed misses include Case IQ (in-person Canada, scored 100), Secureframe (hybrid NYC,
95), Mandolin (onsite SF, 92), yeet (onsite Chicago, 92). This is why Epic 1 below is location, not
domain, despite domain being the original trigger for this overhaul — the data overrode the working
assumption mid-session and the plan was reordered accordingly. Do not re-skip Epic 1.

Also found: TrellisWare already has a prior DB row with `status='Applied'`, score 85, from before this
session — i.e. it was already mis-applied-to once under the current scoring. Unity (`Senior TPM,
gaming`) shows `status='Applied'` in the DB despite a prior memory note saying "flagged do-not-apply" —
a second concrete instance of score not tracking actual judgment.

---

## Epic 0 — Diagnosis & Calibration Data (COMPLETE)

- [x] Read every file touching gating/scoring (`seniority_gate.py`, `industry_gate.py`,
      `anchor_gate.py`, `solo_pm_gate.py`, `fit_policy.py`, `utils.py:passes_keyword_gate`,
      `batch_pipeline.py` fit functions, `.agent/rules/job_fit_engine.md`)
- [x] Confirm LLM call returns holistic score directly (top-priority anti-pattern from source brief)
- [x] Pull real outcome ground truth from `data/jobagent.sqlite` (`status`, `rejection_type`,
      `outcome_notes` fields — this is the calibration set called for in the original brief's Step 3,
      no synthetic/fabricated postings needed)
- [x] Quantify leak categories from the 62 high-score self-rejects (table above)

No further action needed on this epic. Re-run the SQL below if more calibration signal is needed later:
```sql
SELECT company, title, score, outcome_notes FROM jobs
WHERE rejection_type='Self-Rejected' AND score >= 72 ORDER BY score DESC;
```

---

## Epic 1 — Location Gate Reliability (do this first; cheapest, highest ROI, pure bugfix)

**Goal:** stop scoring onsite/hybrid/wrong-country/wrong-state jobs ≥72. This is a correctness bug
in existing deterministic code, not a redesign — should not require new architecture.

- [ ] **Story 1.1 — Root-cause the 30 confirmed location misses.** Pull JD text for each of the
      30 location-related self-rejects (`data/jobagent.sqlite` via `jd_text` column on `jobs`, joined
      on company/title from the leak table above — some rows may have empty `jd_text` if scraped
      before that column existed; note any gaps with `[VERIFY]`). For each, run it through
      `scripts/zero_shot_classifier.py: classify_onsite` / `resolve_location_verdict` directly and
      record what verdict it actually returns today vs. what it should return. Categorize failure
      patterns (e.g.: hybrid-language not in the regex/keyword set; city name not recognized as
      non-remote; "Remote (EST timezone only)" being misclassified as REMOTE_OK; hiring-state
      restrictions like "does not hire in California" not detected at all since they require semantic
      understanding, not keyword matching).
- [ ] **Story 1.2 — Fix or extend `classify_onsite`/`resolve_location_verdict`** for the confirmed
      patterns from 1.1. Where the failure is a clean keyword/regex gap, fix deterministically. Where
      it requires actual semantic judgment (e.g. "does not hire in California" — no fixed keyword set
      will catch all phrasings of hiring-state restrictions), this becomes a narrow LLM
      equivalence-judgment call ("does this JD state a hiring-state/country restriction that excludes
      San Diego, CA — yes/no/unclear") per the Epic 2 LLM-boundary pattern, not a holistic re-score.
- [ ] **Story 1.3 — Regression tests.** Add the 30 confirmed-miss JDs (or condensed fixtures derived
      from them) as a test fixture set in whatever test file owns `zero_shot_classifier.py` coverage
      today (`[VERIFY]` exact file — search for existing tests first, do not assume one exists).
      Every fixture must fail (correctly reject) after the fix. Do not mark this story done until the
      fixtures actually run red→green.
- [ ] **Story 1.4 — Re-score affected jobs.** Once the gate is fixed, decide whether to re-run
      `evaluate_job_fit` against currently-`Backlog`/`New` jobs in the DB to catch jobs that should
      now be rejected at the location stage that previously weren't (separate from re-scoring already
      `Applied`/`Rejected`/`Closed` jobs, which is out of scope — don't touch historical outcomes).

---

## Epic 2 — Evidence-Tiered Deterministic Scoring Architecture

**Goal:** replace the single holistic LLM score with: deterministic field extraction → narrow LLM
equivalence judgments (yes/partial/no per requirement, one sentence justification, never a number) →
deterministic score computation in code. This is the architectural core of the original brief.

- [ ] **Story 2.1 — Define the data model.** Implement the `FitReport` schema from the original
      brief (decision, fit_score, confidence_score, must_haves[], criteria_scores[], risks[],
      validation_questions[]) as actual code (Python dataclass/TypedDict — match whatever typing
      convention `batch_pipeline.py` already uses; `[VERIFY]` current convention before choosing).
      Include evidence tiers (1–4) and `verifiable_against_source: bool` on every evidence item per
      the brief.
- [ ] **Story 2.2 — Must-have extraction (deterministic where possible).** Extract 3–5 explicit
      must-haves from JD text. Distinguish "stated requirement" from "incidental number in prose"
      — this directly fixes the years-gate false-positive class (Civica) by requiring the matched
      years figure to appear within a requirements-shaped sentence, not just anywhere in the JD body.
      `[VERIFY]` whether this needs an LLM pass or can stay regex-based with tighter anchoring; try
      tighter regex first since it's cheaper and more auditable.
- [ ] **Story 2.3 — Narrow LLM equivalence-judgment call.** Replace `_call_fit_scoring_only` /
      `_call_fit_llm`'s holistic-score prompt with calls that return only
      `{judgment: "yes"|"partial"|"no", justification: string}` per requirement/criterion — never a
      number. Show the full prompt text in the implementation doc when done (brief requires this).
- [ ] **Story 2.4 — Deterministic score computation.** Compute `criteria_scores[].score` (0-5),
      apply weights, sum to `fit_score` (0-100) — all in code, not LLM output. Implement the
      verifiability cap: a criterion score of 4-5 requires ≥1 evidence item that is both Tier 1/2
      AND `verifiable_against_source: true`; unverifiable/prose-only evidence caps the criterion at 3
      regardless of language strength. This is the direct fix for fabricated-metric-style overconfidence.
- [ ] **Story 2.5 — Confidence-score routing.** `confidence_score` drops when evidence leans
      Tier 3/4 or `verifiable_against_source: false`. A high `fit_score` with low `confidence_score`
      must route to `decision: "review"`, never silently auto-pass identically to a high-confidence
      high score. Make both thresholds configurable (likely in `candidate_preferences.json` alongside
      existing `min_fit_score`).
- [ ] **Story 2.6 — Retire `apply_anchor_floor`'s score-overwrite behavior** (`fit_policy.py:188-222`).
      The anchor-hit signal can still inform `risks`/evidence, but it must not force-overwrite a
      computed score to the pass threshold. Decide whether anchor-hit evidence becomes a Tier 4
      (keyword-only) evidence item feeding the new deterministic computation, or is dropped entirely
      — `[VERIFY]` against calibration data once Epic 4 runs whether anchor-floor promotions ever
      correlated with a job you actually wanted.

---

## Epic 3 — Domain Fit as a Bounded, Scored Signal

**Goal:** stop ignoring domain mismatch, without letting it dominate or auto-reject strong
transferable-skills candidates. Per the original brief and Jason's explicit instruction
("can't weight it so much that a simple domain miss is going to bounce the opportunity").

- [ ] **Story 3.1 — Decide placement in the criteria table.** Per the original brief, domain/context
      fit should NOT be a separately weighted top-level criterion (personnel-selection literature
      treats it as a tie-breaker once skill/responsibility evidence is accounted for). Implement it as
      a bounded modifier inside `risk_penalty` (max -10 of the 100-point total, per the existing
      weight table) plus a `notes`/`risks` flag, not as its own 15-25pt column. Re-confirm this
      placement against the calibration data (domain was only 6% of real self-rejects — a small
      modifier is proportionate to that, a large one would not be).
- [ ] **Story 3.2 — Define what counts as a "domain requirement" vs. "domain preference."**
      Reuse/extend the existing `detect_optional_domain_note` logic (`fit_policy.py:123-131`) which
      already detects "nice to have"/"preferred" framing — that logic should stay, just feed the new
      scoring model instead of being a prompt-injection-only signal.
- [ ] **Story 3.3 — Implement the bounded penalty.** When a JD states a *required* (not preferred)
      domain/vertical skill the candidate's evidence doesn't cover (e.g. "IAM/RBAC", "fintech
      compliance"), apply the bounded penalty and add a `risks` entry naming the specific gap. Must
      not be able to push a strong transferable-skills candidate below the pass threshold on domain
      alone — cap the penalty's effect explicitly in code, don't rely on prompt instruction.
- [ ] **Story 3.4 — Regression test:** a JD with a hard required-domain-skill gap (e.g. the real
      Brahma Consulting IAM/RBAC case from calibration data) scores lower than an equivalent JD
      without that requirement, but does not auto-fail when other criteria are strong. Pair with a
      test that a domain-optional JD ("healthcare experience a plus") does not get penalized at all.

---

## Epic 4 — Calibration Against Real History & Test Matrix

**Goal:** prove the rebuilt rubric actually agrees with Jason's real past judgment before trusting it
live. Do not skip — the original brief is explicit that disagreement on "obvious" cases is a rubric
bug, not a quirk to note and move past.

- [ ] **Story 4.1 — Build a calibration harness** that runs the new `evaluate_job_fit` against stored
      `jd_text` for a sample of: (a) all 62 self-rejected-after-≥72-score jobs (expect new system to
      score these lower or route to `review`), (b) a sample of `Applied` jobs across the score range
      (expect these to still pass), (c) the explicit `rejection_type IN ('Mismatch','Unfit')` rows
      (Clickup/Lifetime Value Co/Edesk/Tailor/Walrus — expect low scores). `[VERIFY]` `jd_text`
      completeness for older rows before relying on this — some early-archive jobs may lack it.
- [ ] **Story 4.2 — Report disagreements.** Any case where new-system output contradicts the known
      real-world outcome (Jason applied and it was a real fit; Jason rejected and it was a real miss)
      gets logged as a rubric bug and fixed before moving on — per brief's explicit instruction, not
      shipped with a footnote.
- [ ] **Story 4.3 — Implement the test matrix** from the original brief (10 cases: exact match,
      adjacent/transferable fit, seniority mismatch, keyword-spam-no-evidence, strong-outcomes-weak-
      domain, must-have hard-fail, high-score-low-confidence routing, overqualified, missing-metrics-
      strong-ownership, sparse/ambiguous JD). Use real JDs from the archive where they exist for a
      given case type; synthesize only where no real example exists, and mark synthesized fixtures
      clearly as such (not presented as real calibration data).

---

## Epic 5 — Rollout

- [ ] **Story 5.1 — Re-run this session's 5 passing/1 failing CSV batch** (Accompany Health, Private
      Health Management, Rencata, TE Connectivity, TrellisWare) through the rebuilt pipeline once
      Epics 1-4 are done. Compare new scores/decisions against the original 95/92/85/95/85. Report
      deltas — this is a live sanity check using a case you already have full context on.
- [ ] **Story 5.2 — Update `.agent/rules/job_fit_engine.md`** to reflect actual implemented logic
      (it's currently aspirational/prompt text, not a 1:1 description of code behavior — keep them in
      sync going forward or note explicitly where they diverge and why).
- [ ] **Story 5.3 — CHANGELOG.md + PRODUCT_CAPABILITIES.md entries** per this repo's standard
      change-request closeout convention (see any `CR-0XX` entry in those files for format).

---

## Open questions / tuning knobs not resolvable from the codebase alone (`[VERIFY]` with Jason)

- Exact `fit_score` pass threshold and `confidence_score` review-routing threshold — brief says "you
  decide a sensible default, make configurable"; current `min_fit_score=72` is the only existing
  anchor point, but it was calibrated against the old holistic scoring, not the new structured one —
  do not assume it transfers unchanged.
- Whether duplicate-listing leak (15% of self-rejects, 8 cases) gets its own epic — it's a dedup
  engineering problem, not a fit-rubric problem, but it's large enough in the data to be worth a
  follow-up CR. Flagging here so it isn't lost; not in scope for CR-053.
- Whether `apply_anchor_floor`'s underlying signal (2+ generic keyword hits) has ever correlated with
  a job Jason actually wanted — needs Epic 4's calibration run to answer with data rather than guessing.

---
---

# CR-054 — Pipeline Integrity & Failure Transparency: Epics & Stories

**Why this is a separate CR, not folded into CR-053:** CR-053 makes the fit *decision* more accurate.
CR-054 makes the *system honest about whether it succeeded* once a decision is made. These are
independent failure modes — a perfectly accurate fit score is worthless if the downstream document it
produces silently contains a fabricated metric or a forbidden phrase and the pipeline reports success
anyway. Found live, twice, in the same session that produced CR-053 (see Epic 1 below) — not
theoretical.

**Priority relative to CR-053:** arguably higher. CR-053 improves which jobs you pursue. CR-054
protects the integrity of every document this tool has ever produced or will produce, including ones
already submitted to real employers. If forced to choose one first, do CR-054 Epic 1 first — it's the
cheapest fix here and the highest-consequence bug in the whole system.

**Independent corroboration:** the same failure class (a submission silently incomplete with no
caller-visible error) was found separately on 2026-06-25 in `CODE_FIXES.md` (repo root), Fix 6 — the
`napster_corp_` folder missing Resume/CoverLetter/PDFs with no error logged. That audit proposed
"completion verification" as its own fix; `docs/pipeline-quality-epics.md` (the epics doc that audit
fed into) doesn't yet have a dedicated epic for it. CR-054 Epic 1 below supersedes/covers that need —
don't build a third version of this fix in the pipeline-quality-epics.md track.

---

## Epic 1 — Stop Reporting Success on Failed Drafts (do this first)

**Goal:** `audit_and_improve_company` failing to converge must make the run report `passed: false`,
not get swallowed by a bare `except` two frames up while an unconditional success message prints anyway.

- [ ] **Story 1.1 — Root cause, confirmed.** `scripts/drafting_engine.py:377-385`:
      ```python
      try:
          from audit_and_improve import audit_and_improve_company
          audit_and_improve_company(company_folder)
      except Exception as e:
          print(f"    [Enhancement Warning] Failed to run automated post-drafting quality check: {e}")
      print(f"  -> Successfully generated and audited all assets for {company_name}")
      ```
      `audit_and_improve_company` (`scripts/audit_and_improve.py:249`) can internally print
      `"[Failed] Could not align assets within constraints for {company} after {attempts} attempts."`
      and still return normally — no exception raised, no return value checked. The `except` never
      fires. The unconditional print two lines later claims success regardless. No further
      investigation needed on this story; the bug is confirmed by direct code read, not inferred.
- [ ] **Story 1.2 — Give `audit_and_improve_company` a real return contract.** It must return
      (or raise) something the caller can branch on — e.g. `{"converged": bool, "attempts": int,
      "final_issues": list[str]}`. `[VERIFY]` current return type before changing — read the full
      function body in `scripts/audit_and_improve.py`, not just the failure print line, since the
      convergence loop and the 3-attempt cap need to be understood before deciding what "converged"
      means precisely (e.g. does attempt 1 succeeding count differently from attempt 3 succeeding?
      probably not for this purpose, but confirm).
- [ ] **Story 1.3 — Propagate non-convergence to the caller.** `run_drafting_engine` must NOT print
      "Successfully generated and audited all assets" when `converged=False`. Trace the call chain
      back up to `batch_pipeline.py:837 process_single` and confirm `passed: false` actually reaches
      the JSON the WebApp/CLI consumer reads (`{"score": score, "passed": false, ...}` pattern already
      exists elsewhere in `process_single` — reuse it, don't invent a new shape).
- [ ] **Story 1.4 — Decide what happens to a non-converged draft already on disk.** Two real cases
      hit this session: (a) PHM — the bad enhanced `CoverLetter.md` was written to disk but the PDF
      export failed separately, leaving a stale-but-clean PDF; (b) TE Connectivity — the bad
      `CoverLetter.md` WAS exported to PDF. Decide and implement a consistent policy: either (i) never
      overwrite the last-known-good Resume.md/CoverLetter.md with a non-converged draft, only ever the
      JSON-reported failure, or (ii) write the failed draft somewhere clearly marked
      (`CoverLetter.DRAFT_FAILED.md`) so a human reviewing the folder can't mistake it for ready output.
      Do not just suppress the symptom — case (b) actually shipped a forbidden-phrase/fabricated-metric
      document to disk under the normal filename with no marker.
- [ ] **Story 1.5 — Regression test.** Force `audit_and_improve_company` to fail to converge (e.g. by
      feeding a JD/claim combination known to trigger a metric-mismatch loop) and assert the pipeline
      reports `passed: false` and does not silently overwrite `Resume.md`/`CoverLetter.md` with
      unconverged content. This is the test that would have caught both of this session's live misses.

---

## Epic 2 — Audit the Other Swallow-and-Continue Exception Blocks

**Goal:** the Epic 1 bug wasn't a one-off pattern — `grep -rn "except Exception" scripts/*.py` returns
120 hits, of which a quick scan found 25 that print-and-continue with no caller-visible failure signal.
Not all 120 are load-bearing (many are legitimately "best-effort, log and move on" — e.g. cheat-sheet
generation already has its own explicit `[cheat_sheet, status: warning]` JSON event, which is the
correct pattern). The goal is to find which of the rest behave like Epic 1's bug, not to rewrite all
exception handling indiscriminately.

- [ ] **Story 2.1 — Triage the 120.** Categorize each `except Exception` block into: (a) correctly
      surfaces a caller-visible warning/error signal already (fine, leave alone — `cheat_sheet`
      generation is the model example), (b) swallows a failure that affects what gets written to a
      submission folder or what gets reported as `passed` (high priority, same class as Epic 1), (c)
      swallows a failure in a genuinely non-critical path (logging, research/intelligence fetch,
      VRAM reclamation — low priority, document and move on). Produce this as a simple table in this
      doc, not a separate artifact, so the triage itself is part of the handoff.
- [ ] **Story 2.2 — Fix category (b) blocks** using the same return-contract pattern as Epic 1 Story
      1.2 (don't invent a second pattern for the same problem).
- [ ] **Story 2.3 — Regression coverage** for whichever category-(b) blocks get fixed, same shape as
      Epic 1 Story 1.5.

---

## Epic 3 — Connect Manual Judgment to Deterministic Gates

**Goal:** a job you've explicitly flagged "do not apply" in writing should never reach `Applied` again,
full stop — independent of whatever the LLM or scoring logic decides on a re-run.

- [ ] **Story 3.1 — Confirmed gap.** `CLAUDE.md` (project root) has a hand-maintained note: *"unity —
      Senior TPM / gaming domain; flagged do-not-apply."* `data/jobagent.sqlite.jobs` shows
      `company='Unity', status='Applied', score=95`. The flag exists in prose; nothing in
      `passes_jd_keyword_gate`/`evaluate_job_fit` reads it. This is a real instance, not a
      hypothetical — confirmed by direct query + direct file read in the same session.
- [ ] **Story 3.2 — Design the enforcement mechanism.** Likely simplest: a `blocked_companies` (or
      `blocked_company_role_pairs`, since "don't apply to Unity for a gaming-domain TPM role" might be
      narrower than "never apply to Unity at all" — `[VERIFY]` with Jason which scope he actually
      means before building) list in `candidate_preferences.json`, checked deterministically in
      `passes_jd_keyword_gate` alongside the existing title/industry blocklists. Simpler and more
      auditable than trying to parse CLAUDE.md prose at runtime.
- [ ] **Story 3.3 — Backfill from existing signal.** Cross-reference `rejection_type IN
      ('Self-Rejected','Mismatch','Unfit')` rows in the DB against company names — any company you've
      already explicitly killed once is a candidate for the new blocklist. `[VERIFY]` with Jason before
      bulk-adding — a self-reject reason like "duplicate" or "contract role" is not the same as "never
      show me this company again," only company-level/domain-level rejections should backfill.
- [ ] **Story 3.4 — Regression test:** a JD from a blocklisted company is rejected at the deterministic
      gate stage regardless of how well it would otherwise score.

---

## Epic 4 — Guardrail Audit (find the other dormant template-literal bugs)

**Goal:** the em-dash bug fixed in CR-053's session wasn't an LLM mistake — it was hard-coded into
`scripts/summary_builder.py`'s template literals and `data/Resume_Style_Reference.md`, meaning the
lint rule (`LR-006`) had presumably been silently rejecting drafts on every run that hit that code
path, for an unknown period, with nothing flagging that the rejection was systematic rather than
occasional.

- [ ] **Story 4.1 — Instrument lint-rejection frequency.** Add lightweight logging/counting of which
      `LR-*`/`CL-*` rule IDs fire across runs (could be as simple as appending to a JSONL file each
      time `lint_document` returns a HARD_BLOCK). `[VERIFY]` whether `data/submissions/*/*.json`
      lint reports already accumulate anywhere queryable — if so, this story may just be "write the
      query," not "add new instrumentation."
- [ ] **Story 4.2 — Static-scan every template literal and reference markdown file the drafting engine
      reads** (`summary_builder.py`, `Resume_Style_Reference.md`, `Cover_Letter_Reference.md`, any
      other `_TEMPLATE_*` constants — `[VERIFY]` full list by grepping for `_TEMPLATE` and for files
      under `data/*.md` referenced by `draft_compiler.py`) against the same forbidden-phrase/em-dash
      rules the lint pass enforces on generated output. A hard-coded source string violating its own
      lint rule should be impossible to ship, not just probable-but-unverified.
- [ ] **Story 4.3 — Add a pre-commit or test-suite check** that scans those same static sources for
      forbidden patterns, so a future template edit can't reintroduce this class of bug silently.

---

## Epic 5 — Deduplication Fix (carried over from CR-053's calibration data)

**Goal:** 8 of the 62 confirmed self-rejects (15%) were flagged "duplicate" — the same listing
re-surfacing from a different source or a re-scrape. This is a real, quantified leak, separate from
both scoring accuracy and failure-transparency, but small enough to fold in here rather than spin up
a third CR.

- [ ] **Story 5.1 — Confirm current dedup logic.** Per `project_applyr.md` memory, Cluster 3 (job
      ingest/dedup: `job_ingest_raw`, `job_clusters`, `job_source_links`) was implemented in Story 3.1
      and 3.2 of the original connector-architecture epic — `[VERIFY]` this is actually wired into the
      live scout path and not just present as unused tables, given 8 confirmed dupes got through.
- [ ] **Story 5.2 — Root-cause why these 8 specific duplicates weren't caught**, using the same
      JD-text-pull-and-replay method as CR-053 Epic 1 Story 1.1.
- [ ] **Story 5.3 — Fix + regression test** using the confirmed-miss set as fixtures.

---

## Rollout note (applies to both CR-053 and CR-054)

Do CR-054 Epic 1 first regardless of what else is in flight — it's a few hours of work, it's the
highest-consequence bug found in this diagnosis, and it doesn't depend on or block the scoring rebuild
in CR-053. Everything else can be sequenced by whichever epic has the best evidence-to-effort ratio
once Epic 1 ships; re-rank using the calibration data in CR-053 Epic 4 once that exists, rather than
guessing at priority order in advance.

---
---

# CR-055 — Collection Gate Accuracy: Epics & Stories

**Why this is a third, separate CR:** CR-053 is about scoring accuracy on jobs that reach scoring.
CR-054 is about the pipeline being honest about its own failures. CR-055 is about a different failure
class entirely — **jobs killed at the deterministic collection gates, before they ever reach scoring,
that you never get a chance to see or correct.** The self-rejected-after-≥72-score data used to
calibrate CR-053 is structurally blind to this category: it can only show jobs that passed the gates
and got scored. To find this, the source `activity_log` table (32,764 rows, back to April) was queried
directly for gate-kill messages instead of relying on post-scoring outcome data. This is real
production log data, not a code-reading inference — every example below has a timestamp and a real
company name behind it.

**Why this matters more than it might look:** CR-053/054 improve what happens to jobs that survive to
scoring. CR-055 is about jobs that never get that chance. If the title blocklist is killing correctly
leveled "Product Manager, Growth" roles before scoring ever sees them, no amount of fit-rubric accuracy
fixes that — the job is simply never shown to you.

## Top-line evidence (June 2026, 3,770 reject events from `activity_log`)

| Reason | Count |
|---|---:|
| Title Blocklist | 1,229 |
| Stale (freshness window) | 627 |
| not_pm_title_scope | 596 |
| target_role_scope:Product Manager | 523 |
| Duplicate (URL/Company+Title) | 570 |
| Location/remote-signal reject | 168 |
| Years-gate parsing error (confirmed, see Epic 1) | 1 found in this sample, mechanism likely recurring |

Re-derive this table with:
```sql
SELECT message FROM activity_log
WHERE timestamp >= '2026-06-01' AND (message LIKE 'Skipped:%' OR message LIKE '[REJECT]%');
-- then bucket by the reason suffix after the last ' - '
```

---

## Epic 1 — Years-Gate Regex Producing Nonsense Requirements (confirmed live, not hypothetical)

**Confirmed evidence:** `activity_log` message `"Remote at The Jackson Laboratory — required_years_90_exceeds_max_7"`
— a real job killed because `seniority_gate.py:parse_max_years_required` parsed **"90 years"** as a
stated JD requirement. No employer requires 90 years of experience; this is a stray number near the
word "years" elsewhere in the JD body (same failure class as the earlier Civica "21 years" false
reject found in CR-053's original diagnosis, now confirmed with a second live, dated example).

- [ ] **Story 1.1 — This is the same root cause as CR-053 Epic 2 Story 2.2 (must-have extraction
      requiring requirements-sentence anchoring).** Do not build a second fix — if CR-053 Epic 2 is
      in progress, land the regex/anchoring fix there and close this story as "implemented via
      CR-053 Epic 2." If CR-053 Epic 2 hasn't started yet, this live evidence is a strong argument to
      pull that story forward ahead of the rest of CR-053's architecture work, since it's a narrow,
      self-contained bugfix independent of the larger evidence-tiering rebuild.
- [ ] **Story 1.2 — Quantify true blast radius.** Only 1 instance surfaced in the June `activity_log`
      sample by exact-match on `required_years_`, but the underlying regex bug (`seniority_gate.py:
      12-23 _YEARS_PATTERNS`) scans the entire JD body, so this likely undercounts — a false years
      figure could also silently lower a score without producing a hard "exceeds_max" reject message
      (e.g. a parsed-but-not-rejected value affecting `years_lock_prompt_block`'s prompt injection).
      Pull a larger sample (e.g. all of `data/jobagent.sqlite.jobs.jd_text` run through
      `parse_max_years_required` directly, offline) and report how many return an implausible figure
      (>25, say) to size this properly before calling it "1 job lost."
- [ ] **Story 1.3 — Regression test** using the Jackson Laboratory JD text (or a fixture derived from
      its actual content) as a fixture: `parse_max_years_required` must not return 90 for that posting.

---

## Epic 2 — Title Blocklist: Contextual Matching, Not Whole-Line Substring Matching

**Confirmed evidence:** sampled all 33 PM-titled jobs killed by "Title Blocklist" in June. Two distinct
false-positive patterns, both real, both losing correctly-leveled PM roles before they reach scoring:

1. **`"Growth"` is a blanket single-word block** (`candidate_preferences.json: blocked_titles`).
   Confirmed losses: `Product Manager, Growth at Pacvue`, `Product Manager, Growth at Jerry`,
   `Product Manager, Platform Growth at JamLoop` — all plain "Product Manager" level, all within
   experience range, killed solely because "Growth" appears anywhere in the title. The block can't
   distinguish "Head of Growth" (a role-type correctly excluded) from "Product Manager, Growth" (a
   properly-scoped PM role with a growth focus area).
2. **Adjacent-discipline blocklist terms match anywhere in the title line, not just as the primary
   role descriptor.** Confirmed loss: `Senior Product Manager, AI Platform and Developer Productivity
   at NVIDIA` — killed because `"Developer"` is in `blocked_titles` and `seniority_gate.py:43-66
   title_matches_blocked` / `title_blocked` does whole-title-line word-boundary scanning with no
   awareness of what role the word is modifying. Same mechanism would false-positive on any PM title
   that mentions "Designer," "Marketer," or "Software Engineer" as a focus area rather than the actual
   role.

- [ ] **Story 2.1 — Decide the design fix.** Two options, pick one (or both, layered):
      (a) **Positional/structural heuristic** — only treat a blocked term as a hit if it appears
      before the first comma/pipe in the title (the typical "role, focus-area" structure: "Product
      Manager, Growth" vs. "Head of Growth, Product"), or if it's not immediately preceded by a
      product-manager-role phrase. Cheap, deterministic, auditable, no LLM call. `[VERIFY]` this
      heuristic against a larger title sample before trusting it — title formatting isn't fully
      consistent across sources (some use "—", some use "|", some have no separator at all, e.g.
      "Growth Product Manager (Principal)" puts Growth *before* the role).
      (b) **Two-list split** — separate `blocked_role_type_titles` (Staff, VP, Head, Principal,
      Director, etc. — words that ARE the role designation) from `blocked_focus_area_words` (Growth,
      Developer, Designer, Marketer — words that function as a *modifier* and should only block when
      they appear as the apparent primary role, e.g. "Growth Lead" or "Head of Growth," not as a
      trailing focus-area descriptor). This is more auditable than a positional heuristic and doesn't
      depend on punctuation consistency across sources, at the cost of needing the list curated once.
      Recommend (b) over (a) for auditability, but `[VERIFY]` against more sampled titles before
      committing — this needs more than the 33-title sample already pulled to be confident.
- [ ] **Story 2.2 — Re-classify the existing `blocked_titles` list** in `candidate_preferences.json`
      against whichever design from 2.1 is chosen. Don't silently change values — show the before/after
      classification in this doc or a linked artifact so the change is auditable.
- [ ] **Story 2.3 — Pull a larger title sample** (not just June, not just 33 PM-titled hits) to find
      other blocklist terms with the same disease before calling this fixed. `"Lead"`, `"Associate"`,
      and `"Manager of"` are also blanket single-word/phrase blocks and were not checked this session —
      `[VERIFY]` whether they have the same false-positive pattern as "Growth" and "Developer" before
      assuming they're clean.
- [ ] **Story 2.4 — Regression tests** covering: a true positive that should still block ("Head of
      Growth" → blocked), a false positive from this session's evidence that should now pass ("Product
      Manager, Growth" → not blocked), and the NVIDIA case ("Senior Product Manager, AI Platform and
      Developer Productivity" → not blocked).

---

## Epic 3 — Freshness Window Sanity Check (open question, not yet a confirmed bug)

**Not confirmed as wrong — flagged for a deliberate decision, not a silent default.** 627 of 3,770
June rejects (17%) are `"Stale"`, governed by `candidate_preferences.json: freshness_days: 7`. This
is the second-largest reject bucket after Title Blocklist. It is plausible this window is correctly
tight (don't bother applying to month-old listings that are likely already filled) — but it's equally
plausible some sources lag in indexing and a 7-day window is silently dropping real, still-open
postings before they're ever surfaced. This has not been investigated with the same rigor as Epics 1-2;
it's flagged here so it isn't lost, not because a bug is confirmed.

- [ ] **Story 3.1 — Sample a handful of "Stale" rejects and manually check whether the listing is
      actually still open** (re-visit the URL if still resolvable, or check posting-age metadata from
      the source). If most "Stale" kills are genuinely expired, the window is fine and this epic
      closes as "verified correct, no action." If a meaningful fraction are still open, that's a real
      finding worth its own story.
- [ ] **Story 3.2 — If Story 3.1 finds real loss, decide a new `freshness_days` value with Jason**
      rather than picking one — this is a judgment call about how aggressively to chase fresh-only
      listings vs. casting a wider net, not something to infer from data alone.

---

## Rollout note (CR-053 / CR-054 / CR-055 combined priority)

Updated priority ranking given all three CRs: **(1) CR-054 Epic 1** (silent failure reporting — cheap,
highest consequence), **(2) CR-055 Epic 1** (years-gate fix — same root cause as CR-053 Epic 2 Story
2.2, pull it forward since it's narrow and has two confirmed live losses), **(3) CR-055 Epic 2**
(title blocklist contextual matching — confirmed losses, moderate effort), **(4) CR-053 location gate
fix (Epic 1)** and the rest of CR-053's architecture rebuild, **(5) CR-054 Epics 2-5** and **CR-055
Epic 3** as they're lower-confirmed or lower-consequence. Re-rank again once CR-053 Epic 4's
calibration harness exists — that will surface whether this ranking still holds once there's a way to
measure it instead of reasoning about it.
