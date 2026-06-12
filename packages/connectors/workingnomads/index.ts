import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

export function createWorkingnomadsConnector(): JobConnector {
  return {
    sourceId: 'workingnomads',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const res = await fetch('https://www.workingnomads.com/api/exposed_jobs/', {
        headers: {
          Accept: 'application/json',
          'User-Agent': 'Mozilla/5.0 (compatible; JobAgent/1.0)',
        },
        signal: AbortSignal.timeout(20000),
      });
      if (!res.ok) throw new Error(`Working Nomads HTTP ${res.status}`);
      const postings = (await res.json()) as Record<string, unknown>[];

      const results: RawJobPayload[] = [];
      const seenUrls = new Set<string>();

      for (const p of postings) {
        const url = String(p['url'] ?? '');
        const category = String(p['category_name'] ?? '').toLowerCase();

        if (!category.includes('product') && !category.includes('management')) continue;
        if (!url || seenUrls.has(url)) continue;

        if (since && p['pub_date'] != null) {
          const pub = new Date(String(p['pub_date']));
          if (!isNaN(pub.getTime()) && pub < new Date(since)) continue;
        }

        seenUrls.add(url);
        results.push({
          external_job_id: url,
          url,
          source_id: 'workingnomads',
          raw_data: p,
        });
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();
      try {
        const res = await fetch('https://www.workingnomads.com/api/exposed_jobs/', {
          headers: { Accept: 'application/json' },
          signal: AbortSignal.timeout(10000),
        });
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
      const rawDesc = d['description']
        ? String(d['description']).replace(/<[^>]+>/g, '').trim().slice(0, 1500)
        : '';

      return {
        external_job_id: raw.external_job_id,
        source_id: 'workingnomads',
        title: String(d['title'] ?? ''),
        company: String(d['company_name'] ?? ''),
        url: raw.url,
        source_site: 'workingnomads',
        description: rawDesc || undefined,
        posted_at: d['pub_date'] ? String(d['pub_date']) : undefined,
      };
    },
  };
}
