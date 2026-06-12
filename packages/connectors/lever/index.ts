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

interface LeverConfig {
  companies?: CompanyEntry[];
  searchTerms?: string[];
}

const DEFAULT_COMPANIES: CompanyEntry[] = [
  { slug: 'netflix', name: 'Netflix' },
  { slug: 'dropbox', name: 'Dropbox' },
  { slug: 'twilio', name: 'Twilio' },
  { slug: 'zendesk', name: 'Zendesk' },
];

export function createLeverConnector(config?: LeverConfig): JobConnector {
  const companies = config?.companies ?? DEFAULT_COMPANIES;
  const searchTerms = config?.searchTerms ?? ['product manager'];

  return {
    sourceId: 'lever',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];

      for (const company of companies) {
        let postings: Record<string, unknown>[];
        try {
          const res = await fetch(
            `https://api.lever.co/v0/postings/${company.slug}?mode=json`,
          );
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          postings = (await res.json()) as Record<string, unknown>[];
        } catch {
          continue;
        }

        for (const posting of postings) {
          if (posting['state'] !== 'published') continue;

          const title = String(posting['text'] ?? '');
          const titleLower = title.toLowerCase();
          if (!searchTerms.some((t) => titleLower.includes(t.toLowerCase()))) continue;

          results.push({
            external_job_id: String(posting['id'] ?? ''),
            url: String(posting['hostedUrl'] ?? ''),
            source_id: 'lever',
            raw_data: { ...posting, _company_name: company.name, _company_slug: company.slug },
          });
        }
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const slug = companies[0]?.slug ?? 'netflix';
      const t0 = Date.now();
      try {
        const res = await fetch(
          `https://api.lever.co/v0/postings/${slug}?mode=json`,
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
      const categories = d['categories'] as Record<string, unknown> | undefined;
      const location = categories?.['location'] ? String(categories['location']) : undefined;
      const description = d['description']
        ? String(d['description']).replace(/<[^>]+>/g, '').trim().slice(0, 1500) || undefined
        : undefined;
      const createdAtMs = d['createdAt'];
      const posted_at =
        typeof createdAtMs === 'number' ? new Date(createdAtMs).toISOString() : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'lever',
        title: String(d['text'] ?? ''),
        company: String(d['_company_name'] ?? ''),
        url: raw.url,
        source_site: 'lever',
        location,
        description,
        posted_at,
      };
    },
  };
}
