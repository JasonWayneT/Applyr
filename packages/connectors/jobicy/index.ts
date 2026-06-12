import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

interface JobicyConfig {
  searchTerms?: string[];
}

export function createJobicyConnector(config?: JobicyConfig): JobConnector {
  const searchTerms = config?.searchTerms ?? ['product manager'];

  return {
    sourceId: 'jobicy',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];
      const seenIds = new Set<string>();

      for (const term of searchTerms) {
        const tag = term.toLowerCase().replace(/\s+/g, '+');
        const res = await fetch(
          `https://jobicy.com/api/v2/remote-jobs?count=50&geo=usa&tag=${encodeURIComponent(tag)}`,
          { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; JobAgent/1.0)' } },
        );
        if (!res.ok) throw new Error(`Jobicy HTTP ${res.status}`);
        const data = (await res.json()) as { jobs?: unknown[] };
        const postings = (data.jobs ?? []) as Record<string, unknown>[];

        for (const p of postings) {
          const id = String(p['id'] ?? '');
          if (!id || seenIds.has(id)) continue;

          if (since && p['pubDate'] != null) {
            const pub = new Date(String(p['pubDate']));
            if (!isNaN(pub.getTime()) && pub < new Date(since)) continue;
          }

          seenIds.add(id);
          results.push({
            external_job_id: id,
            url: String(p['url'] ?? ''),
            source_id: 'jobicy',
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
          'https://jobicy.com/api/v2/remote-jobs?count=1&geo=usa&tag=product-manager',
          { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; JobAgent/1.0)' } },
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
      const rawDesc = d['jobDescription']
        ? String(d['jobDescription']).replace(/<[^>]+>/g, '').trim().slice(0, 1500)
        : '';
      const salMin = d['annualSalaryMin'];
      const salMax = d['annualSalaryMax'];
      const salaryRange =
        salMin && salMax
          ? `$${Math.round(Number(salMin) / 1000)}k - $${Math.round(Number(salMax) / 1000)}k`
          : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'jobicy',
        title: String(d['jobTitle'] ?? ''),
        company: String(d['companyName'] ?? ''),
        url: raw.url,
        source_site: 'jobicy',
        description: rawDesc || undefined,
        salary_range: salaryRange,
        posted_at: d['pubDate'] ? String(d['pubDate']) : undefined,
      };
    },
  };
}
