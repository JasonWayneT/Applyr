import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

interface RemotiveConfig {
  searchTerms?: string[];
}

export function createRemotiveConnector(config?: RemotiveConfig): JobConnector {
  const searchTerms = config?.searchTerms ?? ['product manager'];

  return {
    sourceId: 'remotive',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];
      const seenIds = new Set<string>();

      for (const term of searchTerms) {
        const res = await fetch(
          `https://remotive.com/api/remote-jobs?search=${encodeURIComponent(term)}&limit=50`,
        );
        if (!res.ok) throw new Error(`Remotive HTTP ${res.status}`);
        const data = (await res.json()) as { jobs?: unknown[] };
        const postings = (data.jobs ?? []) as Record<string, unknown>[];

        for (const p of postings) {
          const id = String(p['id'] ?? '');
          if (!id || seenIds.has(id)) continue;

          if (since && p['publication_date'] != null) {
            const pub = new Date(String(p['publication_date']));
            if (!isNaN(pub.getTime()) && pub < new Date(since)) continue;
          }

          seenIds.add(id);
          results.push({
            external_job_id: id,
            url: String(p['url'] ?? ''),
            source_id: 'remotive',
            raw_data: p,
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();
      try {
        const res = await fetch('https://remotive.com/api/remote-jobs?limit=1');
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
        source_id: 'remotive',
        title: String(d['title'] ?? ''),
        company: String(d['company_name'] ?? ''),
        url: raw.url,
        source_site: 'remotive',
        description: rawDesc || undefined,
        salary_range: d['salary'] ? String(d['salary']) : undefined,
        posted_at: d['publication_date'] ? String(d['publication_date']) : undefined,
      };
    },
  };
}
