import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

interface ThemuseConfig {
  category?: string;
}

export function createThemuseConnector(config?: ThemuseConfig): JobConnector {
  const category = config?.category ?? 'Product';

  return {
    sourceId: 'themuse',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];
      const seenIds = new Set<string>();

      for (let page = 0; page <= 1; page++) {
        const res = await fetch(
          `https://www.themuse.com/api/public/jobs?category=${encodeURIComponent(category)}&level=Mid+Level&location=Flexible+%2F+Remote&page=${page}`,
          { headers: { Accept: 'application/json' } },
        );
        if (!res.ok) throw new Error(`The Muse HTTP ${res.status}`);
        const data = (await res.json()) as { results?: unknown[] };
        const postings = (data.results ?? []) as Record<string, unknown>[];

        if (postings.length === 0) break;

        for (const p of postings) {
          const id = String(p['id'] ?? '');
          if (!id || seenIds.has(id)) continue;

          if (since && p['publication_date'] != null) {
            const pub = new Date(String(p['publication_date']));
            if (!isNaN(pub.getTime()) && pub < new Date(since)) continue;
          }

          const refs = p['refs'] as Record<string, unknown> | undefined;
          const url = refs?.['landing_page'] ? String(refs['landing_page']) : '';

          seenIds.add(id);
          results.push({
            external_job_id: id,
            url,
            source_id: 'themuse',
            raw_data: p,
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();
      try {
        const res = await fetch(
          'https://www.themuse.com/api/public/jobs?category=Product&page=0',
          { headers: { Accept: 'application/json' } },
        );
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
      const rawDesc = d['contents']
        ? String(d['contents']).replace(/<[^>]+>/g, '').trim().slice(0, 1500)
        : '';

      return {
        external_job_id: raw.external_job_id,
        source_id: 'themuse',
        title: String(d['name'] ?? ''),
        company: company?.['name'] ? String(company['name']) : '',
        url: raw.url,
        source_site: 'themuse',
        description: rawDesc || undefined,
        posted_at: d['publication_date'] ? String(d['publication_date']) : undefined,
      };
    },
  };
}
