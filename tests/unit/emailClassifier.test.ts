// CR-105 — regression tests for classifyEmailText's free/local pattern layer. Fixtures are paraphrased
// from a real 315-message mailbox audit (SESSION-HANDOFF-2026-08-30-email-classifier-audit.md), not
// pasted verbatim, so no real recruiter names/addresses/company-specific wording ends up committed —
// only the structural shape that made each one a real miss or a real false-positive risk.
import { describe, it, expect, vi, beforeEach } from 'vitest';

// emailClassifier.ts now imports llmSettings.js (for classifyEmailWithLLM's task-provider
// override), which imports db.js — mock it the same way tests/unit/scoutOrchestrator.test.ts
// and tests/unit/groqClient.test.ts do, so this file doesn't open the real project database.
vi.mock('../../server/db.js', () => ({
  db: { prepare: vi.fn(() => ({ get: vi.fn(() => undefined) })) },
}));

const { db } = await import('../../server/db.js');
const { classifyEmailText, classifyEmailWithLLM } = await import('../../server/services/emailClassifier.js');

function mockSettingsRow(settings: Record<string, unknown>) {
  vi.mocked(db.prepare).mockReturnValue({
    get: vi.fn(() => ({ value: JSON.stringify(settings) })),
  } as any);
}

describe('classifyEmailText — rejection', () => {
  it('matches the original literal-phrase templates (unchanged from CR-072)', () => {
    expect(classifyEmailText('Update', 'We have decided not to move forward with your application.')).toBe(
      'rejection',
    );
    expect(classifyEmailText('Update', 'This position has been filled.')).toBe('rejection');
  });

  it('matches active AND passive voice for "position filled" (Pax8 / Talkiatry-style)', () => {
    expect(classifyEmailText('Update', 'We have filled the position for this role.')).toBe('rejection');
    expect(classifyEmailText('Update', 'The role has now been filled.')).toBe('rejection');
  });

  it('matches "filled" past an intervening relative clause (PointClickCare-style)', () => {
    expect(
      classifyEmailText('Update', 'Unfortunately the position you applied to has now been filled.'),
    ).toBe('rejection');
  });

  it('matches "candidates"/"applicants" interchangeably, not just "candidates" (Turquoise-style)', () => {
    expect(
      classifyEmailText('Update', 'We have decided to move forward with other applicants at this time.'),
    ).toBe('rejection');
  });

  it('matches a comparative rejection with no "other/another" qualifier (ApartmentIQ/Dexcom-style)', () => {
    expect(
      classifyEmailText(
        'Update',
        'We have decided to move forward with candidates whose experience more closely aligns with what we are looking for.',
      ),
    ).toBe('rejection');
    expect(
      classifyEmailText('Update', 'We have chosen to pursue a candidate more closely matched to the role.'),
    ).toBe('rejection');
  });

  it('matches "another candidate has been selected" — passive voice (CivicPlus-style)', () => {
    expect(classifyEmailText('Update', 'After careful consideration, another candidate has been selected.')).toBe(
      'rejection',
    );
  });

  it('matches "will not be moving forward" without requiring "we" immediately before it (Talkiatry-style)', () => {
    expect(
      classifyEmailText('Update', 'As a result, we will not be moving forward with additional candidates.'),
    ).toBe('rejection');
  });

  it('matches location/eligibility rejections with no "candidate" language at all', () => {
    expect(
      classifyEmailText('Update', 'You are outside of the states where we are approved to hire for this role.'),
    ).toBe('rejection');
    expect(classifyEmailText('Update', 'This position is not available in your current location.')).toBe(
      'rejection',
    );
  });

  it('matches a negated-fit rejection (ConnectWise-style) without misfiring on positive fit language', () => {
    expect(
      classifyEmailText('Update', 'Your application does not match the requirements we are looking for.'),
    ).toBe('rejection');
  });

  it('does not fire on the same "if not selected" disclaimer a plain confirmation uses', () => {
    const confirmation =
      "Thank you for applying. We'll review your background, and if you're not selected for this position, we encourage you to check our careers page.";
    expect(classifyEmailText('Thank you for applying', confirmation)).toBe('confirmation');
  });
});

describe('classifyEmailText — interview', () => {
  it('matches an actionable scheduling invite (Archy/Hudu-style)', () => {
    expect(
      classifyEmailText('Next round interview', 'Please book a time for an intro call with us here: [link]'),
    ).toBe('interview');
    expect(
      classifyEmailText('Update', 'Please use this link to schedule a time that works best for you.'),
    ).toBe('interview');
  });

  it('matches "invite you to a phone interview"', () => {
    expect(classifyEmailText('Update', "We'd like to invite you to a phone interview.")).toBe('interview');
  });

  it('matches a dedicated interview-scheduling link even with no keyword nearby', () => {
    expect(classifyEmailText('Your interview', 'Please use this link: https://goodtime.io/intro/abc123')).toBe(
      'interview',
    );
  });

  it('matches "Interview Confirmation" only as a subject line, not inside body boilerplate', () => {
    expect(classifyEmailText('Archy Interview Confirmation', 'Your interview has been scheduled.')).toBe(
      'interview',
    );
    // Real trap found in the audit: a recording-consent policy clause referencing the concept in passing
    // inside an otherwise plain application confirmation (HubSpot-style) must NOT fire as an interview.
    expect(
      classifyEmailText(
        'Thank you for applying!',
        "We've received your application. If you prefer not to have interviews recorded, you may opt-out via the link in your interview confirmation emails, or by informing your recruiter once the interview has been scheduled.",
      ),
    ).toBe('confirmation');
  });

  it('does NOT fire on a plain confirmation\'s forward-looking "we will reach out to schedule" disclaimer', () => {
    expect(
      classifyEmailText(
        'Thank you for applying!',
        "Thank you for your application. If your background is a match, we'll reach out to schedule an interview.",
      ),
    ).toBe('confirmation');
    expect(
      classifyEmailText(
        'Thank you for your application',
        'We are planning to schedule interviews over the next few weeks. If you are among the qualified candidates, you will receive an email from a recruiter to schedule an interview.',
      ),
    ).toBe('confirmation');
  });

  it('still wins as rejection when a post-interview rejection mentions the earlier conversation', () => {
    expect(
      classifyEmailText(
        'Update',
        'Thank you for taking the time to speak with us. After careful consideration, we have decided to move forward with another candidate.',
      ),
    ).toBe('rejection');
  });
});

describe('classifyEmailText — confirmation', () => {
  it('matches the original literal-phrase templates (unchanged from CR-072)', () => {
    expect(classifyEmailText('Thank you for applying!', 'We appreciate your interest.')).toBe('confirmation');
  });

  it('matches "our team"/"we" received your application interchangeably (CivicPlus-style)', () => {
    expect(classifyEmailText('Update', 'Our team has received your application and will be in touch.')).toBe(
      'confirmation',
    );
    expect(classifyEmailText('Update', 'We received your job application for this role.')).toBe('confirmation');
  });
});

describe('classifyEmailText — low confidence', () => {
  it('returns null (not "confirmation") for a message with no unconditional match', () => {
    // Deliberately not force-matched (see CR-105 design doc) — the free layer should stay conservative
    // and hand ambiguous phrasing to the model fallback rather than guess.
    expect(classifyEmailText('Update on your search', 'Following up on where things stand.')).toBeNull();
  });
});

describe('classifyEmailWithLLM', () => {
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

  it('returns null (not a network call) when no Groq key is configured', async () => {
    mockSettingsRow({});
    const result = await classifyEmailWithLLM('Subject', 'Body');
    expect(result).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('parses a valid category from the model reply', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    mockGroqReply('rejection');
    expect(await classifyEmailWithLLM('Subject', 'Body')).toBe('rejection');
  });

  it('is case/whitespace tolerant', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    mockGroqReply('  Interview.\n');
    expect(await classifyEmailWithLLM('Subject', 'Body')).toBe('interview');
  });

  it('treats the model\'s "none" as null, not a category', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    mockGroqReply('none');
    expect(await classifyEmailWithLLM('Subject', 'Body')).toBeNull();
  });

  it('treats an unparseable reply as null rather than throwing', async () => {
    mockSettingsRow({ groqApiKey: 'gsk_x' });
    mockGroqReply('I am not sure, could you clarify?');
    expect(await classifyEmailWithLLM('Subject', 'Body')).toBeNull();
  });

  it('never falls back to Gemini for this task even if no Groq key is set', async () => {
    // The privacy-motivated default (see the function's own doc comment): Gemini's free tier
    // trains on submitted data, Groq's doesn't, so this task must not silently substitute it.
    mockSettingsRow({ geminiApiKey: 'gm_x' }); // Gemini configured, Groq is not
    const result = await classifyEmailWithLLM('Subject', 'Body');
    expect(result).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  function mockGeminiReply(text: string) {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ candidates: [{ content: { parts: [{ text }] } }] }),
    } as any);
  }

  it('only tries Gemini as a fallback once explicitly opted in via taskProviderOverrides', async () => {
    mockSettingsRow({ geminiApiKey: 'gm_x' }); // no groqApiKey, no override yet
    const resultBeforeOptIn = await classifyEmailWithLLM('Subject', 'Body');
    expect(resultBeforeOptIn).toBeNull();
    expect(fetch).not.toHaveBeenCalled();

    mockSettingsRow({ geminiApiKey: 'gm_x', taskProviderOverrides: { email_classification: 'gemini' } });
    mockGeminiReply('interview');
    expect(await classifyEmailWithLLM('Subject', 'Body')).toBe('interview');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('generativelanguage.googleapis.com');
  });

  it('always tries Groq first even when the Gemini fallback is opted in', async () => {
    mockSettingsRow({
      groqApiKey: 'gsk_x',
      geminiApiKey: 'gm_x',
      taskProviderOverrides: { email_classification: 'gemini' },
    });
    mockGroqReply('rejection');
    expect(await classifyEmailWithLLM('Subject', 'Body')).toBe('rejection');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(vi.mocked(fetch).mock.calls[0][0]).toContain('groq.com');
  });
});
