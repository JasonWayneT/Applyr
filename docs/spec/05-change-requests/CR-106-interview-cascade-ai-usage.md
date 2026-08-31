---
status: implemented
created: 2026-08-30
related: CR-105, CR-072, CR-015
---

# CR-106 — Interview Auto-Status, Provider Cascade Notifications, AI Usage Task Table

Successor to CR-105. That CR's "Not in scope" deferred three items: interview auto-status-write,
free-tier cascade + usage notifications, and migrating the remaining hardcoded-provider call
sites onto `taskProviderOverrides`. This CR lands the first two fully, and the third honestly:
two of three remaining sites wired, one left alone on purpose, plus two documented scope cuts.

Full session context: `docs/spec/08-implementation/SESSION-HANDOFF-2026-08-30-interview-cascade-ai-usage.md`.

## Problem

1. **Interview invites were detected but not acted on.** CR-105 added a real `interview` category
   and a `gmail_sync_interview` notification, then stopped: advancing to Recruiter Screen / Core
   Interviews requires `interview_date`, and nothing extracted a date/time from the email. Jason
   still had to open the job and type the time himself after being told an invite arrived.

2. **Free-tier exhaustion was silent.** Groq (and Claude/Perplexity) already made a cascade
   decision when rate-limited, but the user-visible result was a stderr print. A tripped daily-cap
   breaker or a 429 that cascaded to the next provider never showed up in Notifications, so a
   provider quietly falling over looked like "the task just failed."

3. **The AI Usage card only listed two (later three) tasks.** CR-105 scoped `taskProviderOverrides`
   honestly to Stage 0 extraction and email classification. Other real call sites still had
   hardcoded providers (WE scoring summary pinned to Gemini, AI rewrite riding `primaryProvider`
   with no override at all, company research pinned to Gemini for live search). A Settings card
   titled "Where AI actually runs" that omitted real tasks was the next incomplete shape.

## Decision

**Interview auto-status-write**: extract date/time from the interview email (regex first for the
shapes real invites use, Groq LLM fallback, Gemini strictly opt-in via
`taskProviderOverrides.interview_date_extraction` — same privacy reasoning as email
classification). Only when a date/time was actually extracted AND
`deriveStatusForInterviewDateChange` says the current status is eligible, auto-write via
`applyJobStatusUpdate`. No confirm-first UI step: matches the existing rejection auto-close
precedent. Dry-run previews the intended action (extraction has no side effects).

A real parse bug found in testing, not guessed: `Date.parse` rejects `"...2026 - 12:00 PM"` and
`"...2026 at 12:00 PM"` outright. Fixed by a normalize-and-retry step that strips the `-`/`at`/`@`
connector immediately before the time.

**Cascade notifications**: when any provider actually cascades (or a self-counted daily cap
trips), write a WARN `activity_log` row with `meta.event = 'llm_provider_cascade'`. Python
(`_log_provider_notification` in `scripts/utils.py`) and Node (`logActivity` in
`groqClient.ts` / `geminiClient.ts`) write the same table. New `GET /api/llm-usage/notifications`
feeds NotificationPanel. Daily-cap trips are deduped per provider+reason over 24h; per-call
cascades are not. Claude and Perplexity, which previously did a blind exponential-backoff sleep
loop on 429, now read `retry-after` and cascade immediately past a 30s threshold, matching Groq.
Gemini notifies once its own retry loop is exhausted (its REST error body has no parseable delay).

**AI Usage table**:
- `we_scoring_summary` (`generate_experience_summary.py`): was hardcoded
  `provider_override='gemini'`. Now `resolve_task_providers('we_scoring_summary', ['gemini'])` so
  an override can promote a different first-choice without changing the Gemini default. Must
  **not** use `resolve_default_task_providers` — that helper would silently switch the default to
  whatever `primaryProvider` is.
- `ai_rewrite` (`ai_rewrite.py`): had no override. Now
  `resolve_default_task_providers('ai_rewrite')`, which is the right helper here (no prior
  explicit default to preserve). Behavior unchanged when unset.
- Settings rows for both. Unlike the email/interview rows (one privacy-tradeoff alternate:
  Gemini), these two are general-purpose text tasks, so the dropdown offers every first-class
  provider (Claude / Groq / Perplexity / local; Gemini too on `ai_rewrite`). Groq is included
  even though it isn't a `primaryProvider` option — `we_scoring_summary` processes
  `workExperience.md`, and Gemini's free tier trains on submitted data while Groq's does not.
  The row description says so.
- **Not migrated, documented in-place**: `research-engine.py`'s two `call_llm` sites pass
  `tools=[{"google_search": {}}]`, a Gemini-only capability. Putting them on
  `taskProviderOverrides` would let someone pick a provider with no search tool and silently
  lose grounding.
- **Not migrated, documented in-place**: `scripts/llm_stages.py`'s `STAGE_PROVIDERS` is a
  separate, older per-stage override for the legacy/opt-in UI Draft path, not default
  generate-submission Stage 1. Unifying it is low practical value and real regression risk.

New helper `resolve_default_task_providers(task_id)` in `scripts/utils.py`: same promote-to-front
semantics as `resolve_task_providers`, but the default chain is `_get_configured_providers`
(the task previously just rode `call_llm`'s normal rotation).

## Requirements

- `FR-273`: A detected interview email with an extracted date/time auto-advances the matched
  job's status when `deriveStatusForInterviewDateChange` says the current status is eligible;
  no confirmation step. Dry-run previews without writing.
- `FR-274`: When a provider is rate-limited or a daily cap trips, a user-visible notification
  is written to `activity_log` (`meta.event = 'llm_provider_cascade'`) from either language
  runtime, surfaced in NotificationPanel, and Claude/Perplexity cascade on `retry-after` > 30s
  the same way Groq already did.
- `FR-275`: Settings → AI Usage lists `we_scoring_summary` and `ai_rewrite` as configurable
  tasks. Company-research Gemini-search calls and `STAGE_PROVIDERS` are documented exclusions,
  not oversights. Defaults for both new tasks are unchanged when no override is set.

## Acceptance criteria

- [x] Regex layer parses common explicit invite shapes; LLM fallback is Groq-first, Gemini
      opt-in via `taskProviderOverrides.interview_date_extraction`.
- [x] `Date.parse` rejection of `"...2026 - 12:00 PM"` / `"...2026 at 12:00 PM"` is handled by
      normalize-and-retry; covered by `tests/unit/interviewDateExtractor.test.ts`.
- [x] `gmailSyncOrchestrator.ts` interview branch auto-writes only when extraction succeeded
      and the current status is eligible; dry-run previews the intended action.
- [x] NotificationPanel interview copy renders the orchestrator's own message (no hardcoded
      "update yourself").
- [x] `_call_claude` / `_call_perplexity` cascade past a 30s `retry-after` instead of sleeping;
      each cascade (and daily-cap trip) writes `llm_provider_cascade`. Groq/Gemini Node clients
      do the same at their existing cascade points.
- [x] `GET /api/llm-usage/notifications` returns those rows; NotificationPanel polls it.
- [x] `generate_experience_summary.py` default chain remains `['gemini']` unless
      `taskProviderOverrides.we_scoring_summary` is set.
- [x] `ai_rewrite.py` uses `resolve_default_task_providers('ai_rewrite')`; unset override
      equals prior `call_llm` rotation.
- [x] Settings AI Usage exposes both new task ids; `we_scoring_summary` description flags
      that the input is `workExperience.md`.
- [x] `research-engine.py` and `STAGE_PROVIDERS` carry comments explaining why they are not
      on `taskProviderOverrides`.
- [x] `scripts/test_resolve_task_providers.py` covers both helpers, including the
      we_scoring_summary-must-not-use-the-default-helper regression.
- [x] Full Python suite (`run_all_tests.py`), full JS/TS suite (`vitest run`), and
      `tsc --noEmit` pass.

## Not in scope

- A confirm-first UI step before the interview auto-status-write (easy follow-up if wanted
  after seeing it in practice).
- Unifying `STAGE_PROVIDERS` onto `taskProviderOverrides`.
- Migrating `research-engine.py`'s Gemini-search calls onto `taskProviderOverrides`.
- A review-queue UI inside Applyr for `NEEDS_DISPOSITION` gates (renamed from `WAITING_FOR_HUMAN`
  under CR-107 — see that doc). Parked on the roadmap for later consideration
  (`docs/ROADMAP_BEST_PRACTICES.md` §4), not dropped.
- A full reorderable per-task fallback-chain editor (still the natural next step if that
  need shows up; see `docs/ROADMAP_BEST_PRACTICES.md`).
