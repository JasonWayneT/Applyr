/**
 * Preference-driven geographic helpers — no hardcoded metro lists.
 */
export interface GeoPrefs {
  /** Cities/regions where on-site or hybrid is acceptable (lowercase match in text). */
  localAreaTerms: string[];
  /** e.g. "United States" — used for foreign-location heuristics. */
  locationPreference?: string;
  /** When set with preferences.reject_est_cst_remote, remote EST/CST roles pass if any term appears in JD. */
  timezoneFlexibilityTerms?: string[];
}

export function normalizeGeoTerms(terms: string[] | undefined): string[] {
  return (terms ?? []).map((t) => t.trim().toLowerCase()).filter(Boolean);
}

export function textMatchesLocalArea(text: string, localAreaTerms: string[]): boolean {
  const lower = (text || '').toLowerCase();
  if (!lower || !localAreaTerms.length) return false;
  return localAreaTerms.some((term) => lower.includes(term));
}

export function textHasRemoteSignal(text: string): boolean {
  const lower = (text || '').toLowerCase();
  return (
    lower.includes('remote') ||
    lower.includes('anywhere in') ||
    lower.includes('work from home') ||
    lower.includes('telecommute') ||
    lower.includes('wfh')
  );
}

const BUILTIN_HYBRID_OR_ONSITE_CARD =
  /\b(in[-\s]?office\s+or\s+remote|remote\s+or\s+hybrid|hybrid\s+or\s+remote|on[-\s]?site|in[-\s]?office)\b/i;

/** Built In listing card: remote signal or user-configured local area; reject hybrid/onsite combo cards. */
export function passesBuiltInStrictRemoteCard(cardText: string, geo: GeoPrefs): boolean {
  const c = (cardText || '').toLowerCase();
  if (!c) return false;
  if (BUILTIN_HYBRID_OR_ONSITE_CARD.test(c)) return false;
  if (textHasRemoteSignal(c)) return true;
  return textMatchesLocalArea(c, normalizeGeoTerms(geo.localAreaTerms));
}

export function isExplicitForeignLocation(text: string, locationPreference = 'United States'): boolean {
  const lower = (text || '').toLowerCase();
  const pref = (locationPreference || '').toLowerCase();
  const foreignSignals = [
    'canada',
    'united kingdom',
    'london,',
    'europe',
    'germany',
    'india',
    'apac',
  ];
  const usSignals = ['united states', 'within the us', 'us citizen', 'usa'];
  const isForeign = foreignSignals.some((k) => lower.includes(k));
  if (!isForeign) return false;
  if (pref.includes('united states') || pref.includes('usa') || pref.includes('us')) {
    return !usSignals.some((k) => lower.includes(k));
  }
  return isForeign;
}
