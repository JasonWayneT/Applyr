import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

interface RemoteokConfig {
  searchTerms?: string[];
}

export function createRemoteokConnector(config?: RemoteokConfig): JobConnector {
  const searchTerms = config?.searchTerms ?? ['product-manager'];

  return {
    sourceId: 'remoteok',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const tags = searchTerms.slice(0, 2).map((t) => t.toLowerCase().replace(/\s+/g, '-')).join(',');
      const res = await fetch(`https://remoteok.com/api?tags=${encodeURIComponent(tags)}`, {
        headers: { 'User-Agent': 'JobAgent/1.0' },
      });
      if (!res.ok) throw new Error(`RemoteOK HTTP ${res.status}`);
      const data = (await res.json()) as unknown[];

      const results: RawJobPayload[] = [];
      const seenIds = new Set<string>();

      for (const item of data) {
        const p = item as Record<string, unknown>;
        if (!p['id'] || !p['position']) continue;

        const id = String(p['id']);
        if (seenIds.has(id)) continue;

        if (since && p['epoch'] != null) {
          const epoch = Number(p['epoch']);
          if (!isNaN(epoch) && epoch * 1000 < new Date(since).getTime()) continue;
        }

        seenIds.add(id);
        results.push({
          external_job_id: id,
          url: String(p['url'] ?? p['apply_url'] ?? ''),
          source_id: 'remoteok',
          raw_data: p,
        });
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();
      try {
        const res = await fetch('https://remoteok.com/api', {
          headers: { 'User-Agent': 'JobAgent/1.0' },
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
      const salMin = d['salary_min'];
      const salMax = d['salary_max'];
      const salaryRange =
        salMin && salMax
          ? `$${Math.round(Number(salMin) / 1000)}k - $${Math.round(Number(salMax) / 1000)}k`
          : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'remoteok',
        title: String(d['position'] ?? ''),
        company: String(d['company'] ?? ''),
        url: raw.url,
        source_site: 'remoteok',
        description: rawDesc || undefined,
        salary_range: salaryRange,
      };
    },
  };
}
