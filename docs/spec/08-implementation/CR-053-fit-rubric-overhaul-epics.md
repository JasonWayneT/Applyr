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

- [x] **Story 1.1 — Root-cause the 30 confirmed location misses.** 26 location-related self-rejects
      in DB; **26/26 have empty `jd_text`** (pre-column scrape era) so replay was impossible from DB
      alone. Failure patterns inferred from `outcome_notes` + synthetic fixtures: non-SD
      onsite/hybrid cities, Canada in-person, EST/CST-only remote. See `scripts/_diag_location_misses.py`.
- [x] **Story 1.2 — Fix or extend `classify_onsite`/`resolve_location_verdict`** — non-SD city +
      onsite/hybrid without remote, Canada in-person, EST/CST timezone-restricted remote (`zero_shot_classifier.py`).
      Hiring-state semantic restrictions deferred to structured-fit equivalence path (Epic 2).
- [x] **Story 1.3 — Regression tests.** `scripts/test_location_gate.py` (10 synthetic fixtures from
      calibration notes; all red→green).
- [x] **Story 1.4 — Re-score affected jobs.** `scripts/rescore_location_gates.py` (dry-run default;
      `--apply` updates Backlog/New rows only).

---

## Epic 2 — Evidence-Tiered Deterministic Scoring Architecture

**Goal:** replace the single holistic LLM score with: deterministic field extraction → narrow LLM
equivalence judgments (yes/partial/no per requirement, one sentence justification, never a number) →
deterministic score computation in code. This is the architectural core of the original brief.

- [x] **Story 2.1 — Define the data model.** `scripts/structured_fit.py` — `FitReport`, `MustHave`,
      `CriterionScore`, `EvidenceItem` dataclasses with tiers and `verifiable_against_source`.
- [x] **Story 2.2 — Must-have extraction.** `extract_must_haves()` + years anchoring in
      `seniority_gate.parse_max_years_required()` (shared fix for CR-055 Epic 1).
- [x] **Story 2.3 — Narrow LLM equivalence-judgment call.** `_call_equivalence_llm()` returns
      judgments only; heuristic fallback when LLM unavailable. Primary path in `evaluate_job_fit`
      when `STRUCTURED_FIT=1` (default).
- [x] **Story 2.4 — Deterministic score computation.** `compute_fit_report()` with weighted criteria
      and verifiability cap at 3 without tier-1/2 verified evidence.
- [x] **Story 2.5 — Confidence-score routing.** `confidence_score` + `min_confidence_score` pref;
      high score + low confidence → `REVIEW` (surfaced as `NO` + `needs_manual_review` flag).
- [x] **Story 2.6 — Retire `apply_anchor_floor` score-overwrite.** Anchor hits append `RiskFlags` only
      (`fit_policy.py`); REG-18 updated in smoke regression.

---

## Epic 3 — Domain Fit as a Bounded, Scored Signal

**Goal:** stop ignoring domain mismatch, without letting it dominate or auto-reject strong
transferable-skills candidates. Per the original brief and Jason's explicit instruction
("can't weight it so much that a simple domain miss is going to bounce the opportunity").

- [x] **Story 3.1 — Decide placement in the criteria table.** Domain is a bounded `-10` penalty in
      `structured_fit._domain_penalty()`, not a weighted column.
- [x] **Story 3.2 — Define domain requirement vs preference.** Reuses `detect_optional_domain_note()`.
- [x] **Story 3.3 — Implement the bounded penalty.** Max 10pt; capped explicitly in code.
- [x] **Story 3.4 — Regression test.** `scripts/test_structured_fit.py` (IAM required vs strong JD;
      optional-domain note skipped).

---

## Epic 4 — Calibration Against Real History & Test Matrix

**Goal:** prove the rebuilt rubric actually agrees with Jason's real past judgment before trusting it
live. Do not skip — the original brief is explicit that disagreement on "obvious" cases is a rubric
bug, not a quirk to note and move past.

- [x] **Story 4.1 — Build a calibration harness.** `scripts/calibration_harness.py`.
- [ ] **Story 4.2 — Report disagreements.** Harness runnable; most high-score self-rejects lack
      `jd_text` in DB so disagreement count is unreliable until JD backfill — re-run after scrape
      coverage improves.
- [ ] **Story 4.3 — Implement the test matrix.** Partial: `test_structured_fit.py` + location/title/years
      fixtures cover subsets; full 10-case matrix still open.

---

## Epic 5 — Rollout

- [ ] **Story 5.1 — Re-run this session's 5 passing/1 failing CSV batch** (Accompany Health, Private
      Health Management, Rencata, TE Connectivity, TrellisWare) through the rebuilt pipeline once
      Epics 1-4 are done. Compare new scores/decisions against the original 95/92/85/95/85. Report
      deltas — this is a live sanity check using a case you already have full context on.
- [x] **Story 5.2 — Update `.agent/rules/job_fit_engine.md`** to reflect actual implemented logic
      (v5.0: structured fit default, title split, location gate, anchor risk-only, CR-054 audit note).
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

- [x] **Story 1.1 — Root cause, confirmed.** `scripts/drafting_engine.py:377-385`:
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
- [x] **Story 1.2 — Give `audit_and_improve_company` a real return contract.** Returns
      `AuditImproveResult(converged, attempts, final_issues, skipped)` dataclass from
      `scripts/audit_and_improve.py`.
- [x] **Story 1.3 — Propagate non-convergence to the caller.** `run_drafting_engine` raises
      `RuntimeError` when `converged=False`; `batch_pipeline.process_single` already catches and
      emits `{"score": score, "passed": false, ...}`.
- [x] **Story 1.4 — Decide what happens to a non-converged draft already on disk.** Policy:
      snapshot Resume.md/CoverLetter.md/PDFs before audit loop; restore snapshot on non-convergence
      so enhanced-but-failed content never ships under normal filenames.
- [x] **Story 1.5 — Regression test.** `scripts/test_audit_convergence.py` — forced non-convergence
      asserts `converged=False`, file restore, `run_drafting_engine` raise, and `process_single`
      `passed:false` JSON.

---

## Epic 2 — Audit the Other Swallow-and-Continue Exception Blocks

**Goal:** the Epic 1 bug wasn't a one-off pattern — `grep -rn "except Exception" scripts/*.py` returns
120 hits, of which a quick scan found 25 that print-and-continue with no caller-visible failure signal.
Not all 120 are load-bearing (many are legitimately "best-effort, log and move on" — e.g. cheat-sheet
generation already has its own explicit `[cheat_sheet, status: warning]` JSON event, which is the
correct pattern). The goal is to find which of the rest behave like Epic 1's bug, not to rewrite all
exception handling indiscriminately.

- [ ] **Story 2.1 — Triage the 120.** Abbreviated triage (2026-07-01): drafting-critical paths
      (`drafting_engine`, `audit_and_improve`, `batch_pipeline.process_single`) now propagate failures;
      `draft_compiler` lint/strict paths log warnings but PDF export failure raises; cheat_sheet uses
      explicit JSON warning (model). Full 120-row table deferred — no additional category-(b) bugs
      found beyond Epic 1 in drafting success path.
- [ ] **Story 2.2 — Fix category (b) blocks** — covered by Epic 1 for audit convergence.
- [ ] **Story 2.3 — Regression coverage** — `test_audit_convergence.py`.

---

## Epic 3 — Connect Manual Judgment to Deterministic Gates

**Goal:** a job you've explicitly flagged "do not apply" in writing should never reach `Applied` again,
full stop — independent of whatever the LLM or scoring logic decides on a re-run.

- [x] **Story 3.1 — Confirmed gap.** Unity Applied row vs CLAUDE.md note — still valid evidence.
- [x] **Story 3.2 — Design the enforcement mechanism.** `blocked_companies` in
      `candidate_preferences.json`; checked in `passes_jd_keyword_gate` before title gate.
- [ ] **Story 3.3 — Backfill from existing signal.** Unity in example prefs only; bulk backfill needs
      Jason review per doc (not auto-run).
- [x] **Story 3.4 — Regression test.** `scripts/test_blocked_companies.py`.

---

## Epic 4 — Guardrail Audit (find the other dormant template-literal bugs)

**Goal:** the em-dash bug fixed in CR-053's session wasn't an LLM mistake — it was hard-coded into
`scripts/summary_builder.py`'s template literals and `data/Resume_Style_Reference.md`, meaning the
lint rule (`LR-006`) had presumably been silently rejecting drafts on every run that hit that code
path, for an unknown period, with nothing flagging that the rejection was systematic rather than
occasional.

- [ ] **Story 4.1 — Instrument lint-rejection frequency.** Deferred; no JSONL accumulator yet.
- [x] **Story 4.2 — Static-scan template literals.** `test_template_lint_sources.py` lints rendered
      `summary_builder` templates (output path, not instructional reference markdown).
- [x] **Story 4.3 — Test-suite check.** Included in `run_all_tests.py`.

---

## Epic 5 — Deduplication Fix (carried over from CR-053's calibration data)

**Goal:** 8 of the 62 confirmed self-rejects (15%) were flagged "duplicate" — the same listing
re-surfacing from a different source or a re-scrape. This is a real, quantified leak, separate from
both scoring accuracy and failure-transparency, but small enough to fold in here rather than spin up
a third CR.

- [x] **Story 5.1 — Confirm current dedup logic.** `server/services/clusterDedup.ts` exists with unit
      tests but is **not imported by scout/sync routes** — dedup tables are unused in live ingest.
- [ ] **Story 5.2 — Root-cause why these 8 specific duplicates weren't caught** — blocked on wiring
      gap from 5.1; duplicate rejects in `activity_log` use URL/company+title heuristic in scout, not
      `clusterDedup`.
- [ ] **Story 5.3 — Fix + regression test** — requires wiring `clusterDedup` into ingest path (follow-up).

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

- [x] **Story 1.1 — Implemented via CR-053 Epic 2 / `seniority_gate.py` requirements anchoring.**
- [x] **Story 1.2 — Quantify blast radius.** Offline scan: implausible (>25) parses only when experience
      context present; Jackson/Civica fixtures fixed. Run `parse_max_years_required` over full DB when
      `jd_text` coverage improves for exact count.
- [x] **Story 1.3 — Regression test.** Jackson + Civica fixtures in `test_seniority_years_gate.py`.

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

- [x] **Story 2.1 — Design fix.** Two-list split: `blocked_role_titles` vs `blocked_focus_area_words`
      with contextual matching in `seniority_gate.title_blocked()`.
- [x] **Story 2.2 — Re-classify blocked titles.** See `candidate_preferences.example.json` — role vs
      focus split documented; legacy `blocked_titles` flat list retained for backward compatibility.
- [ ] **Story 2.3 — Pull a larger title sample** — Lead/Associate/Manager-of patterns not exhaustively
      verified beyond June 33-title sample; monitor activity_log after deploy.
- [x] **Story 2.4 — Regression tests.** `scripts/test_title_blocklist.py`.

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

## Session Evidence — 2026-07-13 (raw findings, not yet triaged into epics/stories)

Logged during a same-day apply push (Jason needed assets today, prioritized getting drafts over
fixing the pipeline; findings captured here for a future dedicated fix session). Three jobs run
through `batch_pipeline.py --mode single` end to end: Cresta (Platform PM, IAM), SailPoint (PM,
Certification & Governance), Group 1001 (Senior PM, Onyx annuity platform). All three failed at the
fit-scoring gate; assets were then generated via manual DB override + `--draft-only` per Jason's
explicit go-ahead, with manual polish afterward. Every finding below is a fresh, reproducible instance
of a *distinct* failure mode, not a repeat of the calibration data already logged in Epic 0.

1. **Identical-score clustering across dissimilar JDs — new evidence for the "opaque single LLM call"
   problem (point 1 in "Why this exists").** All three jobs scored exactly **60** (below the 72
   threshold) on the first pass, despite being structurally different roles (identity/access platform
   PM, identity governance PM, insurance platform PM) with none of Jason's hard exclusions present
   (no 0-to-1, no people management, no AI/ML ownership, no revenue/billing). A real holistic judgment
   producing the *same* integer three times in a row across different JDs is itself suspicious — worth
   pulling the raw LLM completions for these three (if still recoverable from `model_manager.log`) as
   calibration evidence once Epic 4's harness exists.

2. **New confirmed instance of the CR-054 "passed: true on a failed draft" pattern — SailPoint.**
   `data/submissions/sailpoint/cl_lint_report.json` (intermediate) reported `"passed": true`, but the
   final `lint_report.json` for the *same generated file* reported `"passed": false"` with a blocked
   hard rule (`LR-004`, forbidden phrase "proven track record", plus a transition-fluff warning). The
   pipeline still wrote and left `CoverLetter.pdf` on disk containing the blocked content — the CLI's
   only visible signal was a downstream `compile_single.py` non-zero exit buried in a stack-trace-style
   error, not a clear "this document is blocked" message. A human (or another agent) reading the CLI
   output casually could easily miss that the on-disk PDF was invalid. Manually fixed by rewriting the
   flagged paragraph; relevant to CR-054 Epic on failure transparency.

3. **New bug: page-count guard reported failure but final export succeeded — Cresta.** Mid-run log
   showed `Page-count guard: cannot prune further (floor reached)` and `Page-count guard: 1 prune(s) —
   STILL 2 pages`, but the actual final `Resume.pdf` on disk (after the self-healing retry loop
   completed) was 1 page and lint-clean. Either the guard's warning fires on an intermediate draft
   before a later successful prune, or the log message is stale/mis-ordered relative to the real final
   state. Not confirmed dangerous (final artifact was fine) but confusing enough to burn review time
   chasing a non-issue — worth making the log message unambiguous about which attempt it refers to.

4. **New bug: numeric-hallucination guard false-positives on digits embedded in the company name —
   Group 1001.** Cover letter drafting crashed outright (`SUCCESS` never reached, no `CoverLetter.md`
   ever written) with `Cover letter numeric audit: Document introduces numbers not in bullet corpus:
   ['1001']`. The "1001" is literally the second word of the company name "Group 1001", not a
   fabricated metric — the numeric-audit function almost certainly scans the letter body for bare
   digit sequences without excluding tokens that already appear in the company name. This is a hard
   pipeline failure (not just a linter warning), meaning any company with a number in its name (e.g.
   "Group 1001", "Big Bang 1", "1Password"-style names) cannot draft through the automated path at all.
   Cover letter was hand-drafted from the same claim catalog codes the compiler had already selected
   (`ACC-101-TECH`, `ACC-103-ROADMAP`, `ACC-105-PROCESS`, `ACC-113-ADOPTION`) to keep it consistent
   with what the engine would have produced, then run through `submission_linter.lint_document` and
   `quality_checker.check_resume` manually — both clean, 242 words, 1 page after compile.

5. **Unverified claim shipped to a live resume without a hard block — `ACC-111-ENTERPRISE`
   (Cresta).** The compiler's own catalog validation logged `ACC-111-SCOPE: no workExperience anchor
   for ACC-111` and `ACC-111-ENTERPRISE: metric '38' not in approved list` as warnings, then shipped
   the bullet ("Maintained a secondary legacy enterprise platform for approximately 38 high-revenue
   enterprise accounts...") into `Resume.md` anyway. Grepped `data/workExperience.md` for "38",
   "secondary", "two separate", "multi-platform" — zero matches. This claim has no ground-truth anchor
   at all, unlike the already-disabled `ACC-114` ($800K Canadian platform deprecation), which was
   caught and flagged `"disabled": true` in `master_claims.json`. `ACC-111-SCOPE`/`ACC-111-ENTERPRISE`
   were never disabled despite carrying the identical failure signature (no workExperience anchor).
   Manually replaced with the verified `ACC-107-PLATFORM` claim before sending. **Actionable fix:**
   any claim whose catalog validation logs "no workExperience anchor" should be hard-blocked from
   drafting, the same way `ACC-114` is, not merely warned about — the current soft-warning behavior
   is a silent path for unverified claims to reach a document Jason actually sends. Worth auditing
   `master_claims.json` for any other claim carrying this same warning signature before it ships again.
   **Update 2026-07-13, batch 2:** found a second live instance of this exact bullet in Redox's resume
   (drafted 2026-07-10, before this fix existed) — confirms this was not a one-off, the unanchored
   claim was actively being selected by the compiler across multiple runs. Fixed the same way.

6. **Systemic: one closing paragraph used as a template fallback across 6 of 12 unrelated JDs.**
   Full write-up in `data/jd_gap_analysis_log.md` ("2026-07-13 batch 2" section) — the exact same
   "shelved migration / retention mandate" paragraph (`ACC-104` lifecycle framing) appeared
   word-for-word in Buyers Edge Platform, Ontra, Remote, Tilt, Redox, and Covideo's cover letters, at
   least 4 of which have nothing to do with migrations, legacy platforms, or churn/retention in their
   JD. Two hook lines ("The friction that builds up in a product's identity and admin layer...",
   "Customer-facing friction rarely announces itself on the roadmap...") showed the same pattern across
   Buyers Edge, Tilt, PAR, and Lumos. This is the single highest-recurrence defect found across both
   review batches (6/12 letters) and is almost certainly the same root cause as finding 1 above (opaque,
   single-shot LLM generation with no per-claim JD-fit check) manifesting as a fallback/default rather
   than a scoring artifact. Worth prioritizing a look at why the compiler converges on this specific
   paragraph so often — possibly a claim-selection weighting issue where `ACC-104` variants score as
   generically "safe" across too wide a range of JD-fit profiles.

**Suggested triage order for a future session (updated 2026-07-13 batch 2):** (6) now outranks
everything else — a defect confirmed in 6 of 12 letters reviewed is a bigger real-world impact than a
single crash bug, and it directly degrades conversion quality (mismatched proof points) on every
future submission until fixed. (5) and (4) are next, both outright-crash or silently-wrong-output bugs
— (5) especially, since it's the one that can put a fabricated claim in front of a hiring manager
without any error surfacing at all, and it has now recurred twice (Cresta, Redox). (2) is a CR-054
transparency issue already tracked at the epic level (add this as a concrete repro case). (1) needs
the Epic 4 calibration harness before it's actionable. (3) is low priority (cosmetic log confusion, no
bad output reached the user).

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
