# Feature Specification: FEAT-007 Multi-LLM Provider Configuration & Routing

## Purpose
To enable users to choose their preferred LLM provider (Gemini, Claude, or a local provider via Ollama or LM Studio) directly inside the Applyr user interface and have both frontend and backend tasks dynamically routed to their chosen model.

## Scope & Functional Description
- **Local SQLite Configuration Store:** Store LLM settings (active provider, cloud API keys, and local base URLs / model names) inside the SQLite `profiles` table under key `'llm_settings'`.
- **Premium User Selection Interface:** Add a settings panel inside the "My Profile" tab where the user can choose their active provider using a gorgeous visual card selector, fully styled to match the Applyr soft minimalist design system.
- **Dynamic Routing Engine (`scripts/utils.py`):** Update `call_llm()` to check the active SQLite configuration and dynamically route queries to Google Gemini, Anthropic Claude, or local OpenAI-compatible endpoints (`/v1/chat/completions` for Ollama and LM Studio).

## Requirements Addressed
* `FR-040`: Multi-LLM Selection & Provider Configuration Support
* `AC-041`: Custom LLM routing based on active database settings
