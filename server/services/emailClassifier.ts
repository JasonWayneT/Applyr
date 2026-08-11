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
  // Added 2026-08-10 after a real-mailbox sweep found these exact templates going unmatched (see
  // CHANGELOG) — each pulled verbatim from a real rejection that was Gmail-labeled Applyr/Rejected but
  // fell through this classifier as null.
  'position has now been filled',
  'this position has been filled',
  'tough decision to not move forward',
  "aren't able to move forward in the process",
  'decided to move forward with candidates who more closely align',
  'decided to move forward with another candidate',
  'will not be progressing forward with your application',
  'focusing our search on other candidates',
  'will not move you forward in the hiring process',
  'have not been selected for the position',
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

// Added 2026-08-10 (real-mailbox sweep, see CHANGELOG). Two things were silently defeating every phrase
// in the lists above on real mail:
//   1. Typographic quotes — "we've decided" in REJECTION_PHRASES uses a straight apostrophe, but real
//      email clients/ATS templates render a curly one (U+2019). Byte-exact .includes() never matched.
//   2. Hard-wrapped plain text — a phrase can straddle a line's wrap point ("...decided to move\nforward
//      with other candidates..."), so the literal newline breaks what would otherwise be a normal-space
//      match. Confirmed against a real ARInsights rejection.
// Normalizing curly quotes to straight ones and collapsing all whitespace (including newlines) to single
// spaces before matching fixes both without touching the phrase lists themselves.
function normalizeForMatching(text: string): string {
  return text
    .replace(/[‘’‛]/g, "'")
    .replace(/[“”‟]/g, '"')
    .replace(/\s+/g, ' ');
}

/** Rejection is checked first — a message can't be both, and rejection auto-writes a real status
 *  transition while confirmation only logs, so on the (rare, likely nonexistent) chance both phrase sets
 *  somehow matched the same message, treating it as a rejection is the safer default. */
export function classifyEmailText(subject: string, bodyText: string): EmailCategory | null {
  const combined = normalizeForMatching(`${subject}\n${bodyText}`).toLowerCase();
  if (containsUnconditionalPhrase(combined, REJECTION_PHRASES)) return 'rejection';
  if (containsAny(combined, CONFIRMATION_PHRASES)) return 'confirmation';
  return null;
}

function decodeBase64Url(data: string): string {
  return Buffer.from(data.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf-8');
}

/** Walks a Gmail message's MIME parts for the first body matching the given mimeType. */
function findBodyByMimeType(
  part: gmail_v1.Schema$MessagePart | undefined,
  mimeType: string,
): string | null {
  if (!part) return null;
  if (part.mimeType === mimeType && part.body?.data) {
    return decodeBase64Url(part.body.data);
  }
  for (const child of part.parts ?? []) {
    const found = findBodyByMimeType(child, mimeType);
    if (found) return found;
  }
  return null;
}

const HTML_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  '#39': "'",
  nbsp: ' ',
  rsquo: '’',
  lsquo: '‘',
  rdquo: '”',
  ldquo: '“',
  mdash: '—',
  ndash: '–',
};

function decodeHtmlEntities(text: string): string {
  return text.replace(/&(#\d+|#x[0-9a-f]+|[a-z]+\d*);/gi, (match, code: string) => {
    if (code[0] === '#') {
      const codePoint =
        code[1]?.toLowerCase() === 'x' ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
      return Number.isFinite(codePoint) ? String.fromCodePoint(codePoint) : match;
    }
    return HTML_ENTITIES[code.toLowerCase()] ?? match;
  });
}

// Added 2026-08-10 (real-mailbox sweep, see CHANGELOG) — a real-mailbox sweep found several ATS senders
// (Workday, iCIMS-derived templates, etc.) send HTML-only bodies with no text/plain MIME part at all.
// Without this, extractSubjectAndBody fell straight through to Gmail's `snippet` field, which is only
// ~200 chars of opening boilerplate — it never reaches the actual decision sentence, so every one of
// these was an unconditional miss regardless of phrase-list coverage. Deliberately not a real HTML
// renderer — just enough tag-stripping to get plain, matchable text out of a rejection template.
function htmlToText(html: string): string {
  const withoutNonContent = html.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, ' ');
  const withBreaks = withoutNonContent.replace(
    /<\/(p|div|tr|li|h[1-6]|br)\s*\/?>|<br\s*\/?>/gi,
    '\n',
  );
  const withoutTags = withBreaks.replace(/<[^>]+>/g, ' ');
  return decodeHtmlEntities(withoutTags);
}

export function extractSubjectAndBody(message: gmail_v1.Schema$Message): {
  subject: string;
  bodyText: string;
} {
  const subject = message.payload?.headers?.find((h) => h.name === 'Subject')?.value ?? '';
  const plainText = findBodyByMimeType(message.payload ?? undefined, 'text/plain');
  const htmlText = plainText ? null : findBodyByMimeType(message.payload ?? undefined, 'text/html');
  const bodyText = plainText ?? (htmlText ? htmlToText(htmlText) : null) ?? message.snippet ?? '';
  return { subject, bodyText };
}
