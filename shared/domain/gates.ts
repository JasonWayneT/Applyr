/**
 * Deterministic ingest gates — pure functions, no I/O.
 * Used by scout orchestrator at ingest; tested in tests/unit/gates.test.ts.
 */

export interface ScrapedJob {
  company: string;
  title: string;
  url: string;
  description: string;
  source: string;
  salary_range?: string;
  recruiter_name?: string;
  recruiter_url?: string;
  extraction_confidence?: string;
  data_quality_flags?: string[];
}

export interface GateConfig {
  blockedIndustries: string[];
  titleBlocklist: string[];
  workSetting: string;
  maxExperienceYears: number;
}

export interface TargetRolePrefs {
  targetRole: string;
  searchTerms: string[];
}

const REMOTE_ONLY_SOURCES = new Set([
  'Remotive',
  'RemoteOK',
  'WWR',
  'Himalayas',
  'Jobicy',
  'Working Nomads',
  'JobsCollider',
]);

function industryTermMatches(text: string, term: string): boolean {
  const phrase = term.trim();
  if (!phrase || !text) return false;
  const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`\\b${escaped}\\b`, 'i').test(text);
}

export function titleMatchesBlocked(title: string, term: string): boolean {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`\\b${escaped}\\b`, 'i').test(title);
}

export function parseMaxYearsRequired(text: string): number | null {
  const patterns = [
    /(?:minimum|min\.?|at least|requires?)\s*(\d+)\s*\+?\s*(?:years?|yrs?)/gi,
    /(\d+)\s*\+\s*years?/gi,
    /(\d+)\s*[-–]\s*(\d+)\s*years?/gi,
    /(\d+)\s+years?\s+(?:of\s+)?experience/gi,
  ];
  const found: number[] = [];
  for (const pat of patterns) {
    let m: RegExpExecArray | null;
    const re = new RegExp(pat.source, pat.flags);
    while ((m = re.exec(text)) !== null) {
      const nums = m.slice(1).filter(Boolean).map((g) => parseInt(g, 10));
      if (!nums.length) continue;
      const maxInMatch = nums.length === 1 ? nums[0] : Math.max(...nums);
      if (Number.isFinite(maxInMatch) && maxInMatch > 0 && maxInMatch <= 25) {
        found.push(maxInMatch);
      }
    }
  }
  return found.length ? Math.max(...found) : null;
}

export function passesTitleBlocklist(title: string, config: GateConfig): boolean {
  if (!title) return true;
  return !config.titleBlocklist.some((blocked) => titleMatchesBlocked(title, blocked));
}

/** True when Job Search target_role is PM-family (default for Jason; swappable in prefs). */
export function isProductManagerFamilyTarget(targetRole: string): boolean {
  const r = (targetRole || '').trim().toLowerCase();
  return r.includes('product manager') || r.includes('product owner');
}

/** Preference-driven positive match: title contains a configured search term. */
export function titleMatchesSearchTerm(title: string, term: string): boolean {
  const t = (title || '').trim();
  const q = (term || '').trim();
  if (!t || !q) return false;
  if (q.length <= 4) {
    const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return new RegExp(`\\b${escaped}\\b`, 'i').test(t);
  }
  return t.toLowerCase().includes(q.toLowerCase());
}

export function passesSearchTermsTitleScope(title: string, searchTerms: string[]): boolean {
  if (!searchTerms.length) return true;
  return searchTerms.some((term) => titleMatchesSearchTerm(title, term));
}

const BUILTIN_NON_PM_TITLE_PATTERNS: RegExp[] = [
  /\bproduct marketing\b/i,
  /\bdevops\b/i,
  /\bsoftware engineer\b/i,
  /\bdata engineer\b/i,
  /\bproduct designer\b/i,
  /\bproduct analyst\b/i,
  /\btalent community\b/i,
  /\bsolutions engineer\b/i,
  /\btechnical writer\b/i,
  /\brecruiter\b/i,
];

export function passesBuiltInPmTitleScope(title: string): boolean {
  const t = (title || '').trim();
  if (!t) return false;
  if (!/\bproduct manager\b/i.test(t)) return false;
  if (/\bproduct owner\b/i.test(t) && !/\bproduct manager\b/i.test(t)) return false;
  for (const pat of BUILTIN_NON_PM_TITLE_PATTERNS) {
    if (pat.test(t)) return false;
  }
  return true;
}

const BROAD_NON_PM_TITLE_PATTERNS: RegExp[] = [
  /\bproduct marketing\b/i,
  /\bproduct design/i,
  /\bproduct analyt/i,
  /\bprogram manager\b/i,
  /\bproject manager\b/i,
  /\bsolutions engineer\b/i,
  /\bsales development\b/i,
  /\baccount executive\b/i,
  /\bcustomer success\b/i,
  /\binside sales\b/i,
];

export function passesBroadPmTitleScope(title: string): boolean {
  const t = (title || '').trim();
  if (!t) return false;
  for (const pat of BROAD_NON_PM_TITLE_PATTERNS) {
    if (pat.test(t)) return false;
  }
  return (
    /\bproduct manager\b/i.test(t) ||
    /\bproduct owner\b/i.test(t) ||
    /\b(technical|platform|data|ai|api|integration|enterprise|infrastructure) product\b/i.test(t)
  );
}

/**
 * Single ingest choke point: allow titles matching target_role / search_terms.
 * PM-family targets use broad PM scope; other targets use search_terms only.
 */
export function passesTargetRoleTitleScope(
  title: string,
  prefs: TargetRolePrefs,
  sourceId?: string,
): boolean {
  const t = (title || '').trim();
  if (!t) return false;

  if (sourceId === 'builtin' && isProductManagerFamilyTarget(prefs.targetRole)) {
    return passesBuiltInPmTitleScope(t);
  }

  if (isProductManagerFamilyTarget(prefs.targetRole)) {
    return passesBroadPmTitleScope(t);
  }

  return passesSearchTermsTitleScope(t, prefs.searchTerms);
}

const BUILTIN_HYBRID_OR_ONSITE_CARD =
  /\b(in[-\s]?office\s+or\s+remote|remote\s+or\s+hybrid|hybrid\s+or\s+remote|on[-\s]?site|in[-\s]?office)\b/i;

export function passesBuiltInStrictRemoteCard(cardText: string): boolean {
  const c = (cardText || '').toLowerCase();
  if (!c) return false;
  if (BUILTIN_HYBRID_OR_ONSITE_CARD.test(c)) return false;
  const hasRemote =
    /\bremote\b/.test(c) || /\bwork from home\b/.test(c) || /\banywhere in\b/.test(c);
  const hasSd =
    /\bsan diego\b/.test(c) ||
    /\bcarlsbad\b/.test(c) ||
    /\bla jolla\b/.test(c) ||
    /\bencinitas\b/.test(c) ||
    /\bdel mar\b/.test(c) ||
    /\bsolana beach\b/.test(c);
  return hasRemote || hasSd;
}

export function passesIndustryGate(job: ScrapedJob, config: GateConfig): boolean {
  if (!config.blockedIndustries.length) return true;
  for (const term of config.blockedIndustries) {
    if (industryTermMatches(job.company || '', term)) {
      console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - industry_blocked:${term}`);
      return false;
    }
    if (industryTermMatches(job.title || '', term)) {
      console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - industry_blocked:${term}`);
      return false;
    }
  }
  const desc = (job.description || '').trim();
  if (desc.length > 0 && desc.length <= 120) {
    for (const term of config.blockedIndustries) {
      if (industryTermMatches(desc, term)) {
        console.log(`[REJECT] ${job.title} at ${job.company} (${job.source}) - industry_blocked:${term}`);
        return false;
      }
    }
  }
  return true;
}

export function passesGeographicGate(job: ScrapedJob, config: GateConfig): boolean {
  const text = `${job.title} ${job.description || ''}`.toLowerCase();

  if ((job.description || '').trim().length < 50) {
    if (config.workSetting === 'Remote') {
      if (REMOTE_ONLY_SOURCES.has(job.source)) return true;
      console.log(
        `[REJECT] ${job.title} at ${job.company} (${job.source}) - [GEOGRAPHIC REJECT] remote_only_no_location_signal`,
      );
      return false;
    }
    return true;
  }

  const hasLocalSD =
    text.includes('san diego') ||
    text.includes('carlsbad') ||
    text.includes('la jolla') ||
    text.includes('encinitas') ||
    text.includes('del mar') ||
    text.includes('solana beach') ||
    text.includes('ca');

  const hasRemote =
    text.includes('remote') ||
    text.includes('anywhere in') ||
    text.includes('work from home') ||
    text.includes('telecommute');

  const isExplicitForeign =
    (text.includes('canada') ||
      text.includes('united kingdom') ||
      text.includes('london,') ||
      text.includes('europe') ||
      text.includes('germany') ||
      text.includes('india') ||
      text.includes('apac')) &&
    !(text.includes('united states') || text.includes('within the us') || text.includes('us citizen'));

  if (isExplicitForeign) return false;
  if (hasLocalSD || hasRemote) return true;
  if (REMOTE_ONLY_SOURCES.has(job.source)) return true;
  return false;
}

export function passesSeniorityGate(job: ScrapedJob, config: GateConfig): boolean {
  const title = (job.title || '').trim();
  for (const term of config.titleBlocklist) {
    if (titleMatchesBlocked(title, term)) {
      console.log(`[REJECT] ${title} at ${job.company} — title_blocked:${term}`);
      return false;
    }
  }
  const desc = (job.description || '').trim();
  if (desc.length >= 80) {
    const required = parseMaxYearsRequired(`${title}\n${desc}`);
    if (required !== null && required > config.maxExperienceYears) {
      console.log(
        `[REJECT] ${title} at ${job.company} — required_years_${required}_exceeds_max_${config.maxExperienceYears}`,
      );
      return false;
    }
  }
  return true;
}
