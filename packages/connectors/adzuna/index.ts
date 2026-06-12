import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

interface AdzunaConfig {
  appId?: string;
  appKey?: string;
  searchTerms?: string[];
  maxCallsPerRun?: number;
  /** Milliseconds to wait between API calls. Defaults to 3000 (25 req/min free-tier limit). Set to 0 in tests. */
  callGapMs?: number;
}

export function createAdzunaConnector(config?: AdzunaConfig): JobConnector {
  const appId = config?.appId ?? '';
  const appKey = config?.appKey ?? '';
  const searchTerms = config?.searchTerms ?? ['product manager'];
  const maxCallsPerRun = config?.maxCallsPerRun ?? 10;
  const callGapMs = config?.callGapMs ?? 3000;

  return {
    sourceId: 'adzuna',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      if (!appId || !appKey) return [];

      const results: RawJobPayload[] = [];
      const seenUrls = new Set<string>();
      let callCount = 0;

      for (const term of searchTerms) {
        if (callCount >= maxCallsPerRun) break;
        if (callCount > 0 && callGapMs > 0) await new Promise((r) => setTimeout(r, callGapMs));
        callCount++;

        const params = new URLSearchParams({
          app_id: appId,
          app_key: appKey,
          results_per_page: '50',
          what: term,
          'content-type': 'application/json',
        });

        if (since) {
          const diffMs = Date.now() - new Date(since).getTime();
          const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
          params.set('max_days_old', String(diffDays));
        }

        const res = await fetch(`https://api.adzuna.com/v1/api/jobs/us/search/1?${params}`);
        if (!res.ok) throw new Error(`Adzuna HTTP ${res.status}`);
        const data = (await res.json()) as { results?: unknown[] };
        const postings = (data.results ?? []) as Record<string, unknown>[];

        for (const p of postings) {
          const url = String(p['redirect_url'] ?? '');
          if (!url || seenUrls.has(url)) continue;

          seenUrls.add(url);
          results.push({
            external_job_id: url,
            url,
            source_id: 'adzuna',
            raw_data: p,
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();

      if (!appId || !appKey) {
        return {
          status: 'error',
          last_checked: new Date().toISOString(),
          latency_ms: 0,
          error: 'Missing Adzuna credentials (appId / appKey)',
        };
      }

      try {
        const params = new URLSearchParams({
          app_id: appId,
          app_key: appKey,
          results_per_page: '1',
          what: 'product manager',
          'content-type': 'application/json',
        });
        const res = await fetch(`https://api.adzuna.com/v1/api/jobs/us/search/1?${params}`);
        const health: ConnectorHealth = {
          status: res.ok ? 'ok' : 'degraded',
          last_checked: new Date().toISOString(),
          latency_ms: Date.now() - t0,
        };
        if (!res.ok) health.error = `HTTP ${res.status}`;
        return health;
      } catch (err) {
        return {
          status: 'error',
          last_checked: new Date().toISOString(),
          latency_ms: Date.now() - t0,
          error: String(err),
        };
      }
    },

    normalize(raw: RawJobPayload): NormalizedJob {
      const d = raw.raw_data;
      const company = d['company'] as Record<string, unknown> | undefined;
      const rawDesc = d['description']
        ? String(d['description']).replace(/<[^>]+>/g, '').trim().slice(0, 1500)
        : '';
      const salMin = d['salary_min'];
      const salMax = d['salary_max'];
      const salaryRange =
        salMin && salMax
          ? `$${Math.round(Number(salMin) / 1000)}k - $${Math.round(Number(salMax) / 1000)}k`
          : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'adzuna',
        title: String(d['title'] ?? ''),
        company: company?.['display_name'] ? String(company['display_name']) : '',
        url: raw.url,
        source_site: 'adzuna',
        description: rawDesc || undefined,
        salary_range: salaryRange,
        posted_at: d['created'] ? String(d['created']) : undefined,
      };
    },
  };
}
