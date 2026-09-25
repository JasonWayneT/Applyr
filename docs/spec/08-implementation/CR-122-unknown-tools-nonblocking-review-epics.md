---
status: implemented
date: 2026-09-21
change_request: ../05-change-requests/CR-122-unknown-tools-nonblocking-review.md
---

# CR-122 execution tracker

IDs: CR-122, `FR-357`–`FR-360`, `UX-001`, `AC-465`–`AC-469`.
`AC-363` superseded.

Work one unchecked story at a time. Do not pause Stage 0 on `skill_presence`. Do not write new `NOT_PRESENT` memory. Do not change extraction-review or `conversion_risk` rules. Do not Skip unknown preferred tools.

## Epic 1: Stage 0 defaults to WE (`FR-357`, `FR-358`, `AC-465`, `AC-466`)

1. [x] **1.1 Auto-absent unknown tools and do not raise `Stage0NeedsInput` for skill cards.** `_prepare_skill_confirmations` puts unknown candidates in `absent_skill_terms` without a tap, still creates grouped `skill_presence` rows. Skip the pre-score raise. After scoring, raise only on `pending_hard_reviews`. Merge model-flagged skill cards into `absent_skill_terms`. WE mention of the display name wins leftover `NOT_PRESENT`. Tests: invert `test_stage0_builder_pauses_for_unknown_named_skill_before_scoring`; preferred IBM Cloud-shaped fixture completes without `WAITING_FOR_INPUT`; hard-gate test still raises; WE mention does not absent.

2. [x] **1.2 `No` / `UNSURE_NO_REASK` do not upsert `skill_memory`.** `answer_confirmation` and `answerReviewItem` write memory only for `CONFIRMED_USE`, `VERIFIED_EVIDENCE`, and `BAD_DATA`. Card still completes. Tests in `test_stage0_confirmations.py` and `reviewCenterRepository.test.ts`.

## Epic 2: Queue does not hold on skill cards (`FR-360`, `AC-469`)

3. [x] **2.1 Blocking open count is `hard_gate_review` only.** `_review_center_open_count` / `_review_center_should_promote` / `requeue_paused`. Promote when zero open hard-gates, even if `skill_presence` is open. Tests: skill-only pause promotes; hard-gate open stays paused / requeue refuses; extraction-review and `conversion_risk` unchanged.

## Epic 3: Review Center copy (`UX-001`, `FR-359`, `AC-467`, `AC-468`)

4. [x] **3.1 Optional-correction copy.** Stage 0 and TS fallback question/summary. Skill pad: `No` is not "Do not ask again." Hard-gate wait copy unchanged. Grouping by `skill_key` already exists. Tests: question/summary strings; UI helper text.

## Epic 4: Operator docs

5. [x] **4.1** AGENTS.md, ACTIVE_WORKFLOW, CHANGELOG: unknown preferred tools do not pause. Skill-only live pauses are promotable. CR-122 status stays in-progress until QA/EM.

## Epic 5: Independent gates

6. [x] **5.1** Security: no new PII paths. QA: stories 1–4 tests. EM: scope vs out-of-scope. One size-1 worker on a skill-only paused slug after code lands.

Note (2026-09-22): focused Python + vitest were run in-session and passed. Independent QA/security agents did not start (usage cap). Live `--once` claimed `businessolver`: Stage 0 PASS 76, no `review_center` pause, then CR-121 `conversion_risk` on junk required tool `Businessolver`. `apply_anyway` was not used.

Independent QA (2026-09-22, stories 1.1–4.1 only; did not run the live worker; did not score 5.1):
- 1.1 PASS (`AC-465` / `AC-466` auto-absent, no `WAITING_FOR_INPUT`; hard-gate still pauses). Coverage gap: no IBM Cloud preferred/OR-list fixture; no WE-mention-wins leftover `NOT_PRESENT` test.
- 1.2 PASS (`AC-466` `NOT_PRESENT` writes no `skill_memory` in Python and TS). `UNSURE_NO_REASK` shares the code path, no dedicated test.
- 2.1 PASS (`AC-469` skill-only promote; hard-gate stays paused). `conversion_risk` and extraction-review regressions still pass.
- 3.1 FAIL (`AC-468` / `UX-001`): Review Center question/summary/helpers are correct, but open `skill_presence` still renders JobDetailPanel "This opportunity is waiting for your review" / "needs an answer before Stage 0 can continue," and Review Center labels `decision_basis` "Why this paused." No test asserts the new question/summary/helper strings.
- 3.1 follow-up (same session): Job Detail wait banner is `hard_gate_review` only. Skill cards label `decision_basis` "Why this was flagged." Copy helpers live in `src/lib/reviewCenter.ts` with tests. Leave 3.1 unchecked until QA re-runs.
- 3.1 PASS on re-test (2026-09-21, AC-468 / UX-001). `npx vitest run src/lib/reviewCenter.test.ts`: 7/7 pass. `JobDetailPanel` wait match is `holdsStage0(item.type)` (`hard_gate_review` only; `skill_presence` is not in that file). `ReviewCenterView` uses `decisionBasisLabel(item.type)`. `SKILL_ANSWER_HELPERS.NOT_PRESENT` is "Same as leaving this unanswered. Not a forever no." Hard-gate Job Detail banner and hard-gate card keep Stage 0 wait language. Did not run the live worker. Did not score 5.1.
- 4.1 PASS (AGENTS.md, ACTIVE_WORKFLOW, CHANGELOG Unreleased).

Independent EM (2026-09-21): **APPROVED**. Not `verified` / not shipped complete.

Reran: `test_stage0_builder_does_not_pause_for_unknown_named_skill`, `test_not_present_does_not_write_skill_memory`, `test_waiting_for_input_review_center_promotes_when_only_skill_cards_open`, `test_waiting_for_input_review_center_stays_paused_while_questions_open` (4/4 OK). `npx vitest run src/lib/reviewCenter.test.ts tests/unit/reviewCenterRepository.test.ts` (16/16). Extra: conversion_risk stays paused / requeue requires `apply_anyway`; real extraction-review requeue still refuses; model-flagged unknown tool creates a card without pausing.

Live `businessolver` already claimed: Stage 0 PASS, fit 76, no `review_center` pause, 0 open hard-gates, `paused_reason=conversion_risk` on junk required tool `Businessolver`. `apply_anyway` absent. Did not `--finalize`, fill cards, or run another worker. `employers` / `ss_c_technologies` remain paused `review_center` until a later claim; they are skill-only / no open hard-gate.

Out of scope held: skip floor 40, AC-464 hook still off, conversion_risk and extraction-review rules unchanged.

Non-blocking residuals (keep `implemented`, not `verified`): leftover `skill_memory.NOT_PRESENT` still caps when WE/catalog do not match (v1: do not mass-delete); Yes then No does not delete `CONFIRMED_USE` (No is a no-op); no dedicated IBM Cloud preferred/OR-list builder fixture (Acme Platform required covers the pause removal); no dedicated WE-mention-wins leftover `NOT_PRESENT` test. CR-121 `conversion_risk` on junk required extraction stays CR-121.
