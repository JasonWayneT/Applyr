---
status: next_session_brief
created: 2026-09-13
from: Cursor (Grok 4.6)
candidate: cr112-integrated-validation-candidate
prior_closed_head: b0e732e
code_baseline_story_81: 0aaab87
result: HANDOFF_TO_NEW_SESSION
do_not: push, merge to main, touch live submissions, write production SQLite, call paid APIs
---

# Next session — CR-112 Story 8.1 QA, identity, quality pick, JD 2 readiness

This file is the incoming brief. Prior reconstruction and Camunda
follow-up: `SESSION-HANDOFF-2026-09-12-cr112-cursor-camunda-followup.md`.
Do not redo that recon. Do not mark CR-112 complete. Do not call the
candidate daily-use ready.

Worktree:
`.claude/worktrees/cr112-integrated-validation-candidate`

Branch: `cr112-integrated-validation-candidate`

Start from **clean HEAD of this branch after this docs commit**. The
last *work* commit before this brief is `b0e732e`. Story 8.1 code is
`0aaab87`. Do not reset onto `b0e732e` in a way that drops this file.

Leave untouched:

- Applyr repo root `cr112-selection-closed-world-design` @ `b5616c8`
  (dirty)
- `.claude/worktrees/cr112-story71-72` @ `7bf6829`

Preserve unrelated dirty work. Keep commits local and story-isolated.

Cost: no paid APIs. No silent free→paid fallback. Unknown cost is not
zero. Stage 1 stays author-paste unless an explicitly free provider
has a hard zero-dollar declaration. One investigator and one
independent reviewer at a time. Do not spawn agents per JD. Do not
load full `workExperience.md`, `agent_context_pack.md`, or the full
claims catalog into agents that do not need them.

---

## Already true (do not re-investigate from scratch)

- `470abdf` Stage 0 extraction fallback: ACCEPT (qualification pause;
  non-qualification text does not; `correct_judgment` without raw SQL
  delete).
- `089efec` ATS-term-contract eligibility: ACCEPT. Remaining gap:
  `evidence_map` can still attach empty `allowed_claims` (Camunda
  `ACC-185-CUSTOMER-DISCOVERY`).
- Camunda `PRACTICE_COMPLETE` at Resume 68 was a **defect plus naming
  fact**. Canonical score was `draft_manifest.json` 68/69, not the
  untouched first draft 64/57. Preserve that practice folder as
  regression evidence. Do not rerun Camunda solely to replace the
  historical artifact. Do not inflate scores to clear the floor.
- Story 8.1 implementation is in `0aaab87` (`FR-318` / `AC-415`).
  Design: `CR-112-completion-contract-quality-floor-defect.md`.
  First QA [Review](b782f4e4-bf82-4dec-a31e-e82c43d04f30) was
  **ACCEPT WITH CHANGES**. Required negative controls were added in
  that same commit after the verdict. Checkbox stays `[ ]` until an
  **unqualified** follow-up QA PASS.
- Floors stay Resume 70 / Cover Letter 65. They are gates, not targets.
  Stage 0 fit bands are a different contract (Skip below 40, Tier 1 at
  65+).
- Practice identity is **design only**:
  `CR-112-practice-identity-portability-defect.md` (`SEC-006`).
- Python-only suite at close of prior session: 61 passed, 0 failed.
  Focused floor tests: 140 OK. `test_jd_term_extractor` 9 OK but not
  yet on `PYTHON_TEST_SCRIPTS`.

---

## Step 1: Close Story 8.1 properly

Run a **fresh, independent** follow-up QA review of commit `0aaab87`
**after** its added negative controls. The implementer must not
self-mark PASS.

The reviewer must verify through the **canonical workflow**, using a
faithful temporary workflow fixture, not helper-only assertions.
Include controls proving the test reaches the intended floor
invariant.

Must hold:

- Resume below 70 blocks completion.
- Cover letter below 65 blocks completion.
- Exactly 70/65 passes the floor gate.
- Missing, malformed, nonnumeric, stale, and contradictory score data
  fail closed.
- Practice and production paths enforce the **same** floors.
- `--force` cannot bypass the floors.
- An old disposition for the score-presence warning
  (`mech.rubric_score_required`) cannot clear the new floor BLOCK
  (`mech.rubric_floor.resume` / `mech.rubric_floor.cover_letter`).
- Stage 3 cannot mint `COMPLETE`, `COMPLETE_WITH_OVERRIDE`, or
  `PRACTICE_COMPLETE` while the current canonical documents are below
  floor.
- Above-floor scores alone do not imply send-readiness when another
  Stage 2 block remains.
- `check_workflow_complete` retains its intended distinction between
  practice and production.

If QA finds a defect: smallest correction only, rerun focused and
relevant full suites, then **one** final independent QA pass. Mark
Story 8.1 complete **only** after an unqualified QA PASS is recorded
durably in the epics tracker and this handoff lineage.

User-facing status language (do not rename states unless misleading
output actually requires a bounded change):

- `PRACTICE_COMPLETE` means the practice workflow completed.
- It does **not** mean apply-ready or send-ready.

No exception path, no HAR-as-Jason-review, no lowering 70/65.

## Step 2: Implement practice identity portability

**Only after** Story 8.1 has an unqualified QA PASS.

Take `docs/spec/08-implementation/CR-112-practice-identity-portability-defect.md`
through **one design review, one bounded implementation, and one QA
review**. Do not couple identity to rubric-floor enforcement unless
review proves the same ownership boundary requires it.

Required behavior:

- Canonical real identity source remains gitignored
  `workExperience.md` Section 1.0 through the existing identity/header
  parser (`apply_resume_header.py`).
- SQLite `profiles.identity` is a cache, not the source of truth.
- A clean worktree can use local gitignored identity material without
  copying production SQLite.
- Missing or malformed real identity fails **before authoring** with
  an actionable status.
- Never silently emit John Doe or other plausible placeholder
  identity.
- Synthetic identity only in an explicit synthetic/evaluation mode,
  unmistakably labeled.
- No PII in tracked fixtures, commits, reports, logs, receipts,
  prompts intended for sharing, or test snapshots.
- Tests must use synthetic identity.
- Preserve zero-cost and worktree-isolation.

Security review if touching DB/PII. Isolated commit for Story 8.2.

## Step 3: Prepare the next quality decision

Do **not** implement a first-draft quality change yet.

Produce a compact comparison of two candidate stories:

1. Add the `LW-009-PAIR` cross-document repetition instruction to the
   lean authoring digest (`scripts/generate_authoring_rule_digest.py`).
2. Correct evidence ranking where `ACC-101-SAVINGS` beat more directly
   relevant distributed-systems evidence (RabbitMQ/Kafka) on Camunda.

For each, report:

- The exact Camunda defect it would have prevented.
- Cause class: selection, ranking, packet construction, instruction,
  generation, or review.
- Cross-submission frequency in `data/authoring_defect_ledger.json`.
- Expected improvement to first-draft quality.
- False-positive and overfitting risk.
- Token impact.
- Smallest faithful regression test.
- Whether it generalizes beyond Camunda.

For ranking: a larger metric does not automatically win. Compare with
JD relevance, evidence strength, attribution safety, distinctiveness,
domain-truth risk, page capacity, and cross-document usefulness.
Pearl and SupplyHouse `ACC-101-SAVINGS` remain **negative controls**.
They must not become automatic replacements.

Recommend **exactly one** next story. Prefer broader evidence and
lower overfitting risk, not merely the easiest implementation.

Do not rescore or overwrite the untouched Camunda first draft
(Resume 64 / Cover Letter 57, `FIRST_DRAFT_WEAK`). Prefer
`%TEMP%\camunda_baseline_*.md` hashes `466a7150…` / `970fa377…` over
on-disk `stage1_first_draft/`.

## Step 4: Decide readiness for JD 2

Do **not** begin JD 2 until:

- Story 8.1 has an unqualified QA PASS.
- Practice identity works in a clean isolated worktree.
- All relevant tests pass.
- No paid provider is configured or called.
- The candidate remains clean and isolated.

Do not rerun Camunda solely to replace its historical
`PRACTICE_COMPLETE` artifact. Preserve it as regression evidence.
Recommend whether a clean Camunda rerun adds unique evidence or
whether JD 2 is the stronger next product proof.

## Deliverable (update this lineage when the new session closes)

Update a durable handoff under `docs/spec/08-implementation/` with:

- QA verdict and review identifier for Story 8.1
- any corrective commit
- identity design, implementation, tests, and QA verdict
- exact local commits and ancestry
- the two-story quality comparison and one recommendation
- no-cost / model-call / spawn evidence
- whether the candidate is ready for JD 2
- remaining blockers to daily-use readiness

Keep all commits local and story-isolated. CR-112 remains open.
The candidate must not be called daily-use ready.
