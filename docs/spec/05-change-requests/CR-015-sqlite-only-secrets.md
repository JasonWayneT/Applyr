# CR-015: SQLite-Only Secrets (Remove .env and Env Injection)

## Metadata

| Field | Value |
|---|---|
| **CR ID** | `CR-015` |
| **Status** | Implemented |
| **Priority** | P0 |
| **Date** | 2026-05-19 |
| **Supersedes** | Env-var key shuttle in `buildPythonEnv()` (CR-005 FR-058) |
| **Implements** | `FR-095`, updates `SEC-003`, `SEC-004` |

## Decision

All API keys and connection credentials live in `jobagent.sqlite` (`profiles` table) and are read at runtime by each script. No `.env` file, no `python-dotenv`, no `os.getenv` fallbacks for secrets. `buildPythonEnv()` sets only `PYTHONUNBUFFERED`.

## Changes

| Component | Action |
|-----------|--------|
| `server/shared.ts` | `buildPythonEnv()` → `{ PYTHONUNBUFFERED: '1' }` only |
| `scripts/utils.py` | Remove `load_dotenv`; keys from `load_llm_settings()` only |
| `scripts/scout_local.ts` | Read `api_connections` from SQLite via `better-sqlite3` |
| `scripts/research-engine.py` | Remove dotenv; Perplexity key from `load_llm_settings()` |
| `.env.example` | Deleted |
| `package.json` / `requirements.txt` | Remove dotenv dependencies |

## Acceptance

- **AC-095:** Pipeline and scout succeed with no `.env` file when keys are saved in Settings UI.
