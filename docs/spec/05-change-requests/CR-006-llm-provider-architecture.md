# CR-006 — LLM Provider Architecture

**Status:** Implemented
**Date:** 2026-05-09
**Author:** Jason Wayne

## Overview

Redesign the LLM provider system to support multiple configured providers with automatic fallback, a provider configuration guard (no key = no call), Perplexity repositioned as a general LLM provider (not a data source), and all providers configurable exclusively via the frontend settings UI.

## Motivation

- Users may have keys for some providers but not others — the system should silently skip unconfigured providers rather than failing
- A single provider error should not fail the entire pipeline when another provider is available
- Perplexity's `sonar-pro` model can serve as a general-purpose LLM with web retrieval, not just a company research tool
- The previous UI listed only 3 LLM providers and placed Perplexity under "Data Sources," which was semantically incorrect
- The module-level `genai.Client` bootstrap in `utils.py` line 13 caused import-time failures when `GEMINI_API_KEY` was unset

## Requirements

| ID | Title | Description |
|----|-------|-------------|
| FR-059 | Provider configuration guard | `call_llm()` must call `_is_configured(provider, settings)` before invoking any provider. If no configured providers exist, return `""` and log an actionable warning directing the user to Settings. |
| FR-060 | Multi-provider fallback chain | `call_llm()` iterates configured providers: primary first, then remaining in fixed order `[gemini, claude, local, perplexity]`. Non-rate-limit errors fall through to the next provider. Rate limit errors retry within the same provider up to `max_retries`. |
| FR-061 | Perplexity as LLM provider | Perplexity `sonar-pro` is added as a valid `call_llm()` provider branch. Key stored in `llm_settings.perplexityApiKey`. `research-engine.py` tries Perplexity first if configured (native web retrieval), then falls back to the primary LLM via `call_llm()`. |
| FR-062 | Four-card LLM provider UI | SettingsView "API or Connections" tab shows 4 provider cards: Gemini, Claude, Local, Perplexity. Each card displays an always-visible key/URL field, a Connected badge when credentials are present, and a "Set Primary" / "Primary" button. |
| FR-063 | `primaryProvider` field | `LlmSettings.provider` renamed to `primaryProvider` in both frontend TypeScript and Python with backward-compat read: `settings.get("primaryProvider") or settings.get("provider", "gemini")`. |

## Non-Functional Requirements

| ID | Description |
|----|-------------|
| NFR-005 | No LLM provider is called unless `_is_configured()` returns `True`. Zero silent token waste from misconfigured providers. |

## Security

| ID | Description |
|----|-------------|
| SEC-004 | `perplexityApiKey` is stored in `llm_settings` (SQLite profiles table, gitignored). Removed from `api_connections`. All key injection at spawn time via env vars — never written to disk or logged. |

## Impact Surface

| File | Change |
|------|--------|
| `scripts/utils.py` | Remove global Gemini client bootstrap; add `_is_configured()`, `_get_configured_providers()`, `_call_gemini()`, `_call_claude()`, `_call_local()`, `_call_perplexity()`; refactor `call_llm()` to fallback loop |
| `scripts/research-engine.py` | Remove module-level env read; read Perplexity key from `load_llm_settings()` at call time; `fetch_company_intel()` tries Perplexity if configured, else falls back to `call_llm()` |
| `server/scout.ts` | Move `perplexityApiKey` injection from `api_connections` block to `llm_settings` block |
| `server/index.ts` | Update `buildPythonEnv()` to read `perplexityApiKey` from `llm_settings` not `api_connections` |
| `src/components/SettingsView.tsx` | `LlmSettings` gains `perplexityApiKey` and renames `provider` → `primaryProvider`; `ApiConnections` drops `perplexityApiKey`; UI redesigned to 4-card layout |
