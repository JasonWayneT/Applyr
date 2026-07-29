/**
 * Load materialized scout preferences from data/candidate_preferences.json.
 * target_role + search_terms drive ingest title scope (swappable per user).
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const DEFAULT_PREFS_PATH = path.join(__dirname, '../../data/candidate_preferences.json');

const DEFAULT_TITLE_BLOCKLIST = [
  'Staff',
  'VP',
  'Head',
  'Principal',
  'Lead',
  'Director',
  'Group Product Manager',
  'GPM',
  'Growth',
  'Founding',
  'First',
  'Manager of',
  'Engineering Manager',
  'People Manager',
  'Assistant',
  'Coordinator',
  'Intern',
  'Associate',
  'Entry',
  'Junior',
  'Analyst',
  'Software Engineer',
  'Developer',
  'Designer',
  'Marketer',
];

export interface MaterializedScoutPrefs {
  targetRole: string;
  searchTerms: string[];
  titleBlocklist: string[];
  workSetting: string;
  blockedIndustries: string[];
  blockedCompanies: string[];
  maxExperienceYears: number;
  freshnessDays: number;
  builtinStrictTitle: boolean;
  minJdCharsEvaluate: number;
  localAreaTerms: string[];
  timezoneFlexibilityTerms: string[];
  locationPreference: string;
  scoringJdMaxChars: number;
}

type PrefsFile = {
  target_role?: string;
  search_terms?: string[];
  blocked_titles?: string[];
  blocked_industries?: string[];
  blocked_companies?: string[];
  work_setting?: string;
  experience_range?: { max?: number };
  freshness_days?: number;
  builtin_strict_title?: boolean;
  min_jd_chars_evaluate?: number;
  local_area_terms?: string[];
  timezone_flexibility_terms?: string[];
  location_preference?: string;
  scoring_jd_max_chars?: number;
};

export function loadMaterializedScoutPrefs(prefsPath = DEFAULT_PREFS_PATH): MaterializedScoutPrefs {
  let prefs: PrefsFile = {};
  try {
    if (fs.existsSync(prefsPath)) {
      prefs = JSON.parse(fs.readFileSync(prefsPath, 'utf-8')) as PrefsFile;
    }
  } catch {
    /* defaults */
  }

  const targetRole = (prefs.target_role || 'Product Manager').trim();
  const rawSearchTerms =
    prefs.search_terms?.length && prefs.search_terms.every((t) => typeof t === 'string' && t.trim())
      ? prefs.search_terms.map((t) => t.trim())
      : deriveSearchTermsFromTargetRole(targetRole);
  const searchTerms = expandProductManagerSearchTerms(rawSearchTerms);

  const blockedTitles = prefs.blocked_titles?.length
    ? prefs.blocked_titles
    : DEFAULT_TITLE_BLOCKLIST;

  const minJdRaw = prefs.min_jd_chars_evaluate;
  const minJdCharsEvaluate =
    typeof minJdRaw === 'number' && Number.isFinite(minJdRaw) && minJdRaw >= 200
      ? Math.floor(minJdRaw)
      : 800;

  const scoringRaw = prefs.scoring_jd_max_chars;
  const scoringJdMaxChars =
    typeof scoringRaw === 'number' && Number.isFinite(scoringRaw) && scoringRaw >= 500
      ? Math.min(Math.floor(scoringRaw), 15000)
      : 4000;

  return {
    targetRole,
    searchTerms,
    titleBlocklist: blockedTitles.map((t) => t.toLowerCase().trim()).filter(Boolean),
    workSetting: prefs.work_setting || 'Remote',
    blockedIndustries: (prefs.blocked_industries || []).map((t) => t.trim()).filter(Boolean),
    blockedCompanies: (prefs.blocked_companies || []).map((t) => t.trim()).filter(Boolean),
    maxExperienceYears: prefs.experience_range?.max ?? 7,
    freshnessDays: prefs.freshness_days ?? 7,
    builtinStrictTitle: prefs.builtin_strict_title !== false,
    minJdCharsEvaluate,
    localAreaTerms: (prefs.local_area_terms || []).map((t) => t.trim()).filter(Boolean),
    timezoneFlexibilityTerms: (prefs.timezone_flexibility_terms || [])
      .map((t) => t.trim())
      .filter(Boolean),
    locationPreference: (prefs.location_preference || 'United States').trim(),
    scoringJdMaxChars,
  };
}

function dedupeSearchTerms(terms: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const term of terms) {
    const trimmed = term.trim();
    const key = trimmed.toLowerCase();
    if (!trimmed || seen.has(key)) continue;
    seen.add(key);
    out.push(trimmed);
  }
  return out;
}

/** Product Manager search also tags Technical Product Manager for connector queries + ingest scope. */
export function expandProductManagerSearchTerms(terms: string[]): string[] {
  const normalized = terms.map((t) => t.trim()).filter(Boolean);
  const hasPm = normalized.some((t) => /^product\s+manager$/i.test(t));
  if (!hasPm) return normalized;
  const out = [...normalized];
  if (!normalized.some((t) => /^technical\s+product\s+manager$/i.test(t))) {
    out.push('Technical Product Manager');
  }
  return dedupeSearchTerms(out);
}

/** When search_terms are omitted, default to target_role (PM expands to TPM). */
export function deriveSearchTermsFromTargetRole(targetRole: string): string[] {
  const role = (targetRole || '').trim();
  if (!role) return [];
  if (/^product\s+manager$/i.test(role)) {
    return expandProductManagerSearchTerms([role]);
  }
  return [role];
}
