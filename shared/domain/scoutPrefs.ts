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
  maxExperienceYears: number;
  freshnessDays: number;
}

type PrefsFile = {
  target_role?: string;
  search_terms?: string[];
  blocked_titles?: string[];
  blocked_industries?: string[];
  work_setting?: string;
  experience_range?: { max?: number };
  freshness_days?: number;
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
  const searchTerms =
    prefs.search_terms?.length && prefs.search_terms.every((t) => typeof t === 'string' && t.trim())
      ? prefs.search_terms.map((t) => t.trim())
      : deriveSearchTermsFromTargetRole(targetRole);

  const blockedTitles = prefs.blocked_titles?.length
    ? prefs.blocked_titles
    : DEFAULT_TITLE_BLOCKLIST;

  return {
    targetRole,
    searchTerms,
    titleBlocklist: blockedTitles.map((t) => t.toLowerCase().trim()).filter(Boolean),
    workSetting: prefs.work_setting || 'Remote',
    blockedIndustries: (prefs.blocked_industries || []).map((t) => t.trim()).filter(Boolean),
    maxExperienceYears: prefs.experience_range?.max ?? 7,
    freshnessDays: prefs.freshness_days ?? 7,
  };
}

/** Mirrors server/domain/jobSearchPrefs.ts materialization for PM-family defaults. */
export function deriveSearchTermsFromTargetRole(targetRole: string): string[] {
  const terms = [targetRole.trim()];
  if (targetRole.toLowerCase().includes('product manager')) {
    terms.push(
      'Product Owner',
      'Technical Product Manager',
      'Platform Product Manager',
      'Digital Product Manager',
    );
  }
  return terms;
}
