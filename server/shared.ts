import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const PROJECT_ROOT         = path.join(__dirname, '..');
export const SCRIPTS_DIR          = path.join(PROJECT_ROOT, 'scripts');
export const SUBMISSION_DIR       = path.join(PROJECT_ROOT, 'data/submissions');
export const ARCHIVE_DIR          = path.join(PROJECT_ROOT, 'data/archive/submissions');
export const WORK_EXPERIENCE_PATH = path.join(PROJECT_ROOT, 'data/workExperience.md');
// CANDIDATE_PREFS_PATH re-exported from ./domain/paths.js
/** Local tsx CLI — used instead of `npx tsx` so Windows spawn works without shell (BUG-015 / FR-164). */
export const TSX_CLI_PATH = path.join(PROJECT_ROOT, 'node_modules', 'tsx', 'dist', 'cli.mjs');

/** Windows-safe tsx spawn: `node` + local cli.mjs + script path (no `npx`). */
export function buildTsxSpawn(scriptRelativeToRoot: string, extraArgs: string[] = []): { command: string; args: string[] } {
  return {
    command: process.execPath,
    args: [TSX_CLI_PATH, path.join(PROJECT_ROOT, scriptRelativeToRoot), ...extraArgs],
  };
}

// Allowlist of columns that may be updated via the generic PATCH /api/jobs/:id endpoint
export const ALLOWED_JOB_FIELDS = new Set([
  'title', 'company', 'url', 'score', 'summary', 'status',
  'salary_range', 'recruiter_name', 'recruiter_url', 'source_site',
  'rejection_stage', 'rejection_type', 'outcome_notes', 'interview_date', 'applied_at',
]);

export { DATE_POSTED_TO_DAYS, CANDIDATE_PREFS_PATH } from './domain/paths.js';
export { materializeJobSearchPrefs, readMinFitScore } from './domain/jobSearchPrefs.js';
export { ACTIVE_STATUSES, isActivePipelineStatus, submissionBaseDir } from './domain/jobStatus.js';

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

export function sanitizeCompanySlug(company: string): string {
  let slug = company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  if (!slug) {
    slug = 'company_' + crypto.createHash('md5').update(company).digest('hex').slice(0, 12);
  }
  if (!slug || slug.includes('..') || slug.startsWith('.')) {
    throw new Error(`Invalid company name for folder slug: ${company}`);
  }
  return slug;
}

// Fuzzy-matches a company name to its folder under baseDir (handles slug variants).
export function resolveCompanyFolder(company: string, baseDir: string): string {
  const companySlug = sanitizeCompanySlug(company);
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
  } catch {}

  return standardPath;
}

