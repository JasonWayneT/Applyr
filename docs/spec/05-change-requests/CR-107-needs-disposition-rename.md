---
status: implemented
created: 2026-08-30
related: CR-106, CR-096
---

# CR-107 — Rename WAITING_FOR_HUMAN to NEEDS_DISPOSITION

## Problem

`WAITING_FOR_HUMAN` is a Stage 2 workflow state (`scripts/workflow/{runner,policy}.py`,
`scripts/run_submission.py`, `scripts/contracts.py`) meaning: a WARN-severity review finding
has no disposition recorded yet, so this subphase can't complete. `AGENTS.md` already had a rule
(added 2026-08-30, same day) saying an agent hitting this state must resolve it itself, in the
same session, immediately — never leave it for Jason. That rule exists because it was violated:
a real batch left 2 of 15 submissions sitting at `WAITING_FOR_HUMAN`, one with the disposition
already written and just never re-run.

Naming the state after the exact behavior it should *not* trigger is the likely root cause, not
just a symptom. An agent reading a status literally called "WAITING_FOR_HUMAN" has a reasonable,
literal reading available to it — stop, this needs a human — that directly contradicts the
correct behavior (resolve it and continue). Adding a rule that says "ignore what this name
implies" treats the name as fixed and fights it with prose; removing the misleading name removes
the thing the rule has to fight in the first place. This was raised by Jason directly during a
conversation about why a review-queue UI for this state didn't already exist (CR-106's deferred
"Not in scope" item) — his read was that the state shouldn't need one at all, because it's retry
behavior, not human-review behavior, and the name is what makes it look like the latter.

## Decision

Rename the literal state/verdict string `WAITING_FOR_HUMAN` → `NEEDS_DISPOSITION` everywhere it
functions as live code or an enforced test assertion:

- `scripts/workflow/policy.py` — the verdict value itself (`evaluate_truth_findings` and its
  ATS/HM/policy siblings).
- `scripts/workflow/runner.py` — every subphase that reads/writes that verdict onto
  `state["status"]` (4 call sites).
- `scripts/run_submission.py` — the terminal-status tuple and the `--status` human-readable
  message.
- `scripts/contracts.py` — `check_workflow_complete`'s status branch.
- `scripts/stabilization_orchestrator_corpus.py` — a practice-mode smoke script that polls this
  same state.
- `scripts/test_workflow_authority.py` — all fixture/assertion literals (renamed, not deleted;
  same test coverage, same behavior, new label).

**Deliberately not renamed**: `WAITING_FOR_LLM`, a different and correctly-named state — it
means a human genuinely must paste a cloud LLM's output back in (a real manual step in this
pipeline's design), unlike `NEEDS_DISPOSITION`, which the agent can and must resolve on its own.
Confusing these two would be a real regression in the other direction.

**Doc scope, deliberately narrow**: updated `AGENTS.md`'s own rule (the primary thing a future
agent reads as instruction) to use the new name and to state the "this is retry behavior, not
review behavior" framing directly, rather than just swapping the string inside the old framing.
Updated `CR-106`'s one reference (written the same day, directly adjacent). **Not** updated:
`CR-079`/`CR-080`/`CR-081`/`CR-096`, `docs/spec/06-traceability/traceability-matrix.md`,
`docs/spec/02-requirements-registry.md`, or the two same-day session-handoff docs that predate
this one — those are point-in-time records of what was true when written, not living instructions
a future agent executes from, and rewriting history in an "implemented" CR to match a later
rename would misrepresent what CR-079 etc. actually shipped at the time. `CHANGELOG.md` gets a
forward-looking entry for this CR instead of edits to its own past entries.

No on-disk `workflow_state.json` currently holds `WAITING_FOR_HUMAN` (verified via search before
this change), so there is no live-data migration concern — this is a pure code/test/doc rename.

## Requirements

- `FR-276`: The Stage 2 review-finding-needs-a-decision state is named `NEEDS_DISPOSITION` in
  all executable code and tests. `WAITING_FOR_LLM` is unaffected.
- `FR-277`: `AGENTS.md`'s governing rule for this state describes it as retry behavior the agent
  performs immediately, not a stop condition, and no longer uses the old name as its label.

## Acceptance criteria

- [x] `grep -r WAITING_FOR_HUMAN scripts/` returns only the explanatory "renamed from" comment
      in `run_submission.py`, no live logic or test literal.
- [x] `scripts/test_workflow_authority.py` (37 tests) passes unchanged in substance — same
      scenarios, renamed literal.
- [x] Full Python suite (`run_all_tests.py`, 40 files) and full JS/TS suite (`vitest run`, 336
      tests) pass; `tsc --noEmit` clean.
- [x] `AGENTS.md`'s rule section renamed and reframed around "resolve and retry immediately,"
      not "the agent's stop."
- [x] `WAITING_FOR_LLM` untouched — confirmed distinct in every file it appears.

## Not in scope

- A review-queue UI inside Applyr for `NEEDS_DISPOSITION` (still not needed — per this CR's own
  reasoning, if the rename does its job, an agent resolves this inline and it never needs
  surfacing to Jason at all; no notification system was built for it, on purpose — see the
  session's own back-and-forth on this in `docs/spec/08-implementation/SESSION-HANDOFF-2026-08-30-interview-cascade-ai-usage.md`'s
  continuation).
- Retroactively editing historical CR docs (CR-079/080/081/096) or the traceability matrix to
  use the new name.
- Any change to `dispositions.json`'s own disposition values (`RESOLVED_EDIT`,
  `ACCEPTED_AS_CORRECT`, etc.) — those were never part of the naming problem.
