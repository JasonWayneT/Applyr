import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const PROJECT_ROOT         = path.join(__dirname, '..');
export const SCRIPTS_DIR          = path.join(PROJECT_ROOT, 'scripts');
export const SUBMISSION_DIR       = path.join(PROJECT_ROOT, 'submissions');
export const ARCHIVE_DIR          = path.join(PROJECT_ROOT, 'archive/submissions');
export const WORK_EXPERIENCE_PATH = path.join(PROJECT_ROOT, 'data/workExperience.md');
export const CANDIDATE_PREFS_PATH = path.join(PROJECT_ROOT, 'data/candidate_preferences.json');

// Allowlist of columns that may be updated via the generic PATCH /api/jobs/:id endpoint
export const ALLOWED_JOB_FIELDS = new Set([
  'title', 'company', 'url', 'score', 'summary', 'status',
  'salary_range', 'recruiter_name', 'recruiter_url', 'source_site',
  'rejection_stage', 'rejection_type', 'outcome_notes', 'interview_date',
]);

export const DATE_POSTED_TO_DAYS: Record<string, number> = {
  'Past 24 hours': 1,
  'Past 3 days':   3,
  'Past week':     7,
  'Past month':    30,
};

const DEFAULT_JD_KEYWORDS = [
  'saas', 'b2b', 'platform', 'integration', 'enterprise', 'api',
  'product', 'software', 'agile', 'roadmap', 'stakeholder',
];

const DEFAULT_PIPELINE_PREFERENCES = {
  no_people_management: true,
  no_zero_to_one: true,
  structured_team_required: true,
  max_company_size_penalty_threshold: 50,
};

// Implements FR-095 / CR-015 — spawn flags only; secrets read from SQLite inside each script.
export function buildPythonEnv(): Record<string, string> {
  return {
    PYTHONUNBUFFERED: '1',
    DRAFT_MODE: process.env.DRAFT_MODE || 'compose',
    LOCAL_ONLY_MODE: process.env.LOCAL_ONLY_MODE || '1',
    JD_PROFILE_MODE: process.env.JD_PROFILE_MODE || 'deterministic',
    COVER_HOOK_MODE: process.env.COVER_HOOK_MODE || 'template',
    CHEAT_SHEET_MODE: process.env.CHEAT_SHEET_MODE || 'template',
    RESEARCH_MODE: process.env.RESEARCH_MODE || 'local',
    BATCH_PARALLEL_WORKERS: process.env.BATCH_PARALLEL_WORKERS || '1',
    FIT_LLM_TIMEOUT_SEC: process.env.FIT_LLM_TIMEOUT_SEC || '180',
    BATCH_FAST_MODE: process.env.BATCH_FAST_MODE || '0',
    BATCH_UNLOAD_MODELS: process.env.BATCH_UNLOAD_MODELS || '0',
    BATCH_INTER_JOB_SLEEP_SEC: process.env.BATCH_INTER_JOB_SLEEP_SEC || '2',
    FIT_NUM_PREDICT: process.env.FIT_NUM_PREDICT || '768',
  };
}

// Fuzzy-matches a company name to its folder under baseDir (handles slug variants).
export function resolveCompanyFolder(company: string, baseDir: string): string {
  const companySlug = company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  const standardPath = path.join(baseDir, companySlug);
  if (fs.existsSync(standardPath)) return standardPath;

  const withTrailing = company.toLowerCase().replace(/[^a-z0-9]+/g, '_');
  const trailingPath = path.join(baseDir, withTrailing);
  if (fs.existsSync(trailingPath)) return trailingPath;

  const simpleReplace = company.toLowerCase().replace(/ /g, '_');
  const pathSimple = path.join(baseDir, simpleReplace);
  if (fs.existsSync(pathSimple)) return pathSimple;

  try {
    const strippedTarget = company.toLowerCase().replace(/[^a-z0-9]/g, '');
    for (const d of fs.readdirSync(baseDir)) {
      if (d.toLowerCase().replace(/[^a-z0-9]/g, '') === strippedTarget) {
        return path.join(baseDir, d);
      }
    }
  } catch (_) {}

  return standardPath;
}

// Implements ADR-005 — writes candidate_preferences.json as a projection of the job_search profile row.
export function materializeJobSearchPrefs(jobSearch: any): void {
  let existing: any = {};
  try {
    if (fs.existsSync(CANDIDATE_PREFS_PATH)) {
      existing = JSON.parse(fs.readFileSync(CANDIDATE_PREFS_PATH, 'utf-8'));
    }
  } catch { /* use defaults */ }

  const targetRole: string = jobSearch.targetRole || 'Product Manager';
  const searchTerms: string[] = [targetRole];
  if (targetRole.toLowerCase().includes('product manager')) {
    searchTerms.push('Product Owner', 'Technical Product Manager', 'Platform Product Manager', 'Digital Product Manager');
  }

  const blockedTitles: string[]    = (jobSearch.titleBlocklist    || '').split(',').map((s: string) => s.trim()).filter(Boolean);
  const blockedIndustries: string[] = (jobSearch.industryBlocklist || '').split(',').map((s: string) => s.trim()).filter(Boolean);

  const maxYears = jobSearch.maxYearsRequired ?? existing.experience_range?.max ?? 7;
  const minYears = jobSearch.minYearsPreferred ?? existing.experience_range?.min ?? 2;
  const totalYears = existing.experience_range?.total_years_observed ?? 6;

  const materialized = {
    target_role:          targetRole,
    search_terms:         searchTerms,
    location_preference:  jobSearch.location        || 'United States',
    work_setting:         jobSearch.workSetting      || 'Remote',
    experience_levels:    jobSearch.experienceLevels || [],
    date_posted:          jobSearch.datePosted       || 'Past week',
    freshness_days:       DATE_POSTED_TO_DAYS[jobSearch.datePosted] ?? 7,
    blocked_titles:       blockedTitles,
    blocked_industries:   blockedIndustries,
    min_salary:           jobSearch.minSalary        ?? 0,
    min_fit_score:        existing.min_fit_score     ?? 72,
    jd_required_keywords: existing.jd_required_keywords ?? DEFAULT_JD_KEYWORDS,
    experience_range:     { min: minYears, max: maxYears, total_years_observed: totalYears },
    preferences:          existing.preferences       ?? DEFAULT_PIPELINE_PREFERENCES,
  };

  fs.writeFileSync(CANDIDATE_PREFS_PATH, JSON.stringify(materialized, null, 2), 'utf-8');
}
