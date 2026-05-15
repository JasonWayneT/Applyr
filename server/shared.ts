import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { db } from './db.js';

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

// Implements FR-058, SEC-003, SEC-004
// Reads all API keys from SQLite at spawn time — never from .env.
// Python's load_dotenv() does not override existing env vars, so DB values always win.
export function buildPythonEnv(): Record<string, string> {
  const extra: Record<string, string> = {
    PYTHONUNBUFFERED: "1", // Forces immediate flush of stdout to prevent Node buffering lag
  };
  try {
    const llmRow = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as any;
    if (llmRow?.value) {
      const llm = JSON.parse(llmRow.value);
      if (llm.geminiApiKey)     extra.GEMINI_API_KEY     = llm.geminiApiKey;
      if (llm.claudeApiKey)     extra.ANTHROPIC_API_KEY  = llm.claudeApiKey;
      if (llm.perplexityApiKey) extra.PERPLEXITY_API_KEY = llm.perplexityApiKey;
    }
  } catch { /* no llm_settings record yet */ }
  try {
    const connRow = db.prepare("SELECT value FROM profiles WHERE key = 'api_connections'").get() as any;
    if (connRow?.value) {
      const conns = JSON.parse(connRow.value);
      if (conns.adzunaAppId)  extra.ADZUNA_APP_ID  = conns.adzunaAppId;
      if (conns.adzunaAppKey) extra.ADZUNA_APP_KEY = conns.adzunaAppKey;
    }
  } catch { /* no api_connections record yet */ }
  return extra;
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
    experience_range:     existing.experience_range  ?? { min: 0, max: 7, total_years_observed: 6 },
    preferences:          existing.preferences       ?? DEFAULT_PIPELINE_PREFERENCES,
  };

  fs.writeFileSync(CANDIDATE_PREFS_PATH, JSON.stringify(materialized, null, 2), 'utf-8');
}
