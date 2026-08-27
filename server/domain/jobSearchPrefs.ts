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

/** Keys managed by pipeline/rollout — not overwritten when UI re-materializes prefs (FR-248 / CR-053).
 *  local_area_terms is NOT here (2026-08-26): it used to be a UI-invisible field that needed
 *  preserving across saves, but the Location field now actively derives it every save (see
 *  resolveLocation below) — preserving the old value here would just re-overwrite that with
 *  whatever was set before, silently ignoring what the user just typed. */
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
] as const;

/** Must stay in sync with COUNTRY_LOCATIONS in src/pages/SyncActivityView.tsx — the one
 *  Location dropdown's value is a country/region preset if it matches one of these,
 *  otherwise (a CITY_LOCATIONS entry) it's treated as a "City, State" value (2026-08-26,
 *  Jason-supplied: one field like real job boards use, not a separate city control — made a
 *  dropdown rather than free text so a typo can't silently produce an unmatchable term). */
const KNOWN_LOCATION_PRESETS = new Set([
  'united states', 'canada', 'united kingdom', 'australia', 'worldwide / remote only',
]);

/** Must stay in sync with CITY_LOCATIONS in src/pages/SyncActivityView.tsx — maps each
 *  dropdown city to the country its location_preference should resolve to, so a UK or
 *  Canadian or Australian city doesn't get silently mislabeled "United States." A city
 *  missing here defaults to United States (see resolveLocation) rather than failing closed,
 *  since that covers the common case if the two lists ever briefly drift after an edit. */
const CITY_COUNTRY: Record<string, string> = {
  'new york, ny': 'United States', 'los angeles, ca': 'United States',
  'san diego, ca': 'United States', 'san francisco, ca': 'United States',
  'san jose, ca': 'United States', 'chicago, il': 'United States',
  'seattle, wa': 'United States', 'austin, tx': 'United States',
  'dallas, tx': 'United States', 'houston, tx': 'United States',
  'boston, ma': 'United States', 'denver, co': 'United States',
  'atlanta, ga': 'United States', 'phoenix, az': 'United States',
  'philadelphia, pa': 'United States', 'washington, dc': 'United States',
  'miami, fl': 'United States', 'portland, or': 'United States',
  'minneapolis, mn': 'United States', 'charlotte, nc': 'United States',
  'raleigh, nc': 'United States', 'nashville, tn': 'United States',
  'salt lake city, ut': 'United States',
  'toronto, on': 'Canada', 'vancouver, bc': 'Canada', 'montreal, qc': 'Canada',
  'calgary, ab': 'Canada', 'ottawa, on': 'Canada',
  'london, uk': 'United Kingdom', 'manchester, uk': 'United Kingdom',
  'birmingham, uk': 'United Kingdom', 'edinburgh, uk': 'United Kingdom',
  'sydney, nsw': 'Australia', 'melbourne, vic': 'Australia',
  'brisbane, qld': 'Australia', 'perth, wa': 'Australia',
};

/** Metro-area expansions so a city keeps matching neighboring cities real postings often
 *  name instead of the metro itself (a Carlsbad or La Jolla listing rarely says "San Diego").
 *  Only San Diego has one today — add an entry when there's a real reason to (a city
 *  without one still works, just without the neighboring-city broadening). */
const METRO_EXPANSIONS: Record<string, string[]> = {
  'san diego': [
    'san diego', 'sd, ca', 'carlsbad', 'la jolla', 'del mar', 'encinitas',
    'chula vista', 'oceanside', 'escondido', 'poway', 'san marcos, ca',
  ],
};

/** Splits the single Location field into location_preference (broad country/region) and
 *  local_area_terms (specific city, for the "remote OR local" geographic gate) — see
 *  shared/domain/gates.ts's passesGeographicGate. */
export function resolveLocation(rawLocation: unknown): {
  location_preference: string;
  local_area_terms: string[];
} {
  const value = String(rawLocation ?? '').trim();
  if (!value) {
    return { location_preference: 'United States', local_area_terms: [] };
  }
  if (KNOWN_LOCATION_PRESETS.has(value.toLowerCase())) {
    return { location_preference: value, local_area_terms: [] };
  }

  // A CITY_LOCATIONS entry — resolve its real country rather than assuming US, and drop a
  // trailing ", ST"/", XYZ" region code (2 or 3 letters) for the METRO_EXPANSIONS lookup only;
  // local_area_terms itself keeps the full label so "Toronto, ON" doesn't collide with a
  // same-named city in another region.
  const cityKey = value.toLowerCase();
  const country = CITY_COUNTRY[cityKey] ?? 'United States';
  const strippedKey = cityKey.replace(/,\s*[a-z]{2,3}$/i, '').trim();
  const expansion = METRO_EXPANSIONS[strippedKey];
  return {
    location_preference: country,
    local_area_terms: expansion ?? [cityKey],
  };
}

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

  const { location_preference, local_area_terms } = resolveLocation(jobSearch.location);

  const materialized: Record<string, unknown> = {
    target_role: targetRole,
    search_terms: searchTerms,
    location_preference,
    local_area_terms,
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
