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

interface GreenhouseConfig {
  companies?: CompanyEntry[];
  searchTerms?: string[];
}

const DEFAULT_COMPANIES: CompanyEntry[] = [
  { slug: 'stripe', name: 'Stripe' },
  { slug: 'shopify', name: 'Shopify' },
  { slug: 'figma', name: 'Figma' },
  { slug: 'notion', name: 'Notion' },
  { slug: 'linear', name: 'Linear' },
];

export function createGreenhouseConnector(config?: GreenhouseConfig): JobConnector {
  const companies = config?.companies ?? DEFAULT_COMPANIES;
  const searchTerms = config?.searchTerms ?? ['product manager'];

  return {
    sourceId: 'greenhouse',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];

      for (const company of companies) {
        let data: { jobs?: Record<string, unknown>[] };
        try {
          const res = await fetch(
            `https://boards-api.greenhouse.io/v1/boards/${company.slug}/jobs?content=true`,
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
            external_job_id: `${company.slug}-${String(job['id'] ?? '')}`,
            url: String(job['absolute_url'] ?? ''),
            source_id: 'greenhouse',
            raw_data: { ...job, _company_name: company.name, _company_slug: company.slug },
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const slug = companies[0]?.slug ?? 'stripe';
      const t0 = Date.now();
      try {
        const res = await fetch(
          `https://boards-api.greenhouse.io/v1/boards/${slug}/jobs`,
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
      const location = (d['location'] as { name?: string } | undefined)?.name;
      const description = d['content']
        ? String(d['content']).replace(/<[^>]+>/g, '').trim().slice(0, 1500) || undefined
        : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'greenhouse',
        title: String(d['title'] ?? ''),
        company: String(d['_company_name'] ?? ''),
        url: raw.url,
        source_site: 'greenhouse',
        location: location || undefined,
        description,
        posted_at: d['updated_at'] ? String(d['updated_at']) : undefined,
      };
    },
  };
}
