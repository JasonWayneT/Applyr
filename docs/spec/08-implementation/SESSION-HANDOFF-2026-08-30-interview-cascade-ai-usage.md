# SESSION-HANDOFF-2026-08-30 — Interview Auto-Status, Provider Cascade Notifications, AI Usage Table

Handed off mid-task because the session hit its token budget. This picks up directly from
`SESSION-HANDOFF-2026-08-30-email-classifier-audit.md`'s three deferred items ("1. Interview
auto-status-write", "2. Free-tier cascade + usage-notification system", "3. Full AI Usage task
table" — its item "4", a `WAITING_FOR_HUMAN` review-queue UI, was explicitly not requested this
round). **All three items are complete.** Item 3's remaining Settings rows, tests, CR-106,
CHANGELOG, and README landed in the follow-up session. Read this before continuing; don't
re-derive what's already below.

**The older handoff's "⚠️ Live conflict — resolve first" section is already resolved** — verified
this session (`emailClassifier.ts` is Groq-first with Gemini strictly opt-in, matching the
original design intent) and written up in `docs/spec/05-change-requests/CR-105-email-classifier-groq-provider-config.md`.
Don't re-litigate it; that older doc is otherwise still accurate context for *why* items 1-3 exist,
just not for that one section.

## Repo state — nothing here is committed

`git status --porcelain` currently shows **42 changed/untracked paths**, none committed. This
handoff's own work is mixed in with unrelated, already-finished, already-documented prior work
from a concurrent session — don't assume everything in `git status` needs action, and don't
assume anything in it is safe to discard either:

- **This session's items 1+2** (verified, tested, described above): `server/services/{emailClassifier,gmailSyncOrchestrator,groqClient,geminiClient,llmSettings,interviewDateExtractor}.ts`,
  `server/routes/{gmailSync,llmUsage}.ts`, `server/index.ts`, `src/components/{NotificationPanel,SettingsView}.tsx`,
  `scripts/utils.py`, `tests/unit/{emailClassifier,groqClient,geminiClient,interviewDateExtractor}.test.ts`,
  `scripts/test_llm_provider_cascade.py`, `scripts/run_all_tests.py`.
- **This session's item 3** (partial, see below): `scripts/{ai_rewrite,generate_experience_summary}.py`.
- **Already finished, already documented, not this handoff's concern**: `AGENTS.md`, `CHANGELOG.md`,
  `README.md`, `requirements.txt`, `data/stage0_classifier.pkl`, the deleted
  `packages/connectors/{jobscollider,weworkremotely}/` connectors, `server/services/scoutOrchestrator.ts`,
  `shared/domain/gates.ts`, `scripts/bookmarklet/applyr-job-grabber.js`, `server/migrations/017_remove_unused_sources.sql`,
  `scripts/{build_stage0_fit_gate,pipeline_env,test_build_stage0_fit_gate,test_stage0_skip_ledger,test_workflow_authority}.py`,
  `server/routes/profile.ts` — all covered by CR-105's own CHANGELOG entry from earlier the same
  day. Leave these alone unless Jason says otherwise.

Verification commands in this doc assume this repo's pinned virtualenv, per `AGENTS.md`/`CLAUDE.md`:
use `.venv\Scripts\python.exe`, not a bare `python`/`python3` — the venv has `scikit-learn`/`joblib`
installed that a system interpreter won't.

## Item 1 — Interview auto-status-write: DONE, verified

- New [server/services/interviewDateExtractor.ts](../../../server/services/interviewDateExtractor.ts):
  regex layer for common explicit date/time shapes real invites use ("Friday, August 14, 2026 -
  12:00 PM (PDT)"), LLM fallback (Groq first, Gemini opt-in via
  `taskProviderOverrides.interview_date_extraction`, same privacy reasoning as email
  classification). **Real bug found and fixed while testing**: `Date.parse` rejects
  `"...2026 - 12:00 PM"` and `"...2026 at 12:00 PM"` outright — not documented anywhere, only
  found by writing real regression tests. Fixed via a normalize-and-retry step in `tryParse`
  (strips the `-`/`at`/`@` connector immediately before the time).
- [server/services/gmailSyncOrchestrator.ts](../../../server/services/gmailSyncOrchestrator.ts):
  `interview` branch now calls the extractor, and — only when a date/time was actually extracted
  AND `deriveStatusForInterviewDateChange` (shared/domain/jobPipeline.ts) says the job's current
  status is eligible to advance — auto-writes via `applyJobStatusUpdate`, mirroring how the
  `rejection` branch already auto-closes with no confirmation step. Dry-run mode now previews the
  real intended action (extraction has no side effects, so it's safe to run during a dry run).
- [src/components/NotificationPanel.tsx](../../../src/components/NotificationPanel.tsx): the
  interview notification's `detail` text now just renders the orchestrator's own message (which
  already says whether status changed), replacing the old hardcoded "update yourself" copy.
- [src/components/SettingsView.tsx](../../../src/components/SettingsView.tsx): added the
  `interview_date_extraction` row to the AI Usage card, same shape as email classification's row.
- Tests: [tests/unit/interviewDateExtractor.test.ts](../../../tests/unit/interviewDateExtractor.test.ts)
  (9 tests, new).

**Design decision made without asking, on purpose**: auto-write (not a confirm-first UI step),
matching the codebase's own existing precedent (rejection auto-close) rather than adding new
friction. If Jason wants a confirm step instead after seeing it in practice, that's a real,
easy-to-scope follow-up — nothing here blocks it.

## Item 2 — Free-tier cascade + notifications: DONE, verified

**Python (`scripts/utils.py`)**:
- New `_log_provider_notification(provider, message, reason, dedupe=False, extra=None)` — writes
  a real WARN row to `activity_log` (`meta.event = 'llm_provider_cascade'`), not just a stderr
  print. `dedupe=True` checks the last 24h by provider+reason so a tripped daily-cap breaker
  doesn't spam one notification per call.
- `check_rate_limits`'s daily-cap trip now calls this (dedupe=True).
- `_call_claude` and `_call_perplexity` previously did a **blind exponential-backoff sleep loop**
  on 429 (up to `max_retries`, no cascade decision at all) — now read `retry-after` and cascade
  immediately past a 30s threshold, exactly like `_call_groq` already did. Each cascade decision
  now also calls `_log_provider_notification` (dedupe=False — real per-call events, not a
  self-counted breaker).
- `_call_gemini` now notifies once its own retry loop is exhausted (Gemini's REST error body
  doesn't expose a parseable retry delay, so this can't be preemptive like the others).
- New test file `scripts/test_llm_provider_cascade.py` (11 tests) — added to
  `PYTHON_TEST_SCRIPTS` in `scripts/run_all_tests.py`.

**Node**:
- `server/services/groqClient.ts` / `server/services/geminiClient.ts`: same notify-on-cascade
  calls via `logActivity`, at the exact point each already made its cascade decision. This means
  **every caller** (email classification, interview extraction, anything future) gets this for
  free — no per-caller wiring needed.
- New [server/routes/llmUsage.ts](../../../server/routes/llmUsage.ts): `GET
  /api/llm-usage/notifications`, same shape/pattern as `gmailSync.ts`'s notifications route, reads
  `activity_log` rows with `meta.event = 'llm_provider_cascade'` — written by **either** language,
  since both write into the same SQLite table. Wired into `server/index.ts`.
- `src/components/NotificationPanel.tsx`: polls the new endpoint alongside the Gmail one, renders
  a new notification block (bolt icon, tertiary-container color, routes to Settings on click).
- New test [tests/unit/geminiClient.test.ts](../../../tests/unit/geminiClient.test.ts) (4 tests —
  this file didn't exist before; geminiClient.ts only had indirect happy-path coverage).
  `tests/unit/groqClient.test.ts` updated (db.js mock needed a `logActivity` export added, one new
  assertion on the existing cascade test).

Verified clean at this point: **323/323 vitest tests, 39/39 Python test files (via
`run_all_tests.py`), `tsc --noEmit` clean.**

## Item 3 — Full AI Usage task table: DONE

Comments, Settings rows, tests, CR-106, CHANGELOG, and README all landed this session. Defaults
unchanged when no override is set. Company research and `STAGE_PROVIDERS` remain documented
exclusions.

**Settings UI call that was open:** offer every first-class provider (Claude / Groq / Perplexity /
local; Gemini too on `ai_rewrite`), not a single privacy-tradeoff alternate. Groq is included even
though it isn't a `primaryProvider` option, because `we_scoring_summary` processes
`workExperience.md` and Gemini's free tier trains on submitted data. The row description says so.

**Code already in place from the prior session (unchanged this round):**
- `resolve_default_task_providers(task_id)` in `scripts/utils.py`.
- `generate_experience_summary.py` uses `resolve_task_providers('we_scoring_summary', ['gemini'])`
  — deliberately NOT `resolve_default_task_providers`, which would have silently switched the
  default off Gemini.
- `ai_rewrite.py` uses `resolve_default_task_providers('ai_rewrite')`.

**Added this session:** documenting comments on `research-engine.py` (both Gemini-search call
sites) and `STAGE_PROVIDERS`; Settings rows; `scripts/test_resolve_task_providers.py`; CR-106;
CHANGELOG; README.

## Still open (not this thread)

- Confirm-first UI before interview auto-status-write, if wanted after seeing it in practice.
- WAITING_FOR_HUMAN review-queue UI — parked on the roadmap for later consideration
  (`docs/ROADMAP_BEST_PRACTICES.md` §4). Not this thread.
- Dedicated tests for `generate_experience_summary.py` / `ai_rewrite.py` themselves (judgment
  call, skipped — the helpers they call are now tested).
