// CR-105 — Gemini REST client (generateContent endpoint). Currently the only real caller is the
// Gmail sync email classifier's opt-in secondary fallback (server/services/emailClassifier.ts);
// written standalone, mirroring groqClient.ts's shape, so any future task that needs Gemini via
// the taskProviderOverrides mechanism (llmSettings.ts) can reuse it without duplicating the
// rate-limit handling below. No @google/genai SDK dependency in package.json, so this calls the
// plain REST endpoint directly rather than pulling one in for a single call site.
import { loadLlmSettings } from './llmSettings.js';
import { logActivity } from '../db.js';

export interface GeminiCallResult {
  text: string | null;
  /** True when the call failed specifically because of a rate limit/quota (vs. missing key,
   *  network error, etc.) — callers use this to decide whether "try the next provider" makes
   *  sense. */
  rateLimited: boolean;
}

const GEMINI_ENDPOINT_BASE = 'https://generativelanguage.googleapis.com/v1beta/models';
// Mirrors scripts/utils.py's DEFAULT_MODEL — same provider default on both language sides.
const DEFAULT_MODEL = 'gemini-3.5-flash-lite';

/** Mirrors scripts/utils.py's _call_gemini: same default model, same "quota/429/503 means
 *  cascade to the next provider" treatment, adapted to this file's retry/backoff shape (see
 *  callGroq in groqClient.ts). */
export async function callGemini(
  systemPrompt: string,
  userPrompt: string,
  opts: { model?: string; temperature?: number; maxRetries?: number } = {},
): Promise<GeminiCallResult> {
  const settings = loadLlmSettings();
  const apiKey = settings.geminiApiKey || process.env.GEMINI_API_KEY;
  if (!apiKey) return { text: null, rateLimited: false };

  const model = opts.model ?? DEFAULT_MODEL;
  const temperature = opts.temperature ?? 0.2;
  const maxRetries = opts.maxRetries ?? 3;
  const endpoint = `${GEMINI_ENDPOINT_BASE}/${model}:generateContent?key=${apiKey}`;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    let res: Response;
    try {
      res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_instruction: { parts: [{ text: systemPrompt }] },
          contents: [{ parts: [{ text: userPrompt }] }],
          generationConfig: { temperature },
        }),
      });
    } catch (err) {
      console.error(`[Gemini] Network error: ${(err as Error).message}`);
      return { text: null, rateLimited: false };
    }

    if (res.ok) {
      const data = (await res.json()) as {
        candidates?: { content?: { parts?: { text?: string }[] } }[];
      };
      const text = data.candidates?.[0]?.content?.parts?.[0]?.text?.trim() ?? null;
      return { text, rateLimited: false };
    }

    if (res.status === 429 || res.status === 503) {
      const waitSec = 5 * (attempt + 1);
      console.warn(`[Gemini] Rate limited/unavailable (${res.status}). Waiting ${waitSec}s...`);
      await new Promise((resolve) => setTimeout(resolve, waitSec * 1000));
      continue;
    }

    console.error(`[Gemini] status ${res.status}: ${await res.text()}`);
    return { text: null, rateLimited: false };
  }

  // CR-106: real notification once retries are exhausted, matching groqClient.ts's cascade
  // notification — Gemini's REST error body doesn't expose a parseable retry-delay the way
  // Groq's retry-after header does, so this only fires after the blind retry loop above gives up.
  logActivity(
    'WARN',
    'LLM_Call',
    'Gemini is rate-limited/unavailable after retrying — cascading to the next configured provider for this call.',
    { event: 'llm_provider_cascade', provider: 'gemini', reason: 'rate_limited_cascade' },
  );
  return { text: null, rateLimited: true };
}
