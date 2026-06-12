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

interface AshbyConfig {
  companies?: CompanyEntry[];
  searchTerms?: string[];
}

const DEFAULT_COMPANIES: CompanyEntry[] = [
  { slug: 'openai', name: 'OpenAI' },
  { slug: 'anthropic', name: 'Anthropic' },
  { slug: 'midjourney', name: 'Midjourney' },
  { slug: 'vercel', name: 'Vercel' },
  { slug: 'figma', name: 'Figma' },
];

export function createAshbyConnector(config?: AshbyConfig): JobConnector {
  const companies = config?.companies ?? DEFAULT_COMPANIES;
  const searchTerms = config?.searchTerms ?? ['product manager'];

  return {
    sourceId: 'ashby',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];

      for (const company of companies) {
        let posts: Record<string, unknown>[];
        try {
          const res = await fetch(
            `https://api.ashbyhq.com/v1/publishing-posts/${company.slug}`,
          );
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          posts = (await res.json()) as Record<string, unknown>[];
        } catch {
          continue;
        }

        for (const post of posts) {
          const title = String(post['title'] ?? '');
          const titleLower = title.toLowerCase();
          if (!searchTerms.some((t) => titleLower.includes(t.toLowerCase()))) continue;

          results.push({
            external_job_id: `${company.slug}-${String(post['id'] ?? '')}`,
            url: String(post['jobPostingUrl'] ?? ''),
            source_id: 'ashby',
            raw_data: { ...post, _company_name: company.name, _company_slug: company.slug },
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const slug = companies[0]?.slug ?? 'openai';
      const t0 = Date.now();
      try {
        const res = await fetch(
          `https://api.ashbyhq.com/v1/publishing-posts/${slug}`,
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
      const location = d['location'] ? String(d['location']) : undefined;
      const description = d['descriptionHtml']
        ? String(d['descriptionHtml']).replace(/<[^>]+>/g, '').trim().slice(0, 1500) || undefined
        : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'ashby',
        title: String(d['title'] ?? ''),
        company: String(d['_company_name'] ?? ''),
        url: raw.url,
        source_site: 'ashby',
        location,
        description,
        posted_at: d['publishedAt'] ? String(d['publishedAt']) : undefined,
      };
    },
  };
}
