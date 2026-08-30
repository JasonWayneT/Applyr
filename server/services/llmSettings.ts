// CR-105 — shared reader for the llm_settings profile blob (SQLite, per CR-015: SQLite-only
// secrets, no .env). Mirrors scripts/utils.py's load_llm_settings()/resolve_task_providers() on
// the Python side — same profiles-table row, same taskProviderOverrides shape, kept as two
// language-local readers of one shared JSON blob rather than a cross-language call.
import { db } from '../db.js';

export interface LlmSettingsBlob {
  groqApiKey?: string;
  geminiApiKey?: string;
  claudeApiKey?: string;
  perplexityApiKey?: string;
  // task id -> provider promoted to the front of that task's built-in default chain.
  // Settings > API or Connections > "AI Usage". See resolveTaskProviders below.
  taskProviderOverrides?: Record<string, string>;
  [key: string]: unknown;
}

export function loadLlmSettings(): LlmSettingsBlob {
  const row = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as
    | { value: string }
    | undefined;
  if (!row) return {};
  try {
    return JSON.parse(row.value) as LlmSettingsBlob;
  } catch {
    return {};
  }
}

/** Returns the provider chain to try for `taskId`: the user's override (if set) promoted to
 *  the front of defaultChain, else defaultChain unchanged. Mirrors utils.py's
 *  resolve_task_providers exactly. */
export function resolveTaskProviders(taskId: string, defaultChain: string[]): string[] {
  const settings = loadLlmSettings();
  const override = settings.taskProviderOverrides?.[taskId];
  if (!override) return defaultChain;
  return [override, ...defaultChain.filter((p) => p !== override)];
}
