// CR-105 — Groq client + task-provider-override resolver. Mocks db.js (per the pattern already
// established in tests/unit/scoutOrchestrator.test.ts) and global fetch (per
// tests/unit/ollamaLifecycle.test.ts) rather than hitting real Groq or the real database.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../server/db.js', () => ({
  db: { prepare: vi.fn(() => ({ get: vi.fn(() => undefined) })) },
  logActivity: vi.fn(), // CR-106: callGroq's cascade branch now calls this
}));

const { db, logActivity } = await import('../../server/db.js');
const { loadLlmSettings, resolveTaskProviders } = await import('../../server/services/llmSettings.js');
const { callGroq } = await import('../../server/services/groqClient.js');

function mockSettingsRow(settings: Record<string, unknown>) {
  vi.mocked(db.prepare).mockReturnValue({
    get: vi.fn(() => ({ value: JSON.stringify(settings) })),
  } as any);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', vi.fn());
});

describe('loadLlmSettings / resolveTaskProviders', () => {
  it('returns empty object when no row exists', () => {
    expect(loadLlmSettings()).toEqual({});
  });

  it('returns the default chain unchanged when no override is set', () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    expect(resolveTaskProviders('email_classification', ['groq'])).toEqual(['groq']);
  });

  it('promotes the overridden provider to the front, deduped', () => {
    mockSettingsRow({ taskProviderOverrides: { stage0_extraction: 'gemini' } });
    expect(resolveTaskProviders('stage0_extraction', ['groq', 'gemini'])).toEqual(['gemini', 'groq']);
  });

  it('leaves an unrelated task unaffected by another task\'s override', () => {
    mockSettingsRow({ taskProviderOverrides: { stage0_extraction: 'gemini' } });
    expect(resolveTaskProviders('email_classification', ['groq'])).toEqual(['groq']);
  });
});

describe('callGroq', () => {
  it('returns null text with no rate limit when no API key is configured', async () => {
    mockSettingsRow({});
    const result = await callGroq('system', 'user');
    expect(result).toEqual({ text: null, rateLimited: false });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('returns the completion text on a 200 response', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ choices: [{ message: { content: '  rejection  ' } }] }),
    } as any);
    const result = await callGroq('system', 'user');
    expect(result).toEqual({ text: 'rejection', rateLimited: false });
  });

  it('retries a short rate-limit wait and cascades on a long one', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 429,
      headers: new Headers({ 'retry-after': '3600' }),
    } as any);
    const result = await callGroq('system', 'user', { maxRetries: 2 });
    expect(result).toEqual({ text: null, rateLimited: true });
    expect(fetch).toHaveBeenCalledTimes(1); // did not retry — cascaded immediately
    // CR-106: a real notification, not just a stderr line
    expect(logActivity).toHaveBeenCalledWith(
      'WARN',
      'LLM_Call',
      expect.stringContaining('cascading'),
      expect.objectContaining({ event: 'llm_provider_cascade', provider: 'groq' }),
    );
  });

  it('returns null, not rate-limited, on a non-429 error status', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 500,
      text: async () => 'server error',
    } as any);
    const result = await callGroq('system', 'user');
    expect(result).toEqual({ text: null, rateLimited: false });
  });
});
