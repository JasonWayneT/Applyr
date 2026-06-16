import { chromium } from 'playwright-extra';
import stealthPlugin from 'puppeteer-extra-plugin-stealth';
import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

chromium.use(stealthPlugin());

const DOMAIN = 'levels.fyi';
const SEED_URL = 'https://www.levels.fyi/jobs?jobId=1';
const JOB_CAP = 10;

import { passesTargetRoleTitleScope } from '../../../shared/domain/gates.js';

interface LevelsFyiConfig {
  contextDir?: string;
  targetRole?: string;
  searchTerms?: string[];
  /** Injected at runtime from server/middleware/crawlPolicy. Tests pass a mock. */
  policyChecker?: (domain: string) => { status: string };
}

const humanWait = (min = 2000, max = 5000) =>
  new Promise<void>((r) => setTimeout(r, Math.floor(Math.random() * (max - min + 1) + min)));

export function createLevelsFyiConnector(config?: LevelsFyiConfig): JobConnector {
  const contextDir = config?.contextDir ?? 'data/browser_context';
  const policyChecker = config?.policyChecker ?? (() => ({ status: 'unknown' as const }));
  const targetPrefs = {
    targetRole: config?.targetRole?.trim() || 'Product Manager',
    searchTerms: config?.searchTerms?.length ? config.searchTerms : ['Product Manager'],
  };

  return {
    sourceId: 'levelsfyi',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const policy = policyChecker(DOMAIN);
      if (policy.status !== 'allowed') {
        return [];
      }

      const results: RawJobPayload[] = [];

      const context = await chromium.launchPersistentContext(contextDir, {
        headless: true,
        viewport: { width: 1440, height: 900 },
        args: ['--disable-blink-features=AutomationControlled'],
      });

      try {
        const page = context.pages()[0] ?? (await context.newPage());

        await page.goto(SEED_URL, { waitUntil: 'domcontentloaded' });
        await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
        await humanWait(2000, 4000);

        const anchors = await page.$$('a[href*="/jobs/"]');

        for (const anchor of anchors) {
          if (results.length >= JOB_CAP) break;
          try {
            const href = (await anchor.getAttribute('href')) ?? '';
            const fullUrl = href.startsWith('http') ? href : `https://www.levels.fyi${href}`;
            const text = ((await anchor.textContent()) ?? '').trim();

            if (!text || !fullUrl) continue;

            const parts = text.split('\n').map((p) => p.trim()).filter(Boolean);
            const title = parts[0] ?? '';
            const company = parts[1] ?? '';
            if (!title || !company) continue;
            if (!passesTargetRoleTitleScope(title, targetPrefs, 'levelsfyi')) continue;

            results.push({
              external_job_id: fullUrl,
              url: fullUrl,
              source_id: 'levelsfyi',
              raw_data: { title, company, url: fullUrl },
            });
          } catch {
            /* skip malformed anchor */
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
      return {
        external_job_id: raw.external_job_id,
        source_id: 'levelsfyi',
        title: String(d['title'] ?? ''),
        company: String(d['company'] ?? ''),
        url: raw.url,
        source_site: 'levelsfyi',
      };
    },
  };
}
