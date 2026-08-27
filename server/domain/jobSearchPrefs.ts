/**
 * Projects job_search profile row to data/candidate_preferences.json (ADR-005).
 * Moved from shared.ts (CR-ARCH-002).
 */
import fs from 'fs';
import { CANDIDATE_PREFS_PATH, DATE_POSTED_TO_DAYS } from './paths.js';

import { deriveSearchTermsFromTargetRole } from '../../shared/domain/scoutPrefs.js';

export { CANDIDATE_PREFS_PATH } from './paths.js';

/** Legacy auto-expanded terms — stripped on materialize unless user adds via UI search terms field. */
const LEGACY_STRIPPED_SEARCH_TERMS = new Set(['Product Owner']);

function dedupeSearchTerms(terms: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const term of terms) {
    const key = term.toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(term);
  }
  return out;
}

function parseAdditionalSearchTerms(raw: unknown): string[] {
  if (typeof raw === 'string') {
    return raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (Array.isArray(raw)) {
    return raw.map((t) => String(t).trim()).filter(Boolean);
  }
  return [];
}

/** Resolve scout search_terms from UI job_search payload + existing prefs file. */
export function resolveMaterializedSearchTerms(
  jobSearch: Record<string, unknown>,
  existing: Record<string, unknown>,
): string[] {
  const targetRole = (jobSearch.targetRole as string) || 'Product Manager';
  const hasUiSearchTerms =
    jobSearch.additionalSearchTerms !== undefined || jobSearch.searchTerms !== undefined;
  const uiExtras = parseAdditionalSearchTerms(
    jobSearch.additionalSearchTerms ?? jobSearch.searchTerms,
  );

  if (hasUiSearchTerms) {
    return dedupeSearchTerms([targetRole.trim(), ...uiExtras].filter(Boolean));
  }

  const existingTerms = existing.search_terms;
  if (
    Array.isArray(existingTerms) &&
    existingTerms.length > 0 &&
    existingTerms.every((t) => typeof t === 'string' && String(t).trim())
  ) {
    return dedupeSearchTerms(
      (existingTerms as string[])
        .map((t) => String(t).trim())
        .filter((t) => t && !LEGACY_STRIPPED_SEARCH_TERMS.has(t)),
    );
  }

  return deriveSearchTermsFromTargetRole(targetRole);
}

/** Keys managed by pipeline/rollout — not overwritten when UI re-materializes prefs (FR-248 / CR-053). */
export const PRESERVE_PIPELINE_PREF_KEYS = [
  'blocked_role_titles',
  'blocked_focus_area_words',
  'blocked_companies',
  'min_confidence_score',
  'must_have_keywords',
  'required_anchors',
  'domain_experience',
  'required_domain_min_years',
  'po_solo_backlog_flags',
  'po_solo_backlog_mitigators',
  'local_area_terms',
] as const;

// readMinFitScore() removed (CR-093, 2026-08-19) — it read the old fit-scoring
// floor (min_fit_score), which lived only in the now-deleted batch_pipeline.py
// evaluate_job_fit() path and had zero live callers of its own even before that.
// The real fit-scoring floor now lives in data/fit_rubric_calibration.json,
// read by scripts/evidence_scale.py's load_score_bands() — not this file.

const DEFAULT_JD_KEYWORDS = [
  'saas', 'b2b', 'platform', 'integration', 'enterprise', 'api',
  'product', 'software', 'agile', 'roadmap', 'stakeholder',
];

const DEFAULT_PIPELINE_PREFERENCES = {
  avoid_solo_pm_trap: true,
  no_zero_to_one: true,
  structured_team_required: true,
  max_company_size_penalty_threshold: 50,
};

/** Build merged prefs object — testable without filesystem (FR-248). */
export function buildMaterializedJobSearchPrefs(
  jobSearch: Record<string, unknown>,
  existing: Record<string, unknown> = {},
): Record<string, unknown> {
  const targetRole = (jobSearch.targetRole as string) || 'Product Manager';
  const searchTerms = resolveMaterializedSearchTerms(jobSearch, existing);

  const blockedTitles = ((jobSearch.titleBlocklist as string) || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  const blockedIndustries = ((jobSearch.industryBlocklist as string) || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

  const expRange = (existing.experience_range as Record<string, number>) || {};
  const maxYears = (jobSearch.maxYearsRequired as number) ?? expRange.max ?? 7;
  const minYears = (jobSearch.minYearsPreferred as number) ?? expRange.min ?? 2;
  const totalYears = expRange.total_years_observed ?? 6;

  const materialized: Record<string, unknown> = {
    target_role: targetRole,
    search_terms: searchTerms,
    location_preference: (jobSearch.location as string) || 'United States',
    work_setting: (jobSearch.workSetting as string) || 'Remote',
    experience_levels: jobSearch.experienceLevels || [],
    date_posted: (jobSearch.datePosted as string) || 'Past week',
    freshness_days: DATE_POSTED_TO_DAYS[(jobSearch.datePosted as string)] ?? 7,
    blocked_titles: blockedTitles,
    blocked_industries: blockedIndustries,
    min_salary: (jobSearch.minSalary as number) ?? 0,
    jd_required_keywords: (existing.jd_required_keywords as string[]) ?? DEFAULT_JD_KEYWORDS,
    signal_keywords:
      (existing.signal_keywords as string[])
      ?? (existing.jd_required_keywords as string[])
      ?? DEFAULT_JD_KEYWORDS,
    must_have_keywords: (existing.must_have_keywords as string[]) ?? [],
    required_anchors: (existing.required_anchors as string[]) ?? [],
    experience_range: { min: minYears, max: maxYears, total_years_observed: totalYears },
    preferences: (() => {
      const base: Record<string, unknown> = {
        ...DEFAULT_PIPELINE_PREFERENCES,
        ...((existing.preferences as Record<string, unknown>) ?? {}),
      };
      delete base.no_people_management;
      if (base.avoid_solo_pm_trap === undefined) base.avoid_solo_pm_trap = true;
      return base;
    })(),
  };

  // Implements FR-248 — preserve pipeline-only gate keys across UI save
  for (const key of PRESERVE_PIPELINE_PREF_KEYS) {
    if (existing[key] !== undefined) {
      materialized[key] = existing[key];
    }
  }

  return materialized;
}

export function materializeJobSearchPrefs(jobSearch: Record<string, unknown>): void {
  let existing: Record<string, unknown> = {};
  try {
    if (fs.existsSync(CANDIDATE_PREFS_PATH)) {
      existing = JSON.parse(fs.readFileSync(CANDIDATE_PREFS_PATH, 'utf-8'));
    }
  } catch { /* use defaults */ }

  const materialized = buildMaterializedJobSearchPrefs(jobSearch, existing);
  fs.writeFileSync(CANDIDATE_PREFS_PATH, JSON.stringify(materialized, null, 2), 'utf-8');
}
