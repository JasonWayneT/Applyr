// CR-072 Story 2.3 — layered job-matching pipeline per the spec's resolved OQ-1: an incoming email has no
// Applyr job id, so this tries the highest-confidence signal first and only falls back to fuzzy text
// matching when nothing more reliable resolves it. Any stage returning more than one candidate is treated
// as ambiguous, not resolved by picking one — a wrong auto-write on the wrong job is worse than a missed
// one, and CR-072's design leans on "no match -> skip silently" throughout.
import Fuse from 'fuse.js';

export interface MatchableJob {
  id: string;
  company: string;
  url: string | null;
}

export interface JobMatchResult {
  jobId: string;
  method: 'domain' | 'normalized-exact' | 'fuzzy';
}

const LEGAL_SUFFIXES = /\b(inc|llc|ltd|corp|co|company|group)\b\.?/g;

function normalizeCompanyName(text: string): string {
  return text
    .toLowerCase()
    .replace(LEGAL_SUFFIXES, ' ')
    .replace(/[^\w\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function extractUrlDomain(url: string | null): string | null {
  if (!url) return null;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return hostname.startsWith('www.') ? hostname.slice(4) : hostname;
  } catch {
    return null;
  }
}

function extractSenderDomain(fromHeader: string | null): string | null {
  if (!fromHeader) return null;
  const match = fromHeader.match(/@([\w.-]+\.[a-z]{2,})/i);
  return match ? match[1].toLowerCase() : null;
}

export interface EmailMatchInput {
  fromHeader: string | null;
  subject: string;
  bodyText: string;
}

export function matchJobForEmail(jobs: MatchableJob[], input: EmailMatchInput): JobMatchResult | null {
  // Stage 1: sender-domain match against the job's own posting URL domain. Exact hostname equality only
  // — deliberately not a subdomain/suffix match, since shared-ATS hosts (boards.greenhouse.io,
  // jobs.lever.co) would make every company on that ATS collide on the same suffix.
  const senderDomain = extractSenderDomain(input.fromHeader);
  if (senderDomain) {
    const domainMatches = jobs.filter((j) => extractUrlDomain(j.url) === senderDomain);
    if (domainMatches.length === 1) {
      return { jobId: domainMatches[0].id, method: 'domain' };
    }
  }

  // Stage 2: normalized exact match — does a tracked company's (suffix-stripped, punctuation-stripped)
  // name appear as a whole-word match in the normalized subject+body? Most real ATS mail states the
  // company name plainly ("Your application to Acme"), so this resolves the bulk of what stage 1 doesn't.
  //
  // Two guards here, both found necessary empirically (2026-08-03, CR-072 Story 2.6 dry run against
  // Jason's actual inbox — not hypothetical, both caused confirmed real false matches):
  // 1. MIN_NORMALIZED_LENGTH: "V Group Inc." strips both "Group" and "Inc" as legal-suffix words,
  //    normalizing to just "v" — matched a "Revinate" confirmation and an unrelated "Product Manager"
  //    subject line via plain substring matching.
  // 2. Word-boundary matching, not plain substring: even at length 5, "Verse" (a real tracked company)
  //    matched a Muck Rack confirmation email purely because its DEI boilerplate paragraph contained the
  //    word "diverse" — "verse" is a substring of "diverse" with no boundary check. A length floor alone
  //    doesn't fix this class of bug; only requiring the match to be a whole word (or phrase) does.
  const MIN_NORMALIZED_LENGTH = 4;
  const combinedText = normalizeCompanyName(`${input.subject} ${input.bodyText}`);
  const exactMatches = jobs.filter((j) => {
    const normCompany = normalizeCompanyName(j.company);
    if (normCompany.length < MIN_NORMALIZED_LENGTH) return false;
    return new RegExp(`\\b${escapeRegex(normCompany)}\\b`).test(combinedText);
  });
  if (exactMatches.length === 1) {
    return { jobId: exactMatches[0].id, method: 'normalized-exact' };
  }

  // Stage 3: fuzzy fallback for near-misses (abbreviations, minor spelling/punctuation drift). Strict
  // threshold and a required gap to the second-best candidate — a near-tie between two tracked companies
  // is treated as no match, not a coin flip. Threshold/gap are first-pass values; CR-072's epics tracker
  // already flags these as needing empirical tuning against real synced mail, not a guarantee as-is.
  const fuse = new Fuse(jobs, { keys: ['company'], includeScore: true, threshold: 0.3 });
  const results = fuse.search(input.subject);
  if (results.length > 0) {
    const best = results[0];
    const second = results[1];
    const bestScore = best.score ?? 1;
    const secondScore = second?.score ?? 1;
    if (bestScore <= 0.3 && secondScore - bestScore > 0.15) {
      return { jobId: best.item.id, method: 'fuzzy' };
    }
  }

  return null;
}
