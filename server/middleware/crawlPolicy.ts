import { db, logActivity } from '../db.js';

export type CrawlPolicyStatus = 'allowed' | 'paused' | 'blocked' | 'manual_review' | 'unknown';

export interface CrawlPolicyResult {
  status: CrawlPolicyStatus;
}

/**
 * Checks domain_policies before any crawl. Synchronous (better-sqlite3).
 * Returns 'unknown' and logs WARN if domain is absent from the table.
 * Returns the stored status and logs WARN if status is not 'allowed'.
 */
export function checkCrawlPolicy(domain: string): CrawlPolicyResult {
  const row = db
    .prepare('SELECT status FROM domain_policies WHERE domain = ?')
    .get(domain) as { status: string } | undefined;

  if (!row) {
    logActivity('WARN', 'CrawlPolicy', `Domain not in policy table — blocking fetch: ${domain}`);
    return { status: 'unknown' };
  }

  if (row.status !== 'allowed') {
    logActivity('WARN', 'CrawlPolicy', `Domain ${domain} policy status is '${row.status}' — skipping fetch`);
  }

  return { status: row.status as CrawlPolicyStatus };
}
