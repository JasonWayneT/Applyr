# SESSION-HANDOFF-2026-08-30 — Email Classifier Audit, Stage 0 Fix, Groq/Provider Config

Handed off because the originating session's context window ran long. Read this before touching
`server/services/emailClassifier.ts`, `scripts/build_stage0_fit_gate.py`, or Settings' "AI Usage"
section — several of the decisions below are deliberate, not defaults, and one is **actively
conflicting with concurrent work from a separate session (Antigravity) right now.**

## ⚠️ Live conflict — resolve first

A concurrent Antigravity session, working in this same repo in parallel, just added
`server/services/geminiClient.ts` and wired it into `classifyEmailWithLLM` in
`emailClassifier.ts` as a fallback after Groq:

```ts
const groqResult = await callGroq(CLASSIFICATION_SYSTEM_PROMPT, userPrompt, { temperature: 0 });
...
const geminiResult = await callGemini(CLASSIFICATION_SYSTEM_PROMPT, userPrompt, { temperature: 0 });
```

This directly overrides a deliberate design decision from this session (see "Email classifier
Groq wiring" below): **email classification was built Groq-only on purpose** — real personal
correspondence is more sensitive than JD text, and Gemini's free tier trains on submitted data
while Groq's doesn't (verified against both providers' official docs/ToS this session — see
"Free-tier research" below). Adding a silent Gemini fallback for *this specific task* reintroduces
the privacy tradeoff that was the reason Groq was chosen in the first place.

**Do not silently keep or silently revert this** — surface it to Jason and get an explicit call:
either the Gemini fallback for email gets removed (matching the original design), or Jason
explicitly decides the tradeoff is fine for this task now and the code comments/tests should be
updated to reflect that as an intentional, informed choice rather than an accidental regression.
Also check `SettingsView.tsx` and `emailClassifier.test.ts` for related concurrent edits before
changing either — they were mid-edit by the other session when this handoff was written.

Separately, `git status` (as of handoff) also shows unrelated uncommitted changes from that same
concurrent session that predate this conflict: `AGENTS.md`, `CHANGELOG.md`, `README.md`, two
deleted connectors (`jobscollider`, `weworkremotely`), `scoutOrchestrator.ts`,
`shared/domain/gates.ts`, `scripts/bookmarklet/applyr-job-grabber.js`, and a new
`server/migrations/017_remove_unused_sources.sql`. None of those are from this session's work —
don't assume they're safe to discard, but don't assume they're finished either.

## What this session actually did, in order

### 1. Email classifier rewrite (rule-based layer)

`server/services/emailClassifier.ts`'s `classifyEmailText` was rewritten from literal-phrase
matching to vocabulary-of-synonym regexes, after a real 315-message mailbox audit (pulled via the
existing Gmail sync feature, read-only) found the old approach missing ~41% of real rejections and
0% of interview invites (no category for it existed). Result on the hand-verified 89-message
subset: 100% recall on all three categories (rejection/interview/confirmation), 0 dangerous
miscategorizations (e.g. a real rejection silently logged as a confirmation). Full reasoning and
real (paraphrased) examples are in that file's own comments — read them before changing any
pattern, several encode a specific false-positive trap that was found and fixed (the "future
promise" disclaimer guard, the subject-only "interview confirmation" check, etc.).
`tests/unit/emailClassifier.test.ts` has the regression-guard tests.

### 2. Interview category wired into the real pipeline

`gmailSyncOrchestrator.ts` previously had no branch for `'interview'` — it would've silently
logged a real interview invite as a plain confirmation. Now logs it distinctly
(`gmail_sync_interview` event, surfaced in the Notifications panel — `NotificationPanel.tsx` and
`gmailSync.ts`'s `/api/gmail-sync/notifications` route both updated). **Deliberately does not
auto-write a status change yet** — `Recruiter Screen`/`Core Interviews` require `interview_date`
(`shared/domain/jobPipeline.ts`'s `statusRequiresInterviewDateTime`), and this doesn't extract a
date/time from the email. That's real, not-yet-built scope, not an oversight — see "Not done" below.

### 3. Groq added to the Python LLM layer

`scripts/utils.py` had zero knowledge of Groq before this session — no `_is_configured` entry, no
`_call_groq`, not in `call_llm`'s provider dispatcher. Added all three, plus extended
`check_rate_limits` (a self-counted circuit breaker via `activity_log`, previously Gemini-only) to
also track Groq against its real free-tier cap (14,400 req/day, 30 RPM — verified via Groq's own
docs). Fixed a real bug in the same pass: `provider_override=["groq", ...]` would have been
silently filtered to nothing, because `_get_configured_providers`'s `fixed_order` deliberately
excludes Groq (it's meant to be task-scoped via explicit override, never an implicit
`primaryProvider` default) but the override filter was checking membership in that same list
instead of checking `_is_configured` directly. Fixed to check configuration directly.

### 4. Stage 0 NLP integration — found broken, fixed

A separate concurrent-session write-up claimed the TF-IDF/LogReg classifier + LLM-fallback +
active-learning loop (`_extract_sections_nlp` in `build_stage0_fit_gate.py`,
`scripts/retrain_stage0.py`) was "fully implemented and active." Verified against the actual
commit (`589dd19`) and found this **false**: the function was defined but never called from
anywhere in the codebase — the real pipeline (`build_stage0_fit_gate.py`'s main flow) still called
the old local-model-pinned `_extract_sections_llm` unchanged. Also found a real data-quality bug:
a demo run had fed the JD's own `URL: <url>` first line to the classifier (should have been
stripped by `_parse_url_and_jd` first, wasn't in that demo), which got labeled "preferred" by the
LLM fallback and landed in `data/training_data_feedback.csv` — then **double-weighted** by
`retrain_stage0.py`'s own design.

Fixed this session:
- `_extract_sections_nlp` now wired into the real call site.
  `pipeline_env.stage0_section_mode()` gained a third value, `"nlp"`, now the default (`"llm"`
  stays available for rollback via `STAGE0_SECTION_MODE=llm`, `"deterministic"` unchanged for tests).
- Defensive `URL:` line skip added inside the function itself, not just relying on callers to
  strip it first.
- Bad training row removed, model retrained clean.
- The LLM fallback inside `_extract_sections_nlp` now requests `["groq", "gemini"]` (via
  `resolve_task_providers`, see below) instead of a hardcoded `"gemini"` string.
- **Missing dependency found and fixed**: `scikit-learn`/`joblib` were not in `requirements.txt`
  and not installed in the project's canonical `.venv` — the feature would have crashed the first
  time the real app (which enforces this exact venv via `invoke_applyr_python.mjs`) tried to run
  it. Installed and pinned in `requirements.txt`.
- Added `tests/... TestSectionExtractionNLP` (3 tests) covering the URL bug and the
  Groq-then-Gemini fallback order specifically, since nothing else exercised this function directly.

**A second real regression was found and fixed during verification, not before**: two existing
tests (`test_stage0_skip_ledger.py`, one method in `test_workflow_authority.py`) called the real
Stage 0 pipeline without mocking the LLM call. Under the old `"llm"` default this was harmless
(hit local Ollama, no cost, no side effect). Under the new `"nlp"` default it started making real
Groq/Gemini network calls with Jason's real configured key **during routine test runs**, and
writing real rows into `training_data_feedback.csv` as a side effect of running tests. Root-caused
by bisecting test-by-test (found by watching the feedback CSV grow after each file), fixed by
forcing `STAGE0_SECTION_MODE=deterministic` in both, matching how the rest of the Stage 0 test
suite already does this. Confirmed clean after the fix: full Python suite (37 files) green, feedback
CSV unchanged across a full run.

### 5. Minimal task-provider-override mechanism (Python + Node)

Not the full "AI Usage" vision from the design conversation earlier in this session (see "Not
done" below) — scoped honestly to the two real tasks that exist today:

- `scripts/utils.py`: `resolve_task_providers(task_id, default_chain)` — reads
  `llm_settings.taskProviderOverrides[task_id]`, promotes that provider to the front of
  `default_chain` if set, else returns it unchanged.
- `server/services/llmSettings.ts` + `server/services/groqClient.ts`: Node-side equivalents
  (`resolveTaskProviders`, `callGroq`) reading the identical JSON field from the same SQLite row —
  two language-local readers of one shared blob, same pattern already used for the rest of
  `llm_settings`, not a cross-language call.
- Settings UI: new "AI Usage" card in **Settings → API or Connections**, below the existing Groq
  key card. One dropdown for Stage 0's fallback ("Use default (Groq, then Gemini)" /
  "Prefer Gemini first"), one informational row for email classification (Groq-only, no override
  to offer yet — see the live conflict above, which changes whether that's still true). Verified
  end-to-end live in the running app: picking an override persists to the real database and
  `resolve_task_providers`/`resolveTaskProviders` both read it back correctly.

### 6. Free-tier research (informs future work, nothing built from it yet)

Verified against official docs, not just aggregator blogs:
- **Groq**: free, no card, doesn't train on submitted data (per its Services Agreement), exposes
  `x-ratelimit-remaining-requests`/`-tokens` headers on *every* response (not just 429s) — genuine
  proactive quota visibility.
- **Gemini**: free, no card, but its free tier **does** train on submitted data (per Google's own
  pricing page: "Content used to improve our products" = Yes for free tier). No documented live
  remaining-quota headers — only found out via a 429.
- **Anthropic (Claude)**: same header shape as Groq (`anthropic-ratelimit-*-remaining` on every
  response).
- **Perplexity**: 429 + `Retry-After` only, no proactive headers, same gap as Gemini.

This grounds the "cascade to the next provider on rate-limit exhaustion + notify the user" roadmap
item Jason asked about — technically real and buildable, not yet built. Sketch: on 429, read which
specific limit tripped and its `retry-after` window to distinguish a momentary throttle (retry same
provider) from a real daily-cap exhaustion (cascade now) — Groq's client-side code already does
this (`server/services/groqClient.ts`, `scripts/utils.py`'s `_call_groq`); Gemini/Perplexity would
need self-counted estimation the way `check_rate_limits` already does for Gemini, since neither
exposes a live count.

## Not done — explicitly deferred, not forgotten

- **Interview auto-status-write.** Needs date/time extraction from the email body (real invites in
  the audit consistently stated an explicit date/time — "Friday, August 14, 2026 - 12:00 PM
  (PDT)"). `shared/domain/jobPipeline.ts`'s `deriveStatusForInterviewDateChange` already has the
  correct forward-only round-aware promotion logic (`Recruiter Screen` → `Core Interviews`) —
  reuse it once extraction exists, don't reinvent it.
- **Free-tier cascade + usage-notification system.** Researched and designed (see above), not
  built. Would reuse the existing `logActivity()` → Notifications-panel pipeline (same one used for
  the new `gmail_sync_interview` event) rather than needing new UI infrastructure.
- **Full "AI Usage" task table.** Only Stage 0's fallback and email classification are wired into
  `taskProviderOverrides` today. Other real AI call sites found during the audit — company/job
  research (hardcoded Gemini, `research-engine.py`), `workExperience.md` scoring summary
  (hardcoded Gemini), Stage 1 draft stages (`scripts/llm_stages.py`'s `STAGE_PROVIDERS`, a
  separate, older per-stage mechanism, currently only wired to the legacy/opt-in UI Draft path
  per its own docstring — **not** the default `generate-submission` Stage 1 authoring flow),
  "Apply AI Rewrite" (`ai_rewrite.py`, no override, uses whatever `primaryProvider` is set to) —
  are documented but not migrated onto the new mechanism.
- **UX judgment on Settings layout**: one page, not a separate "Advanced" destination — reasoning
  was that Advanced Settings earns its keep protecting a large non-technical user population from
  complexity, and Applyr's whole audience is Jason (or an equally hands-on future user), so hiding
  this costs discoverability for no real benefit at this scale. Revisit if the task list grows
  past what fits comfortably on one screen.
- **The "who orchestrates when there's no chat agent in the loop" question** (decoupling Applyr
  from a harness) — reframed, not solved: `run_submission.py`'s `workflow_state.json` +
  `WAITING_FOR_LLM`/`WAITING_FOR_HUMAN` states are already a real (if hand-rolled) "durable
  execution" pattern — the industry term for suspend/resume state machines with human-in-the-loop
  gates (Temporal/Inngest are the named frameworks for this, not a suggestion to adopt either, just
  useful vocabulary). The provider-vault/task-binding work in this session is the piece that
  replaces "a human pastes a prompt into chat" with a direct API call — the genuinely missing piece
  is a real review-queue UI *inside Applyr* for the `WAITING_FOR_HUMAN` gate, which doesn't exist
  anywhere yet.

## Verification state as of handoff

Full Python suite (`run_all_tests.py`, 37 files): all passing, `data/training_data_feedback.csv`
confirmed unchanged across a full run (no more test-induced real API calls). Full JS/TS suite
(vitest): 308 passing as of the last clean run *before* the concurrent session's Gemini-fallback
edit landed — **re-run both suites after resolving the live conflict above**, don't trust this
number blindly once that file changes again. TypeScript: clean as of the same point.
