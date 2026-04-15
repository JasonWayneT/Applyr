// Single source of truth for all gate/filter configuration.
// The frontend fetches this via GET /api/config to stay in sync.

export const TITLE_BLOCKLIST = [
  'senior', 'staff', 'vp', 'head', 'principal', 'lead product manager',
  'director', 'growth', 'founding', 'manager of',
];

export const INDUSTRY_BLOCKLIST_DEFAULT = [
  'gambling', 'sports betting', 'gaming', 'ad tech', 'crypto', 'web3',
];
