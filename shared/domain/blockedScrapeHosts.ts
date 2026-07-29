/**
 * FR-080 (CR-010): hosts Applyr must never scrape during routine pipeline runs.
 */

const LINKEDIN_HOSTS = new Set(['linkedin.com', 'www.linkedin.com', 'lnkd.in']);

/** True when URL targets linkedin.com job/apply pages (not candidate profile URLs in resumes). */
export function isLinkedInJobUrl(url: string | null | undefined): boolean {
  if (!url?.trim()) return false;
  try {
    const host = new URL(url.trim()).hostname.toLowerCase().replace(/^www\./, '');
    if (LINKEDIN_HOSTS.has(host) || host.endsWith('.linkedin.com')) return true;
    return /linkedin\.com/i.test(url);
  } catch {
    return /linkedin\.com/i.test(url);
  }
}

/** Hosts blocked for Playwright JD extraction (routine scout scrape stage). */
export function isBlockedScrapeUrl(url: string | null | undefined): boolean {
  return isLinkedInJobUrl(url);
}
