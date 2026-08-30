// CR-106 — extracts a real interview date/time from a Gmail interview-invite email so
// gmailSyncOrchestrator.ts can auto-advance the job's status via shared/domain/jobPipeline.ts's
// deriveStatusForInterviewDateChange, the same way it already auto-closes a job on a detected
// rejection (server/services/jobStatusService.ts). CR-105's own real-mailbox audit found real
// invites consistently state an explicit date/time ("Friday, August 14, 2026 - 12:00 PM (PDT)"),
// so a cheap regex layer handles the common cases for free; an LLM fallback (Groq first, same
// privacy reasoning as classifyEmailWithLLM in emailClassifier.ts — see that file's own comment)
// only runs for the minority of invites the pattern layer can't parse. Returns null rather than
// guessing at a date — gmailSyncOrchestrator.ts falls back to log-only detection, exactly as
// before this existed, whenever this returns null.
import { resolveTaskProviders } from './llmSettings.js';
import { callGroq } from './groqClient.js';
import { callGemini } from './geminiClient.js';
import { isValidInterviewDateTime } from '../../shared/domain/jobPipeline.js';

export interface ExtractedInterviewDateTime {
  isoDateTime: string;
  method: 'pattern' | 'llm';
}

const MONTHS = 'January|February|March|April|May|June|July|August|September|October|November|December';

// "Friday, August 14, 2026 - 12:00 PM (PDT)" / "August 14, 2026 at 12:00 PM" / "Aug 14, 2026, 12:00pm".
// Deliberately stops at the time, before any trailing "(PDT)"-style zone abbreviation — Date.parse
// doesn't reliably resolve those, so a match here is treated as a local-time best guess (see
// extractByPattern's comment). Good enough for a status auto-advance; still correctable by hand.
const EXPLICIT_DATETIME_RE = new RegExp(
  `(?:${MONTHS})\\.?\\s+\\d{1,2},?\\s+\\d{4}[^\\d]{0,15}?\\d{1,2}:\\d{2}\\s*[AaPp]\\.?[Mm]\\.?`,
  'g',
);

// ISO-ish: "2026-08-14 12:00" / "2026-08-14T12:00:00" — some ATS calendar-invite templates use this.
const ISO_DATETIME_RE = /\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}(:\d{2})?/g;

/** Date.parse is stricter than it looks — it rejects "August 14, 2026 - 12:00 PM" and
 *  "August 14, 2026 at 12:00 PM" outright (confirmed empirically, not documented behavior),
 *  even though both are exactly the shape real invites use. Retry with the date-time
 *  connector ("-", "at", "@") stripped before giving up. */
function tryParse(candidate: string): string | null {
  const direct = Date.parse(candidate);
  if (Number.isFinite(direct)) return new Date(direct).toISOString();

  const normalized = candidate.replace(/\s*(?:at|@|-)\s*(?=\d{1,2}:\d{2})/i, ' ');
  const retried = Date.parse(normalized);
  return Number.isFinite(retried) ? new Date(retried).toISOString() : null;
}

/** Regex-only layer — zero cost, tried first. Real timezone precision is out of scope (see the
 *  regex comment above); this is a best-effort local-time parse, not authoritative to the minute. */
function extractByPattern(text: string): string | null {
  for (const re of [EXPLICIT_DATETIME_RE, ISO_DATETIME_RE]) {
    const matches = text.match(re);
    if (!matches) continue;
    for (const match of matches) {
      const iso = tryParse(match);
      if (iso) return iso;
    }
  }
  return null;
}

const EXTRACTION_SYSTEM_PROMPT =
  'You extract the interview date and time from a job-application email. Reply with ONLY the date ' +
  'and time in ISO 8601 format (e.g. 2026-08-14T12:00:00-07:00, or 2026-08-14T12:00:00 if no ' +
  'timezone is stated). If the email does not state one specific date AND time for an interview, ' +
  'reply with exactly: NONE';

function parseLlmDate(text: string | null): string | null {
  if (!text) return null;
  const trimmed = text.trim();
  if (!trimmed || trimmed.toUpperCase() === 'NONE') return null;
  return tryParse(trimmed);
}

/** LLM fallback, same opt-in-Gemini shape as classifyEmailWithLLM (emailClassifier.ts) — this
 *  task also sees real email content, so it gets the identical privacy-first default: Groq only,
 *  unless taskProviderOverrides.interview_date_extraction is explicitly set to 'gemini'. */
async function extractByLLM(subject: string, bodyText: string): Promise<string | null> {
  const providers = resolveTaskProviders('interview_date_extraction', ['groq']);
  const geminiFallbackEnabled = providers.includes('gemini');
  const userPrompt = `Subject: ${subject}\n\nBody:\n${bodyText.slice(0, 4000)}`;

  const groqResult = await callGroq(EXTRACTION_SYSTEM_PROMPT, userPrompt, { temperature: 0 });
  const groqDate = parseLlmDate(groqResult.text);
  if (groqDate) return groqDate;

  if (!geminiFallbackEnabled) return null;

  const geminiResult = await callGemini(EXTRACTION_SYSTEM_PROMPT, userPrompt, { temperature: 0 });
  return parseLlmDate(geminiResult.text);
}

/** Subject is checked too — some ATS interview-invite templates put the date/time in the subject
 *  line alone (e.g. "Interview scheduled: Fri Aug 14 12:00 PM"). */
export async function extractInterviewDateTime(
  subject: string,
  bodyText: string,
): Promise<ExtractedInterviewDateTime | null> {
  const combined = `${subject}\n${bodyText}`;

  const patternMatch = extractByPattern(combined);
  if (patternMatch && isValidInterviewDateTime(patternMatch)) {
    return { isoDateTime: patternMatch, method: 'pattern' };
  }

  const llmMatch = await extractByLLM(subject, bodyText);
  if (llmMatch && isValidInterviewDateTime(llmMatch)) {
    return { isoDateTime: llmMatch, method: 'llm' };
  }

  return null;
}
