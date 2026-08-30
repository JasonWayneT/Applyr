// CR-106 — regression tests for extractInterviewDateTime. Fixtures are paraphrased interview-invite
// shapes from the CR-105 audit ("Friday, August 14, 2026 - 12:00 PM (PDT)" style), not pasted real
// emails. Mirrors tests/unit/emailClassifier.test.ts's mocking pattern (db.js mock + stubbed fetch)
// since this module reuses the same llmSettings/groqClient/geminiClient plumbing.
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../../server/db.js', () => ({
  db: { prepare: vi.fn(() => ({ get: vi.fn(() => undefined) })) },
}));

const { db } = await import('../../server/db.js');
const { extractInterviewDateTime } = await import('../../server/services/interviewDateExtractor.js');

function mockSettingsRow(settings: Record<string, unknown>) {
  vi.mocked(db.prepare).mockReturnValue({
    get: vi.fn(() => ({ value: JSON.stringify(settings) })),
  } as any);
}

describe('extractInterviewDateTime — pattern layer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
    mockSettingsRow({}); // no keys configured — proves the pattern layer needs no network call
  });

  it('parses "Weekday, Month Day, Year - Time (Zone)" (real audit shape)', async () => {
    const result = await extractInterviewDateTime(
      'Interview Confirmation',
      'Your interview is scheduled for Friday, August 14, 2026 - 12:00 PM (PDT). Looking forward to it.',
    );
    expect(result?.method).toBe('pattern');
    expect(new Date(result!.isoDateTime).getUTCFullYear()).toBe(2026);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('parses "Month Day, Year at Time" without a day-of-week prefix', async () => {
    const result = await extractInterviewDateTime(
      'Update',
      'We would like to invite you to interview on August 14, 2026 at 12:00 PM.',
    );
    expect(result?.method).toBe('pattern');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('parses an ISO-style date/time', async () => {
    const result = await extractInterviewDateTime('Update', 'Your call is booked for 2026-08-14 12:00.');
    expect(result?.method).toBe('pattern');
  });

  it('checks the subject line too, not just the body', async () => {
    const result = await extractInterviewDateTime(
      'Interview scheduled: August 14, 2026 at 12:00 PM',
      'See you then.',
    );
    expect(result?.method).toBe('pattern');
  });

  it('falls through to the LLM layer (and returns null with no key configured) when no explicit date/time is stated', async () => {
    const result = await extractInterviewDateTime(
      'Interview Confirmation',
      'We would like to schedule an interview soon — what does your availability look like next week?',
    );
    expect(result).toBeNull();
    expect(fetch).not.toHaveBeenCalled(); // no Groq/Gemini key configured
  });
});

describe('extractInterviewDateTime — LLM fallback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
  });

  function mockGroqReply(content: string) {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ choices: [{ message: { content } }] }),
    } as any);
  }

  function mockGeminiReply(text: string) {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ candidates: [{ content: { parts: [{ text }] } }] }),
    } as any);
  }

  it('uses Groq to parse a date the regex layer misses', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    mockGroqReply('2026-08-14T12:00:00');
    const result = await extractInterviewDateTime(
      'Interview Confirmation',
      'Let\'s connect next Friday at noon Pacific to discuss the role further.',
    );
    expect(result?.method).toBe('llm');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('groq.com');
  });

  it('treats the model\'s NONE reply as no extraction, not a crash', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    mockGroqReply('NONE');
    const result = await extractInterviewDateTime('Update', 'We will be in touch soon about next steps.');
    expect(result).toBeNull();
  });

  it('never falls back to Gemini for this task unless explicitly opted in (same privacy default as email classification)', async () => {
    mockSettingsRow({ geminiApiKey: 'gm_x' }); // Gemini configured, Groq is not, no override
    const result = await extractInterviewDateTime('Update', 'Let\'s talk soon about scheduling.');
    expect(result).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('only tries Gemini once explicitly opted in via taskProviderOverrides.interview_date_extraction', async () => {
    mockSettingsRow({
      geminiApiKey: 'gm_x',
      taskProviderOverrides: { interview_date_extraction: 'gemini' },
    });
    mockGeminiReply('2026-08-14T12:00:00');
    const result = await extractInterviewDateTime('Update', 'Let\'s talk soon about scheduling.');
    expect(result?.method).toBe('llm');
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('generativelanguage.googleapis.com');
  });
});
