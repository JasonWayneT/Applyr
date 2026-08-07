# SESSION HANDOFF — 2026-08-04 — Wire the years-experience gate at ingest

Small, low-risk, no-LLM addition. Independent of the Sync/pending_review work — can land anytime.

## What's missing

`passesSeniorityGate()` (`shared/domain/gates.ts:275`) is fully built — checks a job's required years
against `config.maxExperienceYears` via `parseMaxYearsRequired()` — but is **never called**. Confirmed by
direct trace: `server/services/scoutOrchestrator.ts` calls `passesTitleBlocklist`, `passesIndustryGate`,
`passesGeographicGate` at ingest. Not the seniority gate. Today, a job requiring far more years than
Jason has sails straight through to `data/pending_review/` — the only automated gates are
title/industry/geography, nothing on years.

## The one rule that matters more than the wiring itself

**Stage 0 (the live Claude Code review) is the source of truth for fit and responsibility judgment —
not this gate, and not before it.** (Jason-supplied, 2026-08-04.) This gate's only job is catching
requirements so far outside Jason's range that they're not worth a human look at all — it must never
attempt the nuanced judgment Stage 0 already does (compound-requirement splitting, transferable-skill
bridging, domain anchoring, "apply if you meet 50%" hedge-language handling, etc.). If a job's years
requirement is ambiguous, borderline, or unparseable, **this gate must let it through**, not guess.
Getting this wrong doesn't just add noise — it silently removes a job from Jason ever seeing it, which is
worse than a noisy queue.

## A real, specific risk to check before flipping this on — not hypothetical

This exact failure mode already happened once in this codebase. CR-056 (2026-07-06) found
`experience_range.max` set one year too low, silently rejecting valid "Senior Product Manager" postings
requiring 8 years, for who knows how long before anyone noticed. Two things in the current code make the
same mistake easy to repeat:

1. **`passesSeniorityGate`'s comparison has zero buffer**: `required > config.maxExperienceYears`, strict,
   no cushion. `experience_range.max` is currently `8` (`data/candidate_preferences.json`). A JD stating
   "9+ years" gets rejected outright — a one-year gap is enough.
2. **`parseMaxYearsRequired()`'s range pattern takes the MAX of any stated range.** A JD saying "5-10
   years" extracts `10`, not `5` — even though the real floor a JD like that usually means is closer to 5,
   with 10 read as an aspirational/senior stretch a JD-relevance-first hiring manager wouldn't actually
   hold a candidate to. That's exactly the kind of case Stage 0 would correctly judge as a fine fit and
   this gate would silently reject before it ever got there.

## What to do

1. Confirm `GateConfig.maxExperienceYears` actually reads from `experience_range.max` (currently `8`) —
   don't assume the mapping, verify it directly.
2. Wire the years-check into `scoutOrchestrator.ts` alongside the existing gate calls. Don't wire in the
   whole `passesSeniorityGate()` function as-is — it also re-checks the title blocklist internally, which
   `scoutOrchestrator.ts` already does separately via its own `passesTitleBlocklist`. Extract just the
   years-check portion, or accept the harmless duplication if extracting is more disruptive than it's
   worth — your call, just don't silently double-reject on two different title-blocklist implementations
   that could theoretically disagree.
3. **Add a real buffer to the comparison** before this goes live — e.g. only reject when
   `required > maxExperienceYears + 2` (or whatever margin feels right), not a bare `>`. Given the CR-056
   history, a zero-buffer cutoff is not a safe default here.
4. **Test empirically against real JD text before deploying** — run the updated logic against every
   `Original_JD.txt` currently in `data/pending_review/` and `data/archive/submissions/*` (a large,
   real, already-known corpus). Report which ones it would reject, and manually sanity-check a sample:
   are these genuinely too senior, or would Stage 0 likely have found a fit? This is the same "verify with
   real data before trusting a heuristic" discipline the rest of this project already runs on — don't skip
   it because the change feels small.

## Explicitly out of scope

- No changes to Stage 0's own logic in `generate-submission/SKILL.md` — this gate operates strictly
  before Stage 0 ever sees anything, and must stay coarse relative to it, not converge toward replicating
  it.
- No changes to the CSV-bulk-upload rewiring discussed separately — different task, can land independently
  in either order.

## Verification before calling this done

1. Confirm the buffer is actually in the comparison, not just discussed.
2. Report the empirical test results against the real JD corpus (Step 4 above) — what got rejected, and
   whether a manual spot-check of those rejections looks correct.
3. Confirm `passesTitleBlocklist`, `passesIndustryGate`, `passesGeographicGate`, and the new years-check
   all still run cleanly against a live Sync (or the existing test suite, whichever is faster) with zero
   regressions to jobs that were passing before this change.
