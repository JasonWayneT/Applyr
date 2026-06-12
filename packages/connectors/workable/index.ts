import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

interface CompanyEntry {
  slug: string;
  name: string;
}

interface WorkableConfig {
  companies?: CompanyEntry[];
  searchTerms?: string[];
}

const DEFAULT_COMPANIES: CompanyEntry[] = [
  { slug: 'linear', name: 'Linear' },
  { slug: 'flight-control', name: 'Flightcontrol' },
];

export function createWorkableConnector(config?: WorkableConfig): JobConnector {
  const companies = config?.companies ?? DEFAULT_COMPANIES;
  const searchTerms = config?.searchTerms ?? ['product manager'];

  return {
    sourceId: 'workable',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];

      for (const company of companies) {
        let data: { jobs?: Record<string, unknown>[] };
        try {
          const res = await fetch(
            `https://www.workable.com/api/accounts/${company.slug}?details=true`,
          );
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          data = (await res.json()) as { jobs?: Record<string, unknown>[] };
        } catch {
          continue;
        }

        for (const job of data.jobs ?? []) {
          const title = String(job['title'] ?? '');
          const titleLower = title.toLowerCase();
          if (!searchTerms.some((t) => titleLower.includes(t.toLowerCase()))) continue;

          results.push({
            external_job_id: `${company.slug}-${String(job['shortcode'] ?? '')}`,
            url: String(job['url'] ?? ''),
            source_id: 'workable',
            raw_data: { ...job, _company_name: company.name, _company_slug: company.slug },
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const slug = companies[0]?.slug ?? 'linear';
      const t0 = Date.now();
      try {
        const res = await fetch(
          `https://www.workable.com/api/accounts/${slug}`,
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
      const rawLoc = d['location'] as Record<string, unknown> | undefined;
      const locationParts = [rawLoc?.['city'], rawLoc?.['region'], rawLoc?.['country']]
        .map((x) => String(x ?? '').trim())
        .filter(Boolean);
      const location = locationParts.join(', ') || undefined;

      const description = d['description']
        ? String(d['description']).replace(/<[^>]+>/g, '').trim().slice(0, 1500) || undefined
        : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'workable',
        title: String(d['title'] ?? ''),
        company: String(d['_company_name'] ?? ''),
        url: raw.url,
        source_site: 'workable',
        location,
        description,
        posted_at: d['published'] ? String(d['published']) : undefined,
      };
    },
  };
}
