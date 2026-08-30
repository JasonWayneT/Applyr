// CR-072 Story 2.2, reworked under CR-105 (2026-08-30) — hybrid classifier. Free/local pattern layer
// first; a low-confidence email (no unconditional pattern hit) is meant to fall through to a real model
// call (Groq free tier — see CR-105's design doc) rather than get silently dropped or guessed at. This
// file only owns the free layer's confidence bar: return a category when sure, `null` when not.
//
// CR-105 replaced the original literal-phrase-only design after a 315-message real-mailbox audit (see
// SESSION-HANDOFF-2026-08-30-email-classifier-audit.md) found literal-string matching structurally can't
// keep up with real-world template variation: every ATS phrases "you didn't get it" differently
// ("chosen to pursue a candidate" vs. "decided to move forward with another candidate" vs. "we have
// filled the position" (active) vs. "position has been filled" (passive) vs. "candidates" vs.
// "applicants"...). The fix is small vocabulary-of-synonyms regexes instead of a single exact string per
// pattern, so one rule generalizes to wording it has never literally seen. The literal phrase lists are
// kept as an extra fast/cheap layer underneath the regexes, not because they generalize (they don't) but
// because exact matches are effectively free and zero-risk.
//
// The original literal phrase lists below are lifted from gmail_job_search_intake_filter.md's own
// "Application Acknowledgments" and "Application Updates and Rejections" groups (the same phrases that
// gate the Applyr/Incoming Gmail filter), plus phrases added in a 2026-08-10 real-mailbox sweep.
import type { gmail_v1 } from 'googleapis';
import { resolveTaskProviders } from './llmSettings.js';
import { callGroq } from './groqClient.js';
import { callGemini } from './geminiClient.js';

export type EmailCategory = 'rejection' | 'interview' | 'confirmation';

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

// CR-105: vocabulary-of-synonyms regexes, built from real misses a literal phrase list couldn't cover.
// Each one is commented with the real (paraphrased) example that motivated it. Kept deliberately narrow
// to decision-shaped language — broad enough to generalize past the one example, not so broad it risks
// firing on a plain confirmation's forward-looking disclaimer (that risk is what CONDITIONAL_LOOKBEHIND
// below guards against for every pattern in this file, phrase or regex).
const REJECTION_PATTERNS: RegExp[] = [
  // "decided/chosen/opted to move forward/proceed/pursue with {other/another} {candidate(s)/applicant(s)}"
  // Real: "we've opted to proceed with other candidates" / "chosen to pursue a candidate...more closely
  // matched" / "decided to move forward with other applicants" (Turquoise, Certara — "applicants" wasn't
  // in the old candidate-only list).
  /\b(decided|chosen|opted|choosing)\b[\s\S]{0,50}\b(move forward|moving forward|proceed|proceeding|pursue|pursuing)\b[\s\S]{0,40}\b(another|other)\b[\s\S]{0,15}\b(candidate|candidates|applicant|applicants)\b/,
  // Same decision-verb shape but with no "other/another" qualifier at all — instead a comparative clause
  // ranking Jason against unnamed others ("more closely align(s)", "better suited", "more closely
  // matched"). Real: ApartmentIQ "decided to move forward with candidates whose experience more closely
  // aligns with what we are looking for"; Dexcom (x2) "chosen to pursue a candidate...more closely
  // matched to the position". Comparative language is the signal here, not "other/another".
  /\b(decided|chosen|opted|choosing)\b[\s\S]{0,50}\b(move forward|moving forward|proceed|proceeding|pursue|pursuing)\b[\s\S]{0,60}\bcandidates?\b[\s\S]{0,50}\b(more closely aligns?|closely matched|better suited|better meets?|better aligned)\b/,
  // "another/other candidate(s) has/have been selected" — passive voice of the old "selected another
  // candidate" phrase. Real (CivicPlus): "another candidate has been selected."
  /\b(another|other) candidates? (has|have) been selected\b/,
  // "{the/this} position/role {has (now/recently) been/is now} filled/closed" — passive voice. Widened
  // gap after "position/role" to 40 chars: PointClickCare said "the position you have applied to has now
  // been filled" — the relative clause "you have applied to" pushed past the old 15-char gap.
  // Real: "the position has now been filled", "this position has been filled with another candidate".
  /\b(the |this )?(position|role|opening)\b[\s\S]{0,40}\b(has (now |recently )?been|is now)\b[\s\S]{0,10}\b(filled|closed)\b/,
  // "we have/'ve filled {the/this} position/role" — active voice (Pax8: old list only had passive).
  /\bwe('ve| have)\b[\s\S]{0,10}\bfilled\b[\s\S]{0,15}\b(the |this )?(position|role|opening)\b/,
  // "they've/have closed the position" — active voice of "closing the position" below, past tense. Real
  // (personal recruiter update, not an ATS template): "they've closed the position, so that introduction
  // won't be going ahead."
  /\b(they've|they have|has|have) closed (the|this) (position|role|opening)\b/,
  // "{have/has} not (been) selected ... {position/role/to move forward}" — old list required the exact
  // words "for the position"/"for this position"; McKesson said "you have not been selected for this
  // position" (extra "been" broke the old substring match entirely).
  /\b(have|has|haven't|hasn't)\b[\s\S]{0,10}\b(not\b[\s\S]{0,10})?selected\b[\s\S]{0,30}\b(position|role|move forward)\b/,
  // "will not be moving forward/progressing/proceeding" without requiring "we" immediately before it —
  // Talkiatry said "...and will not be moving forward with additional candidates," where "we" was several
  // words earlier, so the old exact phrase "we will not be moving forward" never matched.
  /\bwill not be (moving forward|progressing|proceeding)\b/,
  // "won't/will not be progressing/proceeding with your application" — Infor said "won't be progressing
  // with your application on this occasion" (old list only had "progressing forward").
  /\b(won't|will not) be (progressing|proceeding) with your application\b/,
  // "unable/not able/won't be able to invite you to the next stage/step/round" — RB Global said "won't be
  // able to invite you to the next stage" (old draft only covered "unable"/"not able").
  /\b(unable|not able|won't be able|will not be able) to invite you\b[\s\S]{0,30}\bnext (stage|step|round)\b/,
  // "unable/not able/aren't able to consider (additional/further) applications" — a rejection shape with
  // no "candidate"/"position" language at all. Real (Advantage Solutions via firstadvantage@myworkday):
  // "the hiring process for this role is already well underway, we aren't able to consider additional
  // applications at this time."
  /\b(unable|not able|aren't able|are not able) to consider (additional |further )?applications?\b/,
  // "unable to connect with you before the position closed" — ICW Group. Narrowed with a required
  // "position" nearby so this doesn't fire on an unrelated "couldn't reach you" scheduling note.
  /\bunable to connect with you\b[\s\S]{0,60}\bposition\b/,
  // "closing your application / closing the position" — Amplify, Omni.
  /\bclosing (your application|the position|this (position|role|opening))\b/,
  // "extended an offer to {a/another} candidate" (so the interview gets canceled) — distinct rejection
  // shape with no "not selected" language at all.
  /\bextended an offer to (a |another )?candidate\b/,
  // "chosen not to move forward with your candidacy" — "candidacy" wasn't covered by the old
  // "with your application" ending.
  /\bnot to move forward with your candidacy\b/,
  // "we do not have {an appropriate/a suitable} position for you" — Ziff Davis. A distinct passive-decline
  // shape (no "other candidate" or "filled" language at all).
  /\bdo not have (an |a )?(appropriate |suitable )?position for you\b/,
  // "{does/did} not match the {expectations/requirements/qualifications} {we/they} {are/were} looking
  // for" — ConnectWise. The explicit negation ("does not match") is what keeps this safe to generalize:
  // the same "matches what we're looking for" language shows up in genuinely positive contexts (e.g. an
  // interview invite), but never negated like this.
  /\b(does not|did not|didn't) match\b[\s\S]{0,30}\b(expectations|requirements|qualifications)\b[\s\S]{0,20}\b(are|were) looking for\b/,
  // Location/eligibility rejections — a distinct rejection shape (no "other candidate" language at all).
  // Real: Marigold ("outside of the states where we are approved to hire"), Clearlink ("this position is
  // not available in your current location").
  /\boutside (of )?the (states?|locations?|areas?) where we (are|'re) approved to hire\b/,
  /\bposition is not available in your (current )?location\b/,
];

// CR-105: this category didn't exist before — 0/7 real interview invites were detected. Patterns below
// are built from every real interview email in the audit (Archy, Relativity, Hudu, PracticeTek,
// AbacusNext). Checked only after the rejection patterns above find nothing unconditional, since a
// post-interview rejection ("thank you for speaking with us... decided to move forward with another
// candidate") should still win as a rejection, not get caught by leftover interview-adjacent wording.
//
// A first pass matching "schedule/book + {time/call/interview}" bluntly turned out to fire constantly on
// plain application confirmations — nearly every ATS template includes a forward-looking disclaimer in
// this exact shape ("if you're a fit, a recruiter will reach out to schedule an interview" / "we are
// planning to schedule interviews over the next few weeks"). That's a *promise about the future*, not an
// actual invite — real invites are imperative/actionable now ("please book a time...", "use this link to
// schedule..."). FUTURE_PROMISE_WORDS below blocks a match sitting right after that framing, the same way
// CONDITIONAL_LOOKBEHIND blocks one sitting right after "if".
const INTERVIEW_PATTERNS: RegExp[] = [
  /\binterview (has been |is )?scheduled\b/,
  // "book/schedule {a time/a call/an interview}" — Archy, Hudu, AbacusNext all use some form of this.
  /\b(book|schedule)\b[\s\S]{0,20}\b(a |an )?(time|call|interview|meeting|conversation)\b/,
  // "invite you to a {phone/video/in-person} interview" / "next round/stage interview".
  /\binvite you to (a |an )?(phone |video |in-person )?interview\b/,
  /\bnext (round|stage) interview\b/,
  // Dedicated interview-scheduling platforms — essentially never linked for any purpose other than
  // booking an interview. Generic ATS confirmation links (a plain "view your application" link) don't
  // match this; these are booking-flow URLs specifically.
  /\b(goodtime\.io|meetme\.so|ashbyhq\.com\/meeting)\b/,
];

const FUTURE_PROMISE_LOOKBEHIND_CHARS = 60;
const FUTURE_PROMISE_WORDS =
  /\b(reach out|contact you|will receive|planning to|will be reaching out|will be contacting|once the|once your)\b/;

// "Interview confirmation" as a bare phrase is too generic to trust anywhere in a body — real senders
// also use it inside unrelated policy boilerplate (e.g. a recording-consent clause: "...opt-out link
// provided in your interview confirmation emails..." — HubSpot, a plain application confirmation, not an
// interview at all). The one real example of this in the audit (Archy) used it as the email's own
// subject line, which is a much more reliable signal: a sender describing what *this* email is, not
// referencing the concept in passing. Checked separately from the body-wide INTERVIEW_PATTERNS above.
const INTERVIEW_SUBJECT_PATTERNS: RegExp[] = [/\binterview confirmation\b/];

const CONFIRMATION_PHRASES = [
  'thank you for applying',
  'thanks for applying',
  'thank you for your application',
  'we received your application',
  'we have received your application',
  'your application has been received',
  'application confirmation',
];

// CR-105: same literal-phrase rigidity problem as rejection — "our team has received your application"
// (CivicPlus, subject swap: "our team" not "we") and "we received your job application" (RB Global, an
// extra word breaking the substring) both slipped past the phrase list above.
const CONFIRMATION_PATTERNS: RegExp[] = [
  /\b(we|our team) (have |has )?received your( job| recent)? application\b/,
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
// CR-105: this guard now applies uniformly to literal phrases AND regex patterns, and to all three
// categories, not just rejection — the same disclaimer shape can just as easily wrap interview language
// ("if you're invited to interview, we'll reach out to schedule").
const CONDITIONAL_LOOKBEHIND_CHARS = 40;

function containsAny(haystackLower: string, phrases: string[]): boolean {
  return phrases.some((p) => haystackLower.includes(p));
}

/** True if `phrase` (literal string) appears in `haystackLower` at least once outside a short
 *  "if ..." lookbehind window (see CONDITIONAL_LOOKBEHIND_CHARS above). */
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

/** Same conditional-lookbehind guard as containsUnconditionalPhrase, generalized to regex patterns.
 *  `extraGuard`, when given, blocks a match the same way if it also sits right after the extra pattern
 *  (used for interview's FUTURE_PROMISE_WORDS — see comment above INTERVIEW_PATTERNS). */
function matchesUnconditionalPattern(
  haystackLower: string,
  patterns: RegExp[],
  extraGuard?: { pattern: RegExp; lookbehindChars: number },
): boolean {
  return patterns.some((pattern) => {
    const global = new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : pattern.flags + 'g');
    let m: RegExpExecArray | null;
    while ((m = global.exec(haystackLower)) !== null) {
      const windowStart = Math.max(0, m.index - CONDITIONAL_LOOKBEHIND_CHARS);
      const preceding = haystackLower.slice(windowStart, m.index);
      const extraWindowStart = extraGuard ? Math.max(0, m.index - extraGuard.lookbehindChars) : 0;
      const extraPreceding = extraGuard ? haystackLower.slice(extraWindowStart, m.index) : '';
      if (!/\bif\b/.test(preceding) && !(extraGuard && extraGuard.pattern.test(extraPreceding))) {
        return true;
      }
      if (m.index === global.lastIndex) global.lastIndex++; // avoid infinite loop on zero-width match
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
 *  transition while confirmation/interview only log, so on the (rare) chance more than one category's
 *  patterns somehow matched the same message, treating it as a rejection is the safer default: a
 *  post-interview rejection ("thank you for speaking with us... we've decided to move forward with
 *  another candidate") should never get caught by leftover interview-adjacent wording instead.
 *
 *  This is the free/local confidence bar (CR-105): a category means "sure enough to act on with zero
 *  further cost." `null` means low confidence, not "not application mail" — the caller is expected to
 *  route that case to a real model call rather than treat it as nothing. */
export function classifyEmailText(subject: string, bodyText: string): EmailCategory | null {
  const subjectLower = normalizeForMatching(subject).toLowerCase();
  const combined = normalizeForMatching(`${subject}\n${bodyText}`).toLowerCase();
  if (
    containsUnconditionalPhrase(combined, REJECTION_PHRASES) ||
    matchesUnconditionalPattern(combined, REJECTION_PATTERNS)
  ) {
    return 'rejection';
  }
  if (
    INTERVIEW_SUBJECT_PATTERNS.some((p) => p.test(subjectLower)) ||
    matchesUnconditionalPattern(combined, INTERVIEW_PATTERNS, {
      pattern: FUTURE_PROMISE_WORDS,
      lookbehindChars: FUTURE_PROMISE_LOOKBEHIND_CHARS,
    })
  ) {
    return 'interview';
  }
  if (
    containsAny(combined, CONFIRMATION_PHRASES) ||
    matchesUnconditionalPattern(combined, CONFIRMATION_PATTERNS)
  ) {
    return 'confirmation';
  }
  return null;
}

const LLM_CATEGORIES = new Set(['rejection', 'interview', 'confirmation', 'none']);

const CLASSIFICATION_SYSTEM_PROMPT =
  'You classify job-application emails. Reply with exactly one word: rejection, interview, confirmation, or none. ' +
  '"rejection" = the application was declined or the role was filled/closed. ' +
  '"interview" = an actual interview/call is being scheduled or confirmed now (not a vague future promise). ' +
  '"confirmation" = a plain "we received your application" acknowledgment with no decision yet. ' +
  '"none" = anything else (not application-status mail at all, or a decision that does not fit the above).';

function parseClassificationLabel(text: string | null): EmailCategory | null {
  if (!text) return null;
  const label = text.trim().toLowerCase().replace(/[^a-z]/g, '');
  if (!LLM_CATEGORIES.has(label) || label === 'none') return null;
  return label as EmailCategory;
}

/** Low-confidence fallback (CR-105): called only when classifyEmailText above returns null —
 *  a real category means the free pattern layer was already sure, at zero further cost, and
 *  this never runs. 'none' from the model is a genuine "not application-status mail" decision,
 *  same terminal outcome as null (no action taken) but distinct from "couldn't determine."
 *
 *  Groq-first by default, same reasoning as before: this task sees real email content, and
 *  Gemini's free tier trains on submitted data (see docs/ROADMAP_BEST_PRACTICES.md's provider
 *  research) while Groq's doesn't. Gemini is available as an opt-in secondary fallback — set
 *  taskProviderOverrides.email_classification to 'gemini' via Settings > API or Connections >
 *  AI Usage — but even then Groq is always tried first; the override only adds Gemini as a
 *  second attempt when Groq comes back empty, it never promotes Gemini ahead of Groq the way
 *  resolveTaskProviders does for other tasks (e.g. Stage 0). That's deliberate: the privacy
 *  tradeoff this comment describes is why Groq is the default in the first place, so opting in
 *  to Gemini here should never come at the cost of trying Groq less than before.
 */
export async function classifyEmailWithLLM(
  subject: string,
  bodyText: string,
): Promise<EmailCategory | null> {
  const providers = resolveTaskProviders('email_classification', ['groq']);
  const geminiFallbackEnabled = providers.includes('gemini');

  const bodySnippet = bodyText.slice(0, 4000); // enough for the decision sentence, not the whole email
  const userPrompt = `Subject: ${subject}\n\n${bodySnippet}`;

  const groqResult = await callGroq(CLASSIFICATION_SYSTEM_PROMPT, userPrompt, { temperature: 0 });
  const groqLabel = parseClassificationLabel(groqResult.text);
  if (groqLabel) return groqLabel;

  if (!geminiFallbackEnabled) return null;

  const geminiResult = await callGemini(CLASSIFICATION_SYSTEM_PROMPT, userPrompt, { temperature: 0 });
  return parseClassificationLabel(geminiResult.text);
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
