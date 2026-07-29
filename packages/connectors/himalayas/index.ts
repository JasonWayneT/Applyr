import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';
import {
  passesTargetRoleTitleScope,
  type TargetRolePrefs,
} from '../../../shared/domain/gates.js';

interface HimalayasConfig {
  searchTerms?: string[];
  titleScopePrefs?: TargetRolePrefs;
}

export function createHimalayasConnector(config?: HimalayasConfig): JobConnector {
  const searchTerms = config?.searchTerms ?? ['product manager'];
  const titleScopePrefs = config?.titleScopePrefs;

  return {
    sourceId: 'himalayas',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const results: RawJobPayload[] = [];
      const seenIds = new Set<string>();

      for (const term of searchTerms) {
        const slug = term.toLowerCase().replace(/\s+/g, '-');
        const res = await fetch(
          `https://himalayas.app/jobs/api?roles=${encodeURIComponent(slug)}&limit=50`,
          { headers: { Accept: 'application/json' } },
        );
        if (!res.ok) throw new Error(`Himalayas HTTP ${res.status}`);
        const data = (await res.json()) as { jobs?: unknown[] };
        const postings = (data.jobs ?? []) as Record<string, unknown>[];

        for (const p of postings) {
          const id = String(p['id'] ?? '');
          if (!id || seenIds.has(id)) continue;

          const title = String(p['title'] ?? '').trim();
          if (titleScopePrefs && !passesTargetRoleTitleScope(title, titleScopePrefs, 'himalayas')) {
            continue;
          }

          if (since && p['publishedAt'] != null) {
            const pub = new Date(String(p['publishedAt']));
            if (!isNaN(pub.getTime()) && pub < new Date(since)) continue;
          }

          seenIds.add(id);
          results.push({
            external_job_id: id,
            url: String(p['applicationLink'] ?? ''),
            source_id: 'himalayas',
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
          'https://himalayas.app/jobs/api?roles=product-manager&limit=1',
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
      const rawDesc = d['description']
        ? String(d['description']).replace(/<[^>]+>/g, '').trim().slice(0, 1500)
        : '';

      return {
        external_job_id: raw.external_job_id,
        source_id: 'himalayas',
        title: String(d['title'] ?? ''),
        company: String(d['companyName'] ?? ''),
        url: raw.url,
        source_site: 'himalayas',
        description: rawDesc || undefined,
        salary_range: d['salaryRange'] ? String(d['salaryRange']) : undefined,
        posted_at: d['publishedAt'] ? String(d['publishedAt']) : undefined,
      };
    },
  };
}
