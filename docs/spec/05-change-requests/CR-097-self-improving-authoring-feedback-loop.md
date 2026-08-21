# CR-097 — Self-Improving Stage 1 Authoring Feedback Loop (Stage 2 findings → Stage 1 instructions)

**Status:** Decisions locked (2026-08-21) — ready for tech-lead design. Jason explicitly delegated
Q1-Q4 to best-judgment/best-practice call rather than requiring his personal sign-off on each
("this doesn't need my sign off we need to use best judgment based on best practices") — see
"Decisions" below for what was chosen and why, in place of the original Open Questions.
**Date:** 2026-08-21
**Author:** Product Manager pass (Claude Code)
**Related:** `CR-096-stage1-3-audit-remediation.md` (names this CR as "Piece A" of its roadmap, deferred
from that session), `CR-093-evidence-scale-fit-engine.md` (`scripts/fit_rubric_examples.py` /
`data/fit_rubric_golden_set.json` — closest live precedent, unmodified by this CR), `CR-074-token-conscious-authoring-packet.md`
(owns `data/authoring_rule_digest.md` and its 10,000/8,000-char budget, which this CR must live
inside, not raise).

**Registry note:** no `FR-*`/`AC-*` registry IDs are claimed in this document. Following the
established project precedent for a proposed, not-yet-built CR with open product decisions still
pending (CR-070; CR-075's first round before Jason's decisions landed), IDs get reserved once the
Open Questions below are answered and the tech-lead pass can design against a fixed target. The
Requirements table below states informal `SR-*` ("self-improvement requirement") IDs, scoped to this
CR document only, not the global registry.

---

## Overview

Stage 2 review (Truth, ATS, HM, Mech, Policy) catches real authoring mistakes on every submission
today, but nothing durable happens to that information once a submission is done. Each submission's
findings live only in that submission's own `reviews/{truth,ats,hm,mech}_findings.json` and
`reviews/dispositions.json` — there is no cross-submission aggregation, and the only mechanism that
has ever fed a Stage 2 finding back into Stage 1's authoring instructions
(`data/authoring_rule_digest.md`) was a single manual edit (Fix 6, `CR-096`), made because one person
happened to notice a repeated pattern during an ad hoc audit. This CR scopes a standing mechanism so
that real, confirmed Stage 2 corrections durably reduce how often the same mistake needs correcting
again — without violating the digest's already near-exhausted token budget, and without touching the
Stage 2 review chain itself.

## Motivation

- **Static first-draft quality.** Nothing in the current pipeline makes Stage 1's authoring behavior
  measurably better over calendar time as more real submissions accumulate real corrections. The one
  time this happened (Fix 6) required a human to manually re-read accumulated findings during an
  unrelated audit pass — not a standing process.
- **Token budget already exhausted.** `data/authoring_rule_digest.md` sits at 7,989 of a hard 10,000-
  char ceiling (8,000-char soft target) as of Fix 6. Any naive "append more rules" version of this
  request fails almost immediately; the mechanism must be retrieval-scoped or rotation-aware from
  the start, per the token-budget and prompt-length-degradation research cited in the companion
  `pipeline-log.md` entry (2026-08-21, Product Manager section).
- **A close precedent already exists, but for a narrower problem.** `scripts/fit_rubric_examples.py`
  (CR-093) already does retrieval-augmented few-shot for one Stage 0 LLM classification call, fed by
  a human-curated golden set. Whether that shape generalizes to Stage 1's different failure class
  (document-level instruction-following, not line-item classification) is an open design question,
  not an assumed yes.

## Scope boundary — what does NOT change

- **The Truth → ATS → HM → Mech → Policy Stage 2 review chain.** Per CR-096's own Anti-churn note:
  "the core... safety-net architecture is not broken and should not be touched." Reviewers stay
  findings-only; they never edit documents. This CR only changes what Stage 1 sees before drafting.
- **`scripts/fit_rubric_examples.py` / `data/fit_rubric_golden_set.json` / the Stage 0 evidence-scale
  engine (CR-093).** Read as precedent, not modified.
- **`data/authoring_rule_digest.md`'s coded 10,000-char hard limit / 8,000-char soft target.** Stay
  exactly as they are; this mechanism must design inside them, never raise them.
- **Each submission folder's own `reviews/*_findings.json` / `reviews/dispositions.json`.** Stay the
  per-folder audit trail they are today; this CR adds a separate, cross-folder record on top, it does
  not restructure the per-folder files.

---

## Requirements

| ID | Title | Description | Status |
|----|-------|-------------|--------|
| SR-01 | Cross-submission durable record | A durable record of confirmed authoring corrections must exist, separate from any single submission's `reviews/` files. | Locked — schema shape per SR-08 |
| SR-02 | Human curation gate | Entry into the record requires an explicit human confirmation that a finding is a real, generalizable authoring mistake — never automatic promotion of every `RESOLVED_EDIT` disposition. Mirrors `fit_rubric_golden_set.json`'s `few_shot_eligible` flag. | Locked |
| SR-03 | Retrieval-scoped injection, never static accretion | Whatever surface receives new entries must be scoped per authoring session (e.g. top-k retrieval into the packet), never a growing block appended to every Stage 1 prompt regardless of relevance. | Locked |
| SR-04 | Digest budget preserved | `authoring_rule_digest.md`'s existing hard/soft char limits are unchanged. Digest text is reserved for binary structural rules only (Decision 3) — the retrieval bank absorbs all growth from contextual examples, so digest addition-only growth is avoided by construction, not by a pruning rule. | Locked |
| SR-05 | Measurable success signal | Before build: define the count/category of Stage 2 findings resolving as `RESOLVED_EDIT`, for the 3 SR-06 target categories, tracked across the next 10 real submissions post-launch (chosen to match a realistic near-term batch size, not an arbitrary round number — small enough to get a read within weeks, large enough that 1-2 submissions of noise don't decide the result). A decrease over that window is the operational definition of "the checker informs the first draft." | Locked |
| SR-06 | First slice scoped to one proven-repeat category | Initial build targets exactly the three failure types Fix 6 already confirmed as repeat mistakes (wrong-job content bleed, gap-confession language, forbidden punctuation) — not a general all-categories ingestion pipeline. | Locked |
| SR-07 | Self-Repair Protocol stays the human-in-the-loop trigger (interim) | `.claude/skills/generate-submission/SKILL.md`'s existing Self-Repair Protocol is not replaced. This mechanism reduces reliance on a human happening to notice a repeat unprompted; it does not remove the human judgment step. | Locked |
| SR-08 | Storage mechanism | (c) — split by failure type: structural/binary rules stay in the digest; contextual pattern examples move to a new per-job retrieval bank, architecturally modeled on `fit_rubric_golden_set.json` + `fit_rubric_examples.py`'s retrieval shape (own file/schema, own token-overlap ranking — not a shared bank with Stage 0's, since the two feed different prompts with different failure vocabularies). | Locked — see Decision 1 |
| SR-09 | Update trigger | (b) — automatic-on-repeat: the same failure category surfacing on 2+ separate submissions opens a mandatory human review of whether to promote it into the bank. | Locked — see Decision 2 |
| SR-10 | Mechanism shape | The retrieval bank targets "rule exists but isn't reliably applied to case X" specifically; "rule doesn't exist yet" stays a direct digest hand-edit, unchanged from how Fix 6 already works. Not a single either/or answer — two failure shapes, two already-distinct tools. | Locked — see Decision 3 |
| SR-11 | Promotion bar | 2+ independent submissions showing the same failure category, matching Decision 2's trigger threshold by construction (the 2nd occurrence is what opens the review that decides promotion). | Locked — see Decision 4 |

## Decisions (locked 2026-08-21, delegated best-judgment call — not guessed, reasoned from the
research and precedent already gathered)

1. **Storage (SR-01/SR-08): (c) — split by failure type.** Structural/binary rules that must always
   fire regardless of context (e.g. "exactly 3 sentences," "no em dashes") stay static in
   `authoring_rule_digest.md`. Contextual pattern examples (e.g. "wrong-job content bleed") move to a
   new per-job retrieval bank, injected alongside the authoring packet the same way WE excerpts
   already are. Reasoning: this is the one option that (a) matches the "200-token core + task-specific
   overlays beats one long static prompt" research directly, (b) reuses an architecture pattern already
   proven live in this exact codebase (`fit_rubric_examples.py`) rather than inventing a new one, and
   (c) is the only option that doesn't force every future entry into the digest's already-near-full
   token budget (SR-04) regardless of whether it's the kind of rule that needs to.
2. **Trigger (SR-05/SR-09): (b) — automatic-on-repeat, mandatory human review.** The same failure
   category surfacing on 2+ separate submissions automatically opens a mandatory review (a human or
   agent judgment call on promotion), rather than firing on a fixed cadence or staying fully ad hoc.
   Reasoning: this is a direct, un-invented extension of `generate-submission/SKILL.md`'s own already-
   standing Self-Repair Protocol principle ("fix the mechanism, not the instance... once it recurs") —
   best practice here is consistency with an existing house rule, not a new one. A fixed-cadence review
   wastes cycles checking nothing changed; fully ad hoc is the status quo this CR exists to fix.
3. **Mechanism shape (SR-10): retrieval-bank examples are the mechanism's real target; the digest
   stays the lever for "the rule doesn't exist yet."** These are not competing answers to the same
   question — they are two different failure shapes needing two different, already-distinct tools.
   "Rule doesn't exist" is cheaply and immediately fixable by hand-editing the digest the moment it's
   noticed (exactly what Fix 6 did, and what SR-01's digest half stays for). "Rule exists but isn't
   reliably applied to a case shaped like X" has no existing lever at all today — that is the actual
   gap this CR fixes, and it is precisely the problem a concrete corrected before/after example solves
   better than another line of abstract instruction (this is GEPA's and few-shot research's whole
   premise: showing a corrected instance generalizes better than restating the rule again in different
   words). The retrieval bank is scoped to this failure shape specifically, not a general catch-all.
4. **Promotion bar (SR-11/SR-05): 2+ independent submissions, same failure category, before an entry
   is eligible for the bank.** A single occurrence can be an idiosyncrasy of one JD, not a real,
   generalizable pattern — promoting on one instance risks the bank overfitting the way a 1-shot
   example would. 2+ matches `fit_rubric_golden_set.json`'s own implicit bar (its entries are confirmed,
   curated cases, not first-draft flags) and ties directly to Decision 2's repeat-triggered review: the
   2nd occurrence is what opens the review in the first place, so the promotion bar and the trigger
   threshold are the same number by construction, not two numbers to keep in sync.

## Out of Scope

- Redesigning, weakening, or bypassing the Truth → ATS → HM → Mech → Policy Stage 2 review chain.
- Embedding-based retrieval (nomic-embed-text) — `fit_rubric_examples.py`'s own stated threshold
  ("revisit past ~10-15 entries per category") applies; this mechanism's bank starts near zero.
- Automatic, unreviewed ingestion of every Stage 2 finding or every `RESOLVED_EDIT` disposition.
- Using the new cross-submission record as a general analytics/reporting surface.
- Retroactively re-authoring or re-scoring any already-completed submission to backfill data for this
  mechanism (CR-096's "Piece B" is a separate, already-flagged decision, not a prerequisite here).
- Any change to `scripts/fit_rubric_examples.py`, `data/fit_rubric_golden_set.json`, or the Stage 0
  evidence-scale engine (CR-093).
- Raising or removing `authoring_rule_digest.md`'s 10,000-char hard limit / 8,000-char soft target.
- The actual retrieval algorithm, storage file schema, or trigger implementation — tech-lead pass,
  next, per CR-096's own roadmap sequencing.

## Traceability Mapping

| File | Action |
|------|--------|
| `data/authoring_rule_digest.md` / `scripts/generate_authoring_rule_digest.py` | No change in this CR. Constraint only: hard/soft char limits stay fixed inputs to the tech-lead design (SR-04). |
| `scripts/fit_rubric_examples.py` / `data/fit_rubric_golden_set.json` | Read as precedent only. No change (Scope boundary, Out of Scope). |
| `data/submissions/{company}/reviews/*_findings.json`, `reviews/dispositions.json` | No structural change. Remain the per-folder source material a future cross-folder record (SR-01, blocked on Q1) would read from. |
| `.claude/skills/generate-submission/SKILL.md` (Self-Repair Protocol) | No change in this CR. Referenced as the existing human-in-the-loop principle SR-07/SR-09 extend, not replace. |
| *(new file(s), name TBD — blocked on Q1/SR-08)* | Not created in this CR. Tech-lead pass designs the actual storage artifact once Q1 is answered. |

---

## Sequencing (per CR-096's roadmap, unchanged here)

1. Read `scripts/fit_rubric_examples.py` — **done**, informed this CR's scope boundary and Open
   Questions.
2. Product-manager pass — **this document.**
3. Tech-lead design pass — **unblocked, next.** Designs the actual aggregation point, trigger
   implementation, and retrieval-bank mechanics against the decisions above.
4. Implementation once the tech-lead pass is locked, per this repo's own SDD process.
