# Change Request: CR-005 API Key Unification

## Metadata

- CR ID: `CR-005`
- Status: implemented
- Date: 2026-05-09
- Requested by: User
- Implements: `FR-057`, `FR-058`, `SEC-003`
- Feature spec: `FEAT-008`

## Problem

After CR-004, three inconsistencies remained in API key handling:

1. **Perplexity API key** — `scripts/research-engine.py` reads directly from `os.getenv("PERPLEXITY_API_KEY")` with no SQLite fallback and no UI entry point. Users must edit `.env` manually for company research to function.

2. **Gemini bootstrap fragility** — `scripts/utils.py` creates a global `genai.Client` at module import time using `os.getenv("GEMINI_API_KEY")`. Even though `call_llm()` is DB-first, the module fails to import entirely if the env var is absent — silently breaking the entire pipeline.

3. **Python spawns do not inject DB keys** — Both `POST /api/jobs/:id/evaluate` and `POST /api/jobs/:id/draft` in `server/index.ts` spawn `batch_pipeline.py` with only `env: { ...process.env }`. If a user has set their Gemini or Perplexity keys exclusively via the UI (SQLite) and has no `.env` file, every evaluation and draft fails.

Net effect: users MUST maintain a `.env` file alongside the UI, defeating the purpose of the settings panel.

## Solution

### FR-057 — Perplexity UI entry point
Add a "Perplexity AI" card to `SettingsView.tsx` under the existing "Data Sources" section. `perplexityApiKey` stored as a field on the `api_connections` profile key (same SQLite record as Adzuna). `ApiConnections` TypeScript interface extended accordingly.

### FR-058 — Unified Python env injection
Add a `buildPythonEnv()` helper function in `server/index.ts` that reads both `llm_settings` and `api_connections` from the SQLite `profiles` table and returns a flat env-var object:
- `geminiApiKey` → `GEMINI_API_KEY`
- `claudeApiKey` → `ANTHROPIC_API_KEY`
- `perplexityApiKey` → `PERPLEXITY_API_KEY`

This env object is merged into `{ ...process.env, ...buildPythonEnv() }` for all Python spawns in both `server/index.ts` and `server/scout.ts`. Because Python's `load_dotenv()` does not override existing environment variables by default, server-injected values always take precedence over any stale `.env` content.

### SEC-003 — .env is a fallback, not a requirement
With FR-057 and FR-058 implemented, every API key has a UI entry point and a DB-first read path. The `.env` file becomes an optional local developer convenience, not a requirement for the application to function. `.env.example` updated to reflect this.

## Files Changed

| File | Change |
|------|--------|
| `src/components/SettingsView.tsx` | `perplexityApiKey` added to `ApiConnections`; Perplexity card added to Data Sources section |
| `server/index.ts` | `buildPythonEnv()` helper added; both Python spawn calls updated |
| `server/scout.ts` | `extraEnv` expanded to include LLM keys; `evalProcess` spawn now receives `extraEnv` |
| `.env.example` | Updated to clarify UI-first approach; `.env` marked as optional fallback |
| `docs/spec/02-requirements-registry.md` | FR-057, FR-058, SEC-003 added |
