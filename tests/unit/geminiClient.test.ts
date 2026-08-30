// CR-106 — regression tests for callGemini, mirroring tests/unit/groqClient.test.ts's mocking
// pattern. Written alongside the new "notify on retries-exhausted" behavior added this session —
// geminiClient.ts had no dedicated test file before, only indirect happy-path coverage via
// emailClassifier.test.ts / interviewDateExtractor.test.ts.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../../server/db.js', () => ({
  db: { prepare: vi.fn(() => ({ get: vi.fn(() => undefined) })) },
  logActivity: vi.fn(),
}));

const { db, logActivity } = await import('../../server/db.js');
const { callGemini } = await import('../../server/services/geminiClient.js');

function mockSettingsRow(settings: Record<string, unknown>) {
  vi.mocked(db.prepare).mockReturnValue({
    get: vi.fn(() => ({ value: JSON.stringify(settings) })),
  } as any);
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('fetch', vi.fn());
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('callGemini', () => {
  it('returns null (not a network call) when no Gemini key is configured', async () => {
    mockSettingsRow({});
    const result = await callGemini('system', 'user');
    expect(result).toEqual({ text: null, rateLimited: false });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('returns the model reply on success', async () => {
    mockSettingsRow({ geminiApiKey: 'gm_x' });
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ candidates: [{ content: { parts: [{ text: '  rejection  ' }] } }] }),
    } as any);
    const result = await callGemini('system', 'user');
    expect(result).toEqual({ text: 'rejection', rateLimited: false });
  });

  it('returns null, not rate-limited, on a non-429/503 error status', async () => {
    mockSettingsRow({ geminiApiKey: 'gm_x' });
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 400, text: async () => 'bad request' } as any);
    const result = await callGemini('system', 'user');
    expect(result).toEqual({ text: null, rateLimited: false });
    expect(logActivity).not.toHaveBeenCalled();
  });

  it('notifies once retries are exhausted on repeated 429s', async () => {
    mockSettingsRow({ geminiApiKey: 'gm_x' });
    vi.mocked(fetch).mockResolvedValue({ ok: false, status: 429, text: async () => 'quota' } as any);
    const resultPromise = callGemini('system', 'user', { maxRetries: 2 });
    await vi.runAllTimersAsync();
    const result = await resultPromise;
    expect(result).toEqual({ text: null, rateLimited: true });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(logActivity).toHaveBeenCalledWith(
      'WARN',
      'LLM_Call',
      expect.stringContaining('cascading'),
      expect.objectContaining({ event: 'llm_provider_cascade', provider: 'gemini' }),
    );
  });
});
