import { chromium } from 'playwright-extra';
import stealthPlugin from 'puppeteer-extra-plugin-stealth';
import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

chromium.use(stealthPlugin());

const DOMAIN = 'builtin.com';
const MAX_PAGES = 2;

interface BuiltInConfig {
  freshnessDays?: number;
  contextDir?: string;
  /** Injected at runtime from server/middleware/crawlPolicy. Tests pass a mock. */
  policyChecker?: (domain: string) => { status: string };
}

function buildSeedUrl(freshnessDays: number): string {
  const term = 'Product Manager';
  return (
    `https://builtin.com/jobs/remote/mid-level` +
    `?search=${encodeURIComponent(term)}` +
    `&daysSinceUpdated=${freshnessDays}` +
    `&days_since_posted=${freshnessDays}` +
    `&city=&state=&country=USA&allLocations=true`
  );
}

function canonicalizeUrl(raw: string): string {
  try {
    const u = new URL(raw);
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'ref', 'src', 'trk'].forEach((p) =>
      u.searchParams.delete(p),
    );
    return u.toString();
  } catch {
    return raw;
  }
}

const humanWait = (min = 2000, max = 5000) =>
  new Promise<void>((r) => setTimeout(r, Math.floor(Math.random() * (max - min + 1) + min)));

export function createBuiltInConnector(config?: BuiltInConfig): JobConnector {
  const freshnessDays = config?.freshnessDays ?? 7;
  const contextDir = config?.contextDir ?? 'data/browser_context';
  const policyChecker = config?.policyChecker ?? (() => ({ status: 'unknown' as const }));

  return {
    sourceId: 'builtin',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const policy = policyChecker(DOMAIN);
      if (policy.status !== 'allowed') {
        return [];
      }

      const results: RawJobPayload[] = [];
      const seenUrls = new Set<string>();
      const seedUrl = buildSeedUrl(freshnessDays);

      const context = await chromium.launchPersistentContext(contextDir, {
        headless: true,
        viewport: { width: 1440, height: 900 },
        args: ['--disable-blink-features=AutomationControlled'],
      });

      try {
        const page = context.pages()[0] ?? (await context.newPage());

        for (let pageNum = 1; pageNum <= MAX_PAGES; pageNum++) {
          const pageUrl = pageNum === 1 ? seedUrl : `${seedUrl}&page=${pageNum}`;
          try {
            await page.goto(pageUrl, { waitUntil: 'domcontentloaded' });
            await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
            await humanWait(2000, 4000);
            await page
              .waitForSelector('.job-item, div[data-id="job-card"]', { timeout: 10000 })
              .catch(() => {});

            const cards = await page.$$('.job-item, div[data-id="job-card"]');
            if (cards.length === 0) break;

            const prevSize = seenUrls.size;

            for (const card of cards) {
              try {
                const title = (
                  await card
                    .$eval('[data-id="job-card-title"], .card-alias-after-overlay', (el) => el.textContent)
                    .catch(() => '')
                ).trim();

                const company = (
                  await card
                    .$eval('[data-id="company-title"]', (el) => el.textContent)
                    .catch(() =>
                      card.$eval('a[href^="/company/"]', (el) => el.textContent).catch(() => ''),
                    )
                ).trim();

                const relUrl = await card
                  .$eval('[data-id="job-card-title"], a.card-alias-after-overlay', (el) =>
                    el.getAttribute('href'),
                  )
                  .catch(() => '');

                if (!relUrl || !title || !company) continue;

                const rawUrl = relUrl.startsWith('http') ? relUrl : `https://builtin.com${relUrl}`;
                const url = canonicalizeUrl(rawUrl);
                if (seenUrls.has(url)) continue;
                seenUrls.add(url);

                results.push({
                  external_job_id: url,
                  url,
                  source_id: 'builtin',
                  raw_data: { title, company, url, description: '' },
                });
              } catch {
                /* skip malformed card */
              }
            }

            if (pageNum > 1 && seenUrls.size === prevSize) break;
            if (pageNum < MAX_PAGES) await humanWait(2000, 4000);
          } catch {
            break;
          }
        }
      } finally {
        await context.close();
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const policy = policyChecker(DOMAIN);
      if (policy.status !== 'allowed') {
        return {
          status: 'degraded',
          last_checked: new Date().toISOString(),
          latency_ms: 0,
          error: `Domain policy status: ${policy.status}`,
        };
      }
      return {
        status: 'ok',
        last_checked: new Date().toISOString(),
        latency_ms: 0,
      };
    },

    normalize(raw: RawJobPayload): NormalizedJob {
      const d = raw.raw_data;
      const desc = d['description'] ? String(d['description']).trim() || undefined : undefined;
      return {
        external_job_id: raw.external_job_id,
        source_id: 'builtin',
        title: String(d['title'] ?? ''),
        company: String(d['company'] ?? ''),
        url: raw.url,
        source_site: 'builtin',
        description: desc,
      };
    },
  };
}
