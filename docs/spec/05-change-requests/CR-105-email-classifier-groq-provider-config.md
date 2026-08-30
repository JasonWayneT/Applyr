---
status: implemented
created: 2026-08-30
related: CR-072, CR-015
---

# CR-105 — Email Classifier Rework, Groq Provider Integration, Task-Scoped Provider Overrides

## Problem

A real 315-message mailbox audit (via the existing read-only Gmail sync feature) found the
CR-072 email classifier's literal-phrase matching missing ~41% of real rejections and 0% of
interview invites (no category for "interview" existed at all). Separately, a concurrent
Antigravity session working in this same repo added a silent Gemini fallback to
`classifyEmailWithLLM` without a design decision behind it — Gemini's free tier trains on
submitted data (per Google's own pricing page) while Groq's does not, and this task sees real
personal correspondence, more sensitive than JD text. Full detail on how this was found and
reasoned through: `docs/spec/08-implementation/SESSION-HANDOFF-2026-08-30-email-classifier-audit.md`.

A third, related problem: Stage 0's `_extract_sections_nlp` (TF-IDF/LogReg classifier +
LLM-fallback + active-learning loop) had been reported elsewhere as "fully implemented and
active." It wasn't — defined but never called from the real pipeline, which still ran the old
`_extract_sections_llm` path unchanged.

## Decision

**Email classifier**: rewrite `classifyEmailText`'s rule-based layer from literal-phrase
matching to vocabulary-of-synonym regexes (kept literal phrases as a cheap first pass
underneath). Add a real `interview` category, wired into `gmailSyncOrchestrator.ts` as a
distinct `gmail_sync_interview` event (surfaced in `NotificationPanel.tsx`), without an
auto-status-write — that needs email date/time extraction that doesn't exist yet.

**Gemini fallback conflict**: resolved as opt-in, not removed and not silently kept. Groq is
always tried first (unchanged). `taskProviderOverrides.email_classification = 'gemini'` (new
Settings → API or Connections → AI Usage row) adds Gemini as a second attempt only when Groq
returns nothing — it never promotes Gemini ahead of Groq the way a generic provider-chain
override normally would. Off by default. This is a deliberate deviation from
`resolveTaskProviders`'s normal "promote to front" semantics, called out in
`emailClassifier.ts`'s own comment above `classifyEmailWithLLM`.

**Groq provider integration**: added to both language runtimes as a real provider, not just for
email classification —`scripts/utils.py` (`_call_groq`, `_is_configured`, `call_llm` dispatch,
`check_rate_limits` extended to track Groq's real free-tier cap: 14,400 req/day, 30 RPM) and
`server/services/groqClient.ts` (Node equivalent, REST call, same rate-limit-header handling).
Groq is task-scoped via explicit override only, never an implicit `primaryProvider` default —
`_get_configured_providers`'s `fixed_order` deliberately excludes it.

**Task-scoped provider overrides**: a new, intentionally minimal mechanism — not the full
"AI Usage" task table from the original design conversation, scoped honestly to the two real
tasks that exist today (Stage 0's ambiguous-bullet fallback, email classification).
`resolve_task_providers(task_id, default_chain)` (Python) / `resolveTaskProviders` (Node,
`server/services/llmSettings.ts`) both read the same `taskProviderOverrides` field off the
`llm_settings` profile row (SQLite, per CR-015 — no `.env` secrets) as two language-local
readers, not a cross-language call. Settings UI: one "AI Usage" card with one dropdown per task.

**Stage 0 NLP wiring**: `_extract_sections_nlp` connected to the real call site.
`pipeline_env.stage0_section_mode()` gained `"nlp"` as the new default (`"llm"` stays available
for rollback via `STAGE0_SECTION_MODE=llm`; `"deterministic"` unchanged for tests). Fixed a
data-quality bug where the JD's own `URL:` line could reach the classifier unstripped
(defensive skip added inside the function, not just relying on callers). Bad training row
removed, model retrained. The LLM fallback inside `_extract_sections_nlp` now requests
`["groq", "gemini"]` via `resolve_task_providers` instead of a hardcoded `"gemini"` string.
`scikit-learn`/`joblib` added to `requirements.txt` and installed in the canonical `.venv`
(missing entirely before this — would have crashed on first real use).

## Requirements

- `FR-268`: Email classifier recognizes rejection, interview, and confirmation categories via
  synonym-vocabulary matching, not literal-phrase-only matching.
- `FR-269`: Email classification's LLM fallback defaults to Groq only; a Gemini second attempt
  is available strictly opt-in via `taskProviderOverrides.email_classification`, and never
  supersedes Groq as the first attempt even when enabled.
- `FR-270`: Groq is a first-class provider in both the Python and Node LLM call layers, with
  real free-tier rate-limit tracking.
- `FR-271`: A task-scoped provider override mechanism exists for Stage 0's extraction fallback
  and email classification, backed by one shared `taskProviderOverrides` field on the
  `llm_settings` profile row.
- `FR-272`: Stage 0's NLP-based section extractor is the default extraction path in the real
  pipeline (not just defined and unused), with a rollback flag to the prior LLM-only path.

## Acceptance criteria

- [x] `emailClassifier.ts`'s rule layer hits 100% recall on all three categories against the
      hand-verified 89-message audit subset, 0 dangerous miscategorizations.
- [x] `classifyEmailWithLLM` tries Groq first unconditionally; Gemini is only attempted when
      `taskProviderOverrides.email_classification === 'gemini'` AND Groq returned nothing.
- [x] `gmailSyncOrchestrator.ts` logs a distinct `gmail_sync_interview` event; no auto
      status-write occurs from it.
- [x] `scripts/utils.py`'s `call_llm` provider dispatcher supports Groq; `provider_override`
      containing `"groq"` is not silently filtered out.
- [x] `pipeline_env.stage0_section_mode()` defaults to `"nlp"`; `STAGE0_SECTION_MODE=llm` and
      `=deterministic` both still work.
- [x] `scikit-learn`/`joblib` present in `requirements.txt` and importable from the project's
      `.venv`.
- [x] `test_stage0_skip_ledger.py` and `test_workflow_authority.py` force
      `STAGE0_SECTION_MODE=deterministic` so routine test runs make no real Groq/Gemini network
      calls and write no rows to `data/training_data_feedback.csv`.
- [x] Settings → API or Connections → AI Usage exposes both task overrides; verified live that
      a saved override persists to SQLite and is read back correctly by both
      `resolve_task_providers` and `resolveTaskProviders`.
- [x] Full Python suite (`run_all_tests.py`) and full JS/TS suite (`vitest run`) pass with the
      above in place; TypeScript typechecks clean.

## Not in scope (landed in CR-106 except the WAITING_FOR_HUMAN review-queue UI)

- Interview auto-status-write (needs date/time extraction from email body). **Done in CR-106.**
- Free-tier cascade-on-exhaustion + usage-notification system (researched, not built). **Done in CR-106.**
- Migrating the remaining hardcoded-provider call sites (company/job research, WE scoring
  summary, Stage 1 `llm_stages.py`'s `STAGE_PROVIDERS`, AI Rewrite) onto
  `taskProviderOverrides`. **Partial in CR-106:** WE scoring summary and AI rewrite wired;
  research-engine Gemini-search calls and `STAGE_PROVIDERS` documented as deliberate exclusions.
- A review-queue UI inside Applyr for `WAITING_FOR_HUMAN` gates. Parked on the roadmap for
  later consideration (`docs/ROADMAP_BEST_PRACTICES.md` §4), not dropped.
