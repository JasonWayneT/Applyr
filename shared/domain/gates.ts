/**
 * Deterministic ingest gates — pure functions, no I/O.
 * Used by scout orchestrator at ingest; tested in tests/unit/gates.test.ts.
 */
import {
  isExplicitForeignLocation,
  textHasRemoteSignal,
  textMatchesLocalArea,
  normalizeGeoTerms,
  type GeoPrefs,
} from './geoPrefs.js';

export type { GeoPrefs };
export { passesBuiltInStrictRemoteCard } from './geoPrefs.js';

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
  localAreaTerms: string[];
  locationPreference: string;
}

export interface TargetRolePrefs {
  targetRole: string;
  searchTerms: string[];
  /** When true (Built In only), apply extra adjacent-role deny patterns at ingest. */
  builtinStrictTitle?: boolean;
}

/** Connector sourceId values that are remote-by-definition (lowercase). */
const REMOTE_ONLY_SOURCES = new Set([
  'remotive',
  'remoteok',
  'weworkremotely',
  'wwr',
  'himalayas',
  'jobicy',
  'workingnomads',
  'jobscollider',
]);

function isRemoteOnlySource(source: string): boolean {
  return REMOTE_ONLY_SOURCES.has((source || '').trim().toLowerCase());
}

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

/** PM-family titles matched when search term is Product Manager (not exact-title equality). */
const PRODUCT_MANAGER_FAMILY_TITLE =
  /\b(?:(?:technical|platform|data|enterprise|api|integration|infrastructure|senior|group)\s+)?product\s+manager\b/i;

export function isProductManagerSearchTerm(term: string): boolean {
  return /^product\s+manager$/i.test((term || '').trim());
}

export function titleMatchesProductManagerFamily(title: string): boolean {
  return PRODUCT_MANAGER_FAMILY_TITLE.test((title || '').trim());
}

/** Preference-driven positive match: title contains a configured search term. */
export function titleMatchesSearchTerm(title: string, term: string): boolean {
  const t = (title || '').trim();
  const q = (term || '').trim();
  if (!t || !q) return false;
  if (isProductManagerSearchTerm(q)) {
    return titleMatchesProductManagerFamily(t);
  }
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

/** Adjacent-role deny list applies only when search terms suggest a product-focused hunt. */
export function shouldApplyAdjacentRoleDeny(searchTerms: string[]): boolean {
  return searchTerms.some((term) => /product/i.test(term || ''));
}

/** Adjacent-role titles rejected on broad category feeds (product marketing, project manager, etc.). */
export const ADJACENT_ROLE_DENY_PATTERNS: RegExp[] = [
  /\bproduct marketing\b/i,
  /\bproduct design/i,
  /\bproduct analyt/i,
  /\bproject manager\b/i,
  /\bsolutions engineer\b/i,
  /\bsales development\b/i,
  /\baccount executive\b/i,
  /\bcustomer success\b/i,
  /\binside sales\b/i,
];

const BUILTIN_EXTRA_DENY_PATTERNS: RegExp[] = [
  /\bdevops\b/i,
  /\bsoftware engineer\b/i,
  /\bdata engineer\b/i,
  /\bproduct designer\b/i,
  /\bproduct analyst\b/i,
  /\btalent community\b/i,
  /\btechnical writer\b/i,
  /\brecruiter\b/i,
];

export function passesCompanyBlocklist(company: string, blocklist: string[]): boolean {
  const key = (company || '').trim().toLowerCase();
  if (!key || !blocklist.length) return true;
  return !blocklist.some((entry) => {
    const e = entry.trim().toLowerCase();
    return e && (key.includes(e) || e.includes(key));
  });
}

export function passesTitleDenyPatterns(title: string, extraPatterns: RegExp[] = []): boolean {
  const t = (title || '').trim();
  if (!t) return false;
  const all = [...ADJACENT_ROLE_DENY_PATTERNS, ...extraPatterns];
  return !all.some((pat) => pat.test(t));
}

/**
 * @deprecated Legacy PM-specific gate — use passesTargetRoleTitleScope with user search_terms.
 */
export function passesBuiltInPmTitleScope(title: string): boolean {
  const t = (title || '').trim();
  if (!t) return false;
  if (!/\bproduct manager\b/i.test(t)) return false;
  if (/\bproduct owner\b/i.test(t) && !/\bproduct manager\b/i.test(t)) return false;
  for (const pat of BUILTIN_EXTRA_DENY_PATTERNS) {
    if (pat.test(t)) return false;
  }
  if (/\bproduct marketing\b/i.test(t)) return false;
  return true;
}

/**
 * @deprecated Legacy PM-specific gate — use passesTargetRoleTitleScope with user search_terms.
 */
export function passesBroadPmTitleScope(title: string): boolean {
  const t = (title || '').trim();
  if (!t) return false;
  if (!passesTitleDenyPatterns(t)) return false;
  return (
    /\bproduct manager\b/i.test(t) ||
    /\bproduct owner\b/i.test(t) ||
    /\b(technical|platform|data|ai|api|integration|enterprise|infrastructure) product\b/i.test(t)
  );
}

/**
 * Single ingest choke point: positive match on user search_terms, then adjacent-role deny patterns.
 */
export function passesTargetRoleTitleScope(
  title: string,
  prefs: TargetRolePrefs,
  sourceId?: string,
): boolean {
  const t = (title || '').trim();
  if (!t) return false;

  if (!passesSearchTermsTitleScope(t, prefs.searchTerms)) return false;

  if (shouldApplyAdjacentRoleDeny(prefs.searchTerms)) {
    const extra =
      sourceId === 'builtin' && prefs.builtinStrictTitle ? BUILTIN_EXTRA_DENY_PATTERNS : [];
    if (!passesTitleDenyPatterns(t, extra)) return false;
  }

  return true;
}

export function passesGeographicGate(job: ScrapedJob, config: GateConfig): boolean {
  const text = `${job.title} ${job.description || ''}`.toLowerCase();
  const localTerms = normalizeGeoTerms(config.localAreaTerms);

  if ((job.description || '').trim().length < 50) {
    if (textMatchesLocalArea(job.title, localTerms)) return true;
    if (config.workSetting === 'Remote') {
      if (isRemoteOnlySource(job.source)) return true;
      console.log(
        `[REJECT] ${job.title} at ${job.company} (${job.source}) - [GEOGRAPHIC REJECT] remote_only_no_location_signal`,
      );
      return false;
    }
    return true;
  }

  if (isExplicitForeignLocation(text, config.locationPreference)) return false;
  if (textMatchesLocalArea(text, localTerms) || textHasRemoteSignal(text)) return true;
  if (isRemoteOnlySource(job.source)) return true;
  return false;
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
