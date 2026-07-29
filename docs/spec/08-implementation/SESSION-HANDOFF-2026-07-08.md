---
date: 2026-07-08
purpose: Self-contained handoff for the next session. Read this before opening any other doc.
---

# Session Handoff — 2026-07-08 → next session

## What happened today

Investigated [CR-059-local-llm-tuning-loop.md](CR-059-local-llm-tuning-loop.md) starting at Round 1,
Story 1.1 (resolve which code path actually produces bullet content by default). The answer closed the
whole CR:

**The default drafting pipeline calls zero local LLMs.** Traced every stage under the actual default
config (`JD_PROFILE_MODE=deterministic`, `DRAFT_MODE=compose`, `COVER_ENGINE` unset → `v1`) — JD
profiling, claim selection, bullet generation, resume summary, cover letter compilation — and every one
of them is deterministic string assembly / template logic, not LLM generation. The only LLM call sites
in the drafting code (`bullet_generation.py`'s `legacy_llm` mode, `cover_letter_slots.py`'s v2 cover
engine, `jd_tailoring.build_jd_profile`'s LLM branch) sit behind non-default env vars nothing sets in
production — dead code, not live behavior. This traces back to a deliberate 2026-05-21 decision
([CR-017](../05-change-requests/CR-017-local-claim-composition-engine.md)): move off free-form LLM
rewrites specifically to kill fabrication risk. CR-058's fix list (7 bugs, all regex/logic, zero prompt
changes) is consistent with this — there was no prompt to fix.

**Outcome:** CR-059 closed as moot (status → `closed_moot`) rather than redirected to the dormant LLM
paths or to fit-scoring/research LLM calls — see the doc's own top section for why both redirects were
rejected. `CLAUDE.md`/`AGENTS.md` re-synced to drop it from Active Engineering Work and note the closure.
Recommended (not opened): if the underlying goal — higher rubric score / less generic-reading output —
is still worth chasing, that's a **deterministic template variety** problem in `claim_composer.py` /
`summary_builder.py`, a different and lower-risk CR than the one that was closed.

**Files touched this session (only these three):**
- `docs/spec/08-implementation/CR-059-local-llm-tuning-loop.md` — closure section added, status flipped
- `CLAUDE.md`, `AGENTS.md` — Active Engineering Work section updated, re-verified byte-identical

No code was changed. No commits were made.

## Current repo state — read before running any git command

`git status` shows ~141 modified/added/deleted files and several untracked scripts. **Almost none of
this is from today's session** — it predates this session and was already present at the start (scout
connector deletions, `scripts/_*.py` one-off diagnostic scripts, `server/services/ollamaLifecycle.ts`,
etc.). This looks like in-flight work from other sessions. Do not `git stash`/`reset --hard`/`checkout --`
across the working tree without first isolating what's actually related to whatever you're about to do —
confirm with Jason if it's unclear whose work it is.

## Where to start next session

The one active engineering thread is
[CR-053-fit-rubric-overhaul-epics.md](CR-053-fit-rubric-overhaul-epics.md) (fit-rubric rebuild +
pipeline-failure-transparency + collection-gate accuracy, three CRs in one doc). **Its own "Rollout
note" priority ranking at the bottom is now stale** — re-checked today's session:

- ✅ **(1) CR-054 Epic 1** (silent failure reporting) — all 5 stories complete
- ✅ **(2) CR-055 Epic 1** (years-gate regex) — all 3 stories complete
- ⚠️ **(3) CR-055 Epic 2** (title blocklist contextual matching) — complete except Story 2.3
  (monitoring task: "pull a larger title sample," not blocked, just ongoing observation)
- ✅ **(4) CR-053 Epic 1** (location gate) and **Epic 2** (scoring architecture) — both fully complete
- ✅ CR-053 Epic 3 (domain fit penalty) — fully complete

**Genuinely open, non-blocked candidates for next work** (not ranked against each other — CR-053's own
doc says wait for Epic 4 calibration data to re-rank rather than guess, and that calibration is itself
blocked, see below):

1. **CR-053 Epic 5, Story 5.3** — CHANGELOG.md + PRODUCT_CAPABILITIES.md closeout entries for CR-053/
   054/055. Quick, doc-only, nothing blocking it.
2. **CR-054 Epic 4, Story 4.1** — instrument lint-rejection frequency (no JSONL accumulator exists yet).
   Real, unstarted dev work.
3. **CR-054 Epic 5, Stories 5.2–5.3** — root-cause + wire `clusterDedup` (exists, has tests, but isn't
   imported by scout/sync routes) into the live ingest path. Quantified value: 15% of confirmed
   self-rejects in the calibration data were unwired duplicates.
4. **CR-055 Epic 3, Story 3.1** — sample a handful of "Stale" rejects (17% of June rejects, second-
   largest bucket) and manually check whether the listing was actually still open. Investigation task,
   not blocked.

**Blocked / needs Jason, don't start cold:**
- CR-053 Epic 4, Stories 4.2–4.3 (calibration harness disagreement report + full test matrix) — blocked
  on JD-text scrape coverage improving; most historical self-rejects lack `jd_text` in the DB.
- CR-053 Epic 5, Story 5.1 (re-run the 5/6 CSV batch sanity check) — explicitly gated on Epics 1–4 being
  done; Epic 4 isn't.
- CR-053 Epic 3, Story 3.3 / CR-054 Epic 3, Story 3.3 (bulk blocklist backfill) — needs Jason's review,
  not an auto-run.
- CR-055 Epic 3, Story 3.2 (freshness window value) — explicitly a judgment call for Jason once 3.1 has
  data, not something to infer alone.

Open with `CR-053-fit-rubric-overhaul-epics.md` itself for full context on any of the above before
touching code — it has file:line evidence and regression-test names for each story.
