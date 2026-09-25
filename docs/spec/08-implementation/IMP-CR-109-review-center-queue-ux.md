# IMP-CR-109 — Review Center queue UX, extraction precision, bad-data loop

Implementation notes for [CR-109](../05-change-requests/CR-109-review-center-queue-ux-and-extraction-precision.md).
Date: 2026-09-02.

## Stories

- [x] FR-286 / BUG-001 extraction guards — `looks_like_named_tool()` rejects candidates
      followed by `:` or `)`; stopword list gained trait/qualifier/role-title/generic-tech
      vocabulary; `_contains_blocked_key()` blocks candidates containing a hard-blocked tool
      token run (Workday compounds).
- [x] FR-287 BAD_DATA answer — new answer end to end: migration 022 (CHECK rebuild),
      `stage0_confirmations.answer_confirmation`, `stage0_harness.question_envelope`,
      `reviewCenterRepository`, route vocabulary, UI "Not a real skill" button. Durable
      `skill_memory` decision `BAD_DATA` at evidence level 0 suppresses re-queueing because
      `_prepare_skill_confirmations` skips any skill with existing memory.
- [x] FR-288 single-tap auto-advance — `ReviewDetail` answer buttons call the save path
      directly; `ReviewCenterView.handleAnswer` precomputes the next visible card and selects
      it after the save/refresh; `animate-card-swap` (240ms fade+rise) plays on the keyed
      remount. No "Save answer" button remains. Corrections from the Completed queue stay on
      the same card (no advance).
- [x] FR-289 completed-card correction — `listReviewItems`/`mapGroup` now surface `answer`;
      client normalizes it; completed cards show "Your answer: ..." plus a Change answer
      button reopening the pad in place. Re-answers append to `review_answer_history`.
- [x] DATA-005 privacy — verified `data/jobagent.sqlite` is covered by `*.sqlite*` and
      untracked; `.gitignore` comment now names this explicitly.

## Design notes

- The inline "add optional context" form on skill_presence cards was removed, not lost: a Yes
  already auto-creates an evidence_enrichment card in the Strengthen queue, which is now the
  single place where details are entered. This is what makes one-tap Yes safe.
- Migration 022 rebuilds three tables because SQLite cannot ALTER a CHECK constraint. It is
  idempotent (staging-table copy/drop/rename) because `stage0_confirmations._connect()` runs
  every migration file on each connection.
- Label-shape guard trade-off (documented in the CR): a genuinely unknown tool written as a
  bare `ToolName:` label no longer queues. Accepted — label shapes produced only junk in the
  live queue, and the BAD_DATA loop covers the residual tail in the other direction.

## Verification

- `scripts/test_stage0_confirmations.py` — 17 tests pass (3 new: label shapes, Workday
  containment, BAD_DATA durability).
- `tests/unit/reviewCenterRepository.test.ts`, `tests/unit/reviewCenterRoute.test.ts`,
  `src/lib/reviewCenter.test.ts` — 16 tests pass (4 new).
- `scripts/test_build_stage0_fit_gate.py` (152 tests) and
  `scripts/test_stage0_checkpoint_failures.py` pass.
- `scripts/test_stage0_model_handoff.py` — 16 tests pass. Its two score-model-pin tests
  were stale (they asserted `classify_requirement` pins a local Ollama model, but the
  2026-09-01 in-flight change moved evidence_scale to cloud Groq/Gemini and relocated the
  pin to `build_stage0_fit_gate._prepare_stage0_score_model`); rewritten to assert the pin
  and FIT_MODEL bakeoff override at their new home.
- Full `npm test`: 47 suites passed, 0 failed. `tsc --noEmit` and ESLint clean.
- `git check-ignore -v data/jobagent.sqlite` → matched by `*.sqlite*`;
  `git ls-files` shows no answer-bearing file tracked.

## Open items

- TEST-109D (manual UI pass of the single-tap flow and transition in the running app) is
  proposed, pending Jason's click-through.
- Existing junk rows in Jason's live queue are intentionally left for one-tap BAD_DATA
  dismissal (each dismissal is the learning signal); no cleanup script was run.
