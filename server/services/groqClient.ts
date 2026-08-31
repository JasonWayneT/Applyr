// CR-105 — Groq chat-completions client (OpenAI-compatible endpoint). Currently the only real
// caller is the Gmail sync email classifier's low-confidence fallback (server/services/
// emailClassifier.ts via gmailSyncOrchestrator.ts); written standalone rather than folded into
// that file so any future task that needs Groq (per the taskProviderOverrides mechanism in
// llmSettings.ts) can reuse it without duplicating the rate-limit handling below.
import { loadLlmSettings } from './llmSettings.js';
import { logActivity } from '../db.js';

export interface GroqCallResult {
  text: string | null;
  /** True when the call failed specifically because of a rate limit (vs. missing key, network
   *  error, etc.) — callers use this to decide whether "try the next provider" makes sense. */
  rateLimited: boolean;
}

const GROQ_ENDPOINT = 'https://api.groq.com/openai/v1/chat/completions';
// Found 2026-08-31 during the Stage 0-3 replay: 'llama-3.3-70b-versatile' (this default since
// CR-105/106) returns a real 404 "model not found" from Groq's own API — fully deprecated from
// their catalog, not a config issue. Verified openai/gpt-oss-120b against the live API (GET
// /openai/v1/models + a real chat completion) before using it here — mirrors scripts/utils.py.
const DEFAULT_MODEL = 'openai/gpt-oss-120b';

/** Mirrors scripts/utils.py's _call_groq: reads the real `retry-after` header instead of a
 *  blind backoff, and treats anything over 30s as "cascade now" rather than blocking. */
export async function callGroq(
  systemPrompt: string,
  userPrompt: string,
  opts: { model?: string; temperature?: number; maxRetries?: number } = {},
): Promise<GroqCallResult> {
  const settings = loadLlmSettings();
  const apiKey = settings.groqApiKey || process.env.GROQ_API_KEY;
  if (!apiKey) return { text: null, rateLimited: false };

  const model = opts.model ?? DEFAULT_MODEL;
  const temperature = opts.temperature ?? 0.2;
  const maxRetries = opts.maxRetries ?? 3;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    let res: Response;
    try {
      res = await fetch(GROQ_ENDPOINT, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model,
          temperature,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt },
          ],
        }),
      });
    } catch (err) {
      console.error(`[Groq] Network error: ${(err as Error).message}`);
      return { text: null, rateLimited: false };
    }

    if (res.ok) {
      const data = (await res.json()) as { choices?: { message?: { content?: string } }[] };
      return { text: data.choices?.[0]?.message?.content?.trim() ?? null, rateLimited: false };
    }

    if (res.status === 429) {
      const retryAfter = res.headers.get('retry-after');
      const waitSec = retryAfter ? parseFloat(retryAfter) : 5 * (attempt + 1);
      if (waitSec > 30) {
        console.warn(`[Groq] Rate limit needs ${waitSec.toFixed(0)}s — cascading to next provider.`);
        // CR-106: a real, user-visible notification (Settings > AI Usage / NotificationPanel),
        // not just a stderr line — mirrors scripts/utils.py's _log_provider_notification.
        logActivity(
          'WARN',
          'LLM_Call',
          `Groq rate limit needs ${waitSec.toFixed(0)}s — cascading to the next configured provider for this call.`,
          { event: 'llm_provider_cascade', provider: 'groq', reason: 'rate_limited_cascade', wait_seconds: waitSec },
        );
        return { text: null, rateLimited: true };
      }
      console.warn(`[Groq] Rate limited. Waiting ${waitSec.toFixed(0)}s...`);
      await new Promise((resolve) => setTimeout(resolve, waitSec * 1000));
      continue;
    }

    console.error(`[Groq] status ${res.status}: ${await res.text()}`);
    return { text: null, rateLimited: false };
  }

  return { text: null, rateLimited: true };
}
