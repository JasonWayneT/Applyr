# Feature Specification: FEAT-007 Multi-LLM Provider Configuration & Routing

## Purpose
To enable users to choose their preferred LLM provider (Gemini, Claude, or a local provider via Ollama or LM Studio) directly inside the Applyr user interface and have both frontend and backend tasks dynamically routed to their chosen model.

## Scope & Functional Description
- **Local SQLite Configuration Store:** Store LLM settings (active provider, cloud API keys, and local base URLs / model names) inside the SQLite `profiles` table under key `'llm_settings'`.
- **Premium User Selection Interface:** Add a settings panel inside the "My Profile" tab where the user can choose their active provider using a gorgeous visual card selector, fully styled to match the Applyr soft minimalist design system.
- **Dynamic Routing Engine (`scripts/utils.py`):** Update `call_llm()` to check the active SQLite configuration and dynamically route queries to Google Gemini, Anthropic Claude, or local OpenAI-compatible endpoints (`/v1/chat/completions` for Ollama and LM Studio).

## Requirements Addressed
* `FR-040`: Multi-LLM Selection & Provider Configuration Support
* `FR-279`: Stage 0 evidence provider/model policy is configurable, with Groq -> Gemini as the default chain and Local as an explicit option (`CR-108`, rollout-flagged)
* `AC-041`: Custom LLM routing based on active database settings

## CR-108 hardening verification

The Stage 0 provider policy must be normalized identically by Python and
TypeScript. A shared fixture covers the default Groq-to-Gemini chain,
provider-specific model identifiers, explicit Local-only mode, and invalid or
duplicate provider entries. Provider golden tests use deterministic transport
fixtures by default. Live Groq/Gemini calls are an opt-in release-gate sample,
not a required offline test dependency.

The deterministic provider fixtures pass all 21 active CR-093 entries for both
Groq and Gemini. Python and TypeScript normalization parity is verified. The
live sample and default cutover remain deferred.
