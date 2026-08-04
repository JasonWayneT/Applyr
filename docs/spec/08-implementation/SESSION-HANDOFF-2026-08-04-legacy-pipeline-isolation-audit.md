# SESSION HANDOFF — 2026-08-04 — Legacy pipeline isolation audit, handed to Cursor

**Purpose of this doc:** cross-harness handoff. A Claude Code session pressure-tested an external audit
doc (`docs/reports/applyr_audit_final.md`) against the real codebase and confirmed a real problem: the
retired deterministic generation pipeline (`draft_compiler.py`, `batch_pipeline.py`, and everything that
hangs off them) is still sitting directly in `scripts/` next to the live pipeline, imported by ~25 other
scripts. Jason's goal: **isolate the current live process from the dead code so a future session reading
`scripts/` isn't also reading retired stuff and getting confused about what's actually running.**

This is an audit-then-move task, not a blind sweep. Do the classification first, move only what's
unambiguous, and stop for Jason's call on anything genuinely uncertain — same discipline as any other
change to a pipeline this load-bearing.

## Background you need

- **The live authoring process is `generate-submission/SKILL.md` v2.0.0.** Its own text says: *"This
  replaces an earlier version of this file that still called `draft_compiler.run()`... That deterministic
  path is retired for authoring."* Stage 1 authoring today is direct LLM reasoning grounded in
  `workExperience.md`/`master_claims_tags_only.json`, not a Python orchestration call.
- **CR-070 already made an explicit decision to keep some old code paths as opt-in, not delete them** —
  the old Ollama-based local-LLM call sites were "kept intact/opt-in per Jason's instruction (not
  deleted)." Anything in that category must land in a different tier than genuinely dead code — see
  Tier 3 below. Don't relitigate that decision here; just classify correctly.
- **CR-062's `local_rewrite.py` is opt-in, not yet default** — same treatment, not dead.

## The task

Classify every script in `scripts/` into exactly one tier, then act only on Tier 1.

### Tier 1 — DEAD (move to `scripts/archive/`)
Not reachable from any live entry point (see list below), directly or transitively, and not an
intentionally-kept opt-in fallback per a prior CR decision.

### Tier 2 — LIVE (leave in place, do not touch)
Reachable from a live entry point today.

### Tier 3 — OPT-IN-FALLBACK-STILL-WANTED (leave in place, but flag clearly)
Not called by the default path, but kept deliberately per an existing CR decision (CR-070's Ollama
fallback, CR-062's `local_rewrite.py`, etc.). Do not move these. Do add a short docstring banner at the
top of each (if one isn't already there) noting it's opt-in and which CR governs it, so a future reader
doesn't mistake "not called by default" for "dead."

### Anything ambiguous → its own **"STOP — needs Jason's call"** list in your final report. Don't guess,
don't move it, don't leave it unresolved either — surface it explicitly.

## Known live entry points to trace from

Verified live in the prior session — start here, don't take these on faith either, confirm them as part
of the audit:
- `scripts/compile_single.py` (MD → PDF, imports `submission_linter`)
- `scripts/verify_submission.py` (imports `submission_linter`, `quality_checker`, `approved_metrics`,
  `jd_term_extractor`)
- `scripts/check_ground_truth_coverage.py`
- `scripts/jd_term_extractor.py` (new, CR-073, 2026-08-04)
- `.claude/skills/generate-submission/SKILL.md`'s own text — read it in full; it names specific scripts
  directly as required commands (`verify_submission.py`, `check_ground_truth_coverage.py`,
  `compile_single.py`)
- Any `server/**/*.ts` route that shells out to a Python script — grep `server/` for `.py` references,
  don't assume the list above is exhaustive from the Python side alone

## Seed findings from the prior session — verify, don't just trust these

A grep already ran once and found this import graph. Re-confirm it as part of the audit rather than
copying it blind, but it's a real head start:

- `draft_compiler.py` and `batch_pipeline.py` are imported by ~25 scripts, many of them one-off
  company/date-specific batch runners that look like historical single-use tools, not a maintained path:
  `batch_reeval_pm_rejections.py`, `calibration_harness.py`, `cleanup_pending_backlog.py`,
  `draft_csv_passers.py`, `draft_passed_jobs.py`, `draft_pending_assets.py`,
  `draft_soft_shortlist_4_7.py`, `evaluate_csv_jobs.py`, `evaluate_jd_only.py`,
  `final_retry_needs_retry.py`, `promote_and_retry_batch2.py`, `report_csv_rejections.py`,
  `refresh_backlog_summaries.py`, `regenerate_backlog.py`, `re_score_jobs.py`,
  `regenerate_all_resumes.py`, `regenerate_all_cover_letters.py`, `run_csv_batch2_draft.py`,
  `_draft_applyr_jobs_3.py`, `_draft_cambridge_ottimate.py`, plus test files
  (`test_batch_gate.py`, `test_blocked_companies.py`, `test_jd_completeness.py`).
  **Check file mtimes / git log per file before bulk-classifying these as dead** — a couple of these
  names read as generic enough (`regenerate_backlog.py`) that they could still be manually invoked
  periodically rather than truly one-off. Don't assume from the name alone.
- `draft_compiler.py` imports directly **from** `quality_checker.py` (`HEADER_BLOCK`, `check_resume`,
  `check_and_repair_cover_letter`, etc.) — the dependency runs retired→active, not the reverse. This means
  **`quality_checker.py` is Tier 2 (LIVE)** regardless of what happens to `draft_compiler.py` — archiving
  the retired file cannot break it.
- `structured_fit.py` is **not cleanly dead** — `fit_judgment_io.py` exists specifically for CR-070 Epic 2
  (the in-progress *active* Claude-native pipeline direction) and is built to feed
  `structured_fit.evaluate_structured_fit()`'s fallback path. Classify `structured_fit.py` as Tier 2 or
  Tier 3, never Tier 1, until CR-070 Epic 3+ actually retires it for real.
- `jd_tailoring.py`'s `extract_req_section()` is called by `local_draft_stages.py`'s
  `build_skills_section()` (the `## CORE COMPETENCIES` builder, FR-195). Whether `build_skills_section()`
  itself is still invoked by any live path, or whether Stage 1's direct-authoring LLM just replicates its
  output *shape* by following CLAUDE.md's structure rules without calling the function, is an **open
  question from the prior session — resolve it as part of this audit**, don't assume either way.

## Explicitly out of scope

- **Don't touch `docs/spec/`.** The CR-doc archive convention there is already correct and intentional —
  old CR docs stay as historical record even after their code is retired. This task is code-only
  (`scripts/`).
- **Don't touch `data/submissions/`** or any real candidate data.
- **Don't delete anything.** Move to `scripts/archive/` (mirrors the existing `data/archive/` convention
  already used for the old OpenPostings project). Nothing gets hard-deleted in this pass.
- **Tests move with their subject module.** If a script moves to Tier 1, its test file(s) move with it in
  the same commit/pass — don't leave an orphaned test in `scripts/` importing a module that's no longer
  there. Update `run_all_tests.py` / pytest discovery so it stops collecting archived tests.

## Verification before calling this done

1. Full classification table (Tier 1 / 2 / 3 / STOP) for every script currently in `scripts/`, not just
   the seed list above.
2. Before moving anything: confirm zero Tier 2 (LIVE) script imports a Tier 1 (DEAD) script, directly or
   transitively. If it does, that script isn't actually dead — reclassify it.
3. Run the existing test suite (`run_all_tests.py` or equivalent pytest invocation) **before and after**
   the move — same pass/fail counts on genuinely live code, and no import errors from orphaned tests.
4. Spot-check that `verify_submission.py` and `compile_single.py` still run clean against a real
   submission folder (e.g. `data/submissions/accertify`) after the move.
5. Report back: the full classification table, what actually moved, the STOP list for Jason's call, and
   the test-suite before/after result.
