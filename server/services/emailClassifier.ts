// CR-072 Story 2.2 — rule-based classifier. Deliberately keyword-only, no LLM call (see CR-072's Decision
// section: an LLM step would need to run locally to respect the no-metered-API constraint, and is
// explicitly deferred to a future CR once this rule-based path's real hit/miss rate is known).
//
// The two phrase sets below are lifted directly from gmail_job_search_intake_filter.md's own
// "Application Acknowledgments" and "Application Updates and Rejections" groups — the same phrases that
// already gate the Applyr/Incoming Gmail filter. Deliberately excludes that doc's broader/ambiguous
// phrases (e.g. "regarding your application", "your candidacy") and its interview-related group — a
// message that only matches those falls through to no classification, which is correct: CR-072 leaves
// interview/recruiter/uncertain mail for Jason to handle through his normal inbox use.
import type { gmail_v1 } from 'googleapis';

export type EmailCategory = 'rejection' | 'confirmation';

const REJECTION_PHRASES = [
  'we have decided not to move forward',
  "we've decided not to move forward",
  'we will not be moving forward',
  'we are not moving forward',
  'will not be proceeding with your application',
  'moving forward with other candidates',
  'move forward with other candidates',
  'pursue other candidates',
  'selected another candidate',
  'selected other candidates',
  'not selected for the position',
  'not selected for this position',
  'not selected to move forward',
  'unable to move forward with your application',
];

const CONFIRMATION_PHRASES = [
  'thank you for applying',
  'thanks for applying',
  'thank you for your application',
  'we received your application',
  'we have received your application',
  'your application has been received',
  'application confirmation',
];

// Found empirically (2026-08-03, CR-072 Story 2.6 dry run against Jason's real inbox): confirmation
// emails routinely include forward-looking disclaimer boilerplate — "If you're not selected for this
// position, keep an eye on our jobs page" — that contains a rejection phrase verbatim despite the email
// being a plain application confirmation. Real examples caught: iSpot, Muck Rack. This isn't isolated to
// one phrase — "moving forward with other candidates," "selected another candidate," etc. are all
// plausible inside the same "if we decide to..." disclaimer shape. A rejection match is only trusted if
// it isn't immediately preceded by "if" within a short window; on the rare chance this also swallows a
// genuine rejection phrased unusually, that's an accepted false negative — this pipeline's dry-run
// design already treats "missed" as far cheaper than "wrongly flagged," so the bias is deliberate.
const CONDITIONAL_LOOKBEHIND_CHARS = 40;

function containsAny(haystackLower: string, phrases: string[]): boolean {
  return phrases.some((p) => haystackLower.includes(p));
}

function containsUnconditionalPhrase(haystackLower: string, phrases: string[]): boolean {
  return phrases.some((phrase) => {
    let idx = haystackLower.indexOf(phrase);
    while (idx !== -1) {
      const windowStart = Math.max(0, idx - CONDITIONAL_LOOKBEHIND_CHARS);
      const preceding = haystackLower.slice(windowStart, idx);
      if (!/\bif\b/.test(preceding)) return true;
      idx = haystackLower.indexOf(phrase, idx + 1);
    }
    return false;
  });
}

/** Rejection is checked first — a message can't be both, and rejection auto-writes a real status
 *  transition while confirmation only logs, so on the (rare, likely nonexistent) chance both phrase sets
 *  somehow matched the same message, treating it as a rejection is the safer default. */
export function classifyEmailText(subject: string, bodyText: string): EmailCategory | null {
  const combined = `${subject}\n${bodyText}`.toLowerCase();
  if (containsUnconditionalPhrase(combined, REJECTION_PHRASES)) return 'rejection';
  if (containsAny(combined, CONFIRMATION_PHRASES)) return 'confirmation';
  return null;
}

function decodeBase64Url(data: string): string {
  return Buffer.from(data.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf-8');
}

/** Walks a Gmail message's MIME parts for the first text/plain body. Falls back to the API's own
 *  `snippet` (always present, short) if no text/plain part is found — good enough for keyword matching,
 *  since these phrases are short and appear early in auto-generated ATS emails. */
function findPlainTextBody(part: gmail_v1.Schema$MessagePart | undefined): string | null {
  if (!part) return null;
  if (part.mimeType === 'text/plain' && part.body?.data) {
    return decodeBase64Url(part.body.data);
  }
  for (const child of part.parts ?? []) {
    const found = findPlainTextBody(child);
    if (found) return found;
  }
  return null;
}

export function extractSubjectAndBody(message: gmail_v1.Schema$Message): {
  subject: string;
  bodyText: string;
} {
  const subject = message.payload?.headers?.find((h) => h.name === 'Subject')?.value ?? '';
  const bodyText = findPlainTextBody(message.payload ?? undefined) ?? message.snippet ?? '';
  return { subject, bodyText };
}
