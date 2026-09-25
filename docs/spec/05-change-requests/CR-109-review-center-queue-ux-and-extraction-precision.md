---
status: implemented
created: 2026-09-02
related: CR-108, CR-086, CR-089
---

# CR-109 — Review Center queue UX, extraction precision, and the bad-data learning loop

## Problem

Three reports from Jason on 2026-09-02, all confirmed against the live database:

1. **Two-step answers.** Answering a Review Center card meant selecting an option and then
   clicking a separate "Save answer" button. For a queue whose entire job is clearing many
   small decisions quickly, the extra click is the dominant interaction cost, and the select
   state added nothing: there is nothing to review between selecting and saving a one-tap
   answer.
2. **Junk cards from JD label prose.** The queue contained "Have you used Spirit in your
   work?" (from `Entrepreneurial Spirit: Demonstrate a track record ...`) and "Have you used
   Preferred in your work?" (from `The Workday Ecosystem (Highly Preferred): ...`), plus
   Thinking, Fluency, Prioritization, Methodologies, Competencies, Implementation Consultant,
   Solutions Architect, Talent Acquisition, API, HCM, GTM, LLM, Finance, Legal, and Sales.
   Root causes, all in the CR-108 candidate extractor:
   - The mid-sentence-capitalization regex can only *start* a match mid-run (a line-leading
     capitalized word has no `[a-z,]\s` before it), so in `Entrepreneurial Spirit:` the match
     starts at "Spirit" — the label's first word is silently dropped and the *second* word of
     a trait header becomes the "tool".
   - Nothing rejected a candidate immediately followed by `:` (a bullet label) or `)` (a
     parenthesized qualifier like `(Highly Preferred):`).
   - The hard-block check compared only the whole candidate key, so `workday_ecosystem`,
     `workday_web_services`, and `workday_recruiting` all queued as blocking questions even
     though `workday` itself has been hard-blocked since CR-092's allow/deny split.
   - The stopword list had degree/field vocabulary but no trait, qualifier, role-title, or
     generic-tech-noun vocabulary.
3. **Answer-store privacy needed verification.** Review answers must not travel with the repo
   if Jason hands it to someone else.

## Decision

**Single-tap answers with auto-advance (FR-288).** Every answer button on a Review Center
card now saves immediately and the next card in the queue is shown with a short fade-and-rise
transition (`animate-card-swap`, 240ms — perceptible on purpose; survey-UX research on
auto-advance consistently pairs it with a visible transition and a correction path, and
forbids silently landing the user nowhere after the last card). There is no "Save answer"
button anywhere in the flow. The last card in a queue resolves to a clear "this queue is
clear" state, and Completed holds anything worth revisiting. This matches the pattern Jason
described (select → next card immediately, mistakes fixed from Completed) and the external
consensus for one-question-at-a-time flows (auto-advance is safe for single-tap answers when
correction is possible and the advance is visibly signaled; UX Stack Exchange threads 90676 /
62405 / 52695 and the 2025 Survey Practice auto-advance study all converge on exactly those
two caveats).

Two consequences of removing the select-then-save flow:
- A Yes on a skill-presence card no longer opens an inline details form. That form duplicated
  what the evidence-enrichment card (auto-created on every Yes, living in the Strengthen
  evidence queue) already does, so the details flow moved there entirely rather than being
  deleted.
- Evidence-enrichment cards keep their details form; the answer buttons themselves are the
  submit action (a form needs an explicit action; single-tap answers don't). The explicit
  "Submit for source verification" promotion flow (FR-284) is unchanged.

**Correction from Completed (FR-289).** Completed cards now show the recorded answer
("Your answer: No") and a Change answer button that reopens the same answer pad in place.
The repository already accepted re-answers (the update is keyed on `review_key`, not status),
so this is a UI unlock plus surfacing `answer` through `listReviewItems` → API → client
normalization, not a new write path. Every re-answer appends to `review_answer_history`, so
the correction trail is preserved.

**Extraction precision (FR-286 / BUG-001).** Three mechanical guards in
`scripts/blocked_tools.py` / `scripts/stage0_confirmations.py`:
1. A candidate immediately followed by `:` or `)` is rejected as a JD label/qualifier shape.
2. The stopword list gains trait words (spirit, mindset, thinking, fluency, prioritization,
   methodologies, competencies, aptitude, acumen, ownership...), qualifier words (preferred,
   highly, bonus, ideally), role-title words (solutions, implementation, integration,
   consultant, talent, acquisition), and generic tech nouns/domain acronyms (api, apis, rest,
   json, xml, llm, ai, ml, machine, learning, gtm, hcm, ats, crm, hris).
3. `_contains_blocked_key()` blocks any candidate containing a hard-blocked tool as a token
   run, closing the Workday-compound hole (token-based, so `sap` cannot false-positive inside
   an unrelated word).

Guard 1 has a known, accepted trade-off: a genuinely unknown tool written as a bare label
(`AppDynamics: 2 years required`) will no longer queue. Label shapes produced only junk in
practice, and layer 3 below catches any real loss.

**Bad-data learning loop (FR-287 / DATA-005).** A fourth answer, `BAD_DATA`
("Not a real skill — bad extraction, never ask again"), is now a first-class answer on every
skill card, in the API, in the harness envelope options, and in durable `skill_memory`
(decision `BAD_DATA`, evidence level 0). Because `_prepare_skill_confirmations` skips any
skill with existing memory, a BAD_DATA flag permanently suppresses that candidate — this is
the "learn from it" mechanism: the tail of extraction junk that no heuristic list will ever
fully cover gets flagged once, by the user, in one tap, and never asked again, and the
accumulated BAD_DATA rows are exactly the dataset for future stopword/guard improvements.

Migration `022_add_bad_data_answer.sql` adds `BAD_DATA` to the three CHECK vocabularies
(`skill_memory.decision`, `pending_skill_confirmations.answer`,
`review_answer_history.answer`) via table rebuild — SQLite cannot ALTER a CHECK. The rebuild
is idempotent because `stage0_confirmations._connect()` executes every migration file on
each connection.

**Privacy (DATA-005).** Verified, not changed: answers, skill memory, and answer history live
only in `data/jobagent.sqlite`, already covered by the `*.sqlite*` `.gitignore` wildcard
(confirmed via `git check-ignore` and `git ls-files`). A `.gitignore` comment now names this
explicitly so the wildcard is not "cleaned up" later. No answer data is written to any
tracked file.

## Requirements

- `FR-286`: Named-tool candidate extraction rejects JD label/qualifier shapes, known trait/
  qualifier/role-title/generic-tech vocabulary, and any candidate containing a hard-blocked
  tool as a token run.
- `FR-287`: `BAD_DATA` is a first-class review answer end to end (UI, API, harness, durable
  memory, answer history) and permanently suppresses the flagged candidate.
- `FR-288`: Answering a Review Center card is a single tap that saves immediately and shows
  the next card in the queue with a visible transition; there is no separate save step.
- `FR-289`: Completed cards display their recorded answer and can be re-answered in place;
  every answer change is preserved in `review_answer_history`.
- `DATA-005`: Review answers, skill memory, and answer history exist only in the gitignored
  local SQLite database.

## Acceptance criteria

- [x] `AC-374`: The exact JD lines that produced "Spirit", "Thinking", "Prioritization",
      "Fluency", "Methodologies", "Competencies", and "Preferred" produce zero candidates;
      the Workday JD line produces only `EIB`, `Extend`, `Studio`.
- [x] `AC-375`: A `BAD_DATA` answer completes the item, writes `skill_memory` with decision
      `BAD_DATA` / evidence level 0, creates no evidence-enrichment follow-up, is recorded in
      `review_answer_history`, and prevents the candidate from being re-queued.
- [x] `AC-376`: `BAD_DATA` is rejected on hard-gate reviews (vocabulary stays per-type).
- [x] `AC-377`: A completed item's recorded answer is returned by `listReviewItems`, served
      by the API, and survives client normalization; unknown answer strings normalize away.
- [x] `AC-378`: Re-answering a completed item updates durable memory and appends a second
      history row (correction trail, no rewrite).
- [x] `npm test` (full Python + Vitest suites) and `tsc --noEmit` pass.
- [x] `git check-ignore data/jobagent.sqlite` matches `*.sqlite*`; no answer-bearing file is
      tracked.

## Not in scope

- Cleaning up the already-created junk rows in Jason's live database. That is deliberately
  left to the new BAD_DATA button: dismissing each one in one tap is the same effort as a
  cleanup script, and each dismissal teaches the durable memory (a script would just delete
  rows without recording the signal).
- ML/NER-based tool extraction. Gazetteer-plus-capitalization with a user-driven bad-data
  loop is still the right weight for this corpus; the CR-108 comment in `blocked_tools.py`
  already made that call and nothing here changes it.
- Undo toasts or swipe gestures. Correction lives in Completed, per Jason's own framing.
