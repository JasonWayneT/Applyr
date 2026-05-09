// Fallback defaults only — the live values are driven by candidate_preferences.json,
// which is materialized from the Job Search settings page on every save.
// These are used only when the preferences file cannot be read.

export const TITLE_BLOCKLIST = [
  'senior', 'staff', 'vp', 'head', 'principal', 'lead product manager',
  'director', 'growth', 'founding', 'manager of',
  'assistant', 'coordinator', 'intern', 'associate', 'junior',
  'analyst', 'engineer', 'developer', 'designer', 'marketer',
];

export const INDUSTRY_BLOCKLIST_DEFAULT = [
  'gambling', 'sports betting', 'gaming', 'ad tech', 'crypto', 'web3',
];

export const SCOUT_FRESHNESS_DAYS = 7;
