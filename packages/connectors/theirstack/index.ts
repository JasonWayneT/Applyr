import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';
import { db, logActivity } from '../../../server/db.js';

interface TheirStackConfig {
  apiKey?: string;
  searchTerms?: string[];
}

export function createTheirstackConnector(config?: TheirStackConfig): JobConnector {
  const searchTerms = config?.searchTerms ?? ['product manager'];

  function checkCredits(): { allowed: boolean; used: number } {
    try {
      const row = db.prepare('SELECT credits_used_this_month FROM sources WHERE id = ?').get('theirstack') as
        | { credits_used_this_month: number }
        | undefined;
      const count = row?.credits_used_this_month ?? 0;
      if (count >= 200) {
        return { allowed: false, used: count };
      }
      return { allowed: true, used: count };
    } catch {
      return { allowed: true, used: 0 };
    }
  }

  function incrementCredits(count: number) {
    try {
      db.prepare('UPDATE sources SET credits_used_this_month = credits_used_this_month + ? WHERE id = ?').run(count, 'theirstack');
    } catch {
      /* ignore database failure in test */
    }
  }

  function pauseSource() {
    try {
      db.prepare("UPDATE sources SET status = 'paused' WHERE id = ?").run('theirstack');
    } catch {
      /* ignore */
    }
  }

  return {
    sourceId: 'theirstack',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const { allowed, used } = checkCredits();
      if (!allowed) {
        logActivity('ERROR', 'theirstack', 'Credit cap reached: fetch aborted');
        pauseSource();
        return [];
      }

      if (used >= 160) {
        logActivity('WARN', 'theirstack', `Approaching credit cap: ${used}/200 used`);
      }

      // Check key in database connections if not passed
      let apiKey = config?.apiKey;
      if (!apiKey) {
        const row = db.prepare("SELECT value FROM profiles WHERE key = 'api_connections'").get() as { value: string } | undefined;
        if (row?.value) {
          try {
            const conns = JSON.parse(row.value) as Record<string, string>;
            apiKey = conns['theirstackApiKey'] ?? '';
          } catch { /* ignore */ }
        }
      }

      if (!apiKey) {
        logActivity('ERROR', 'theirstack', 'TheirStack API key not configured');
        return [];
      }

      const results: RawJobPayload[] = [];
      const term = searchTerms[0] ?? 'product manager';

      try {
        const res = await fetch('https://api.theirstack.com/v1/jobs/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiKey}`,
          },
          body: JSON.stringify({
            query: term,
            location_country: ['US'],
            limit: 20,
          }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { data?: Record<string, unknown>[] };
        const jobs = data.data ?? [];

        const nextCredits = used + jobs.length;
        if (nextCredits >= 200) {
          logActivity('ERROR', 'theirstack', `Fetch would exceed credit cap (current: ${used}, new: ${jobs.length}). Aborting.`);
          pauseSource();
          return [];
        }

        incrementCredits(jobs.length);

        for (const job of jobs) {
          results.push({
            external_job_id: String(job['id'] ?? ''),
            url: String(job['url'] ?? ''),
            source_id: 'theirstack',
            raw_data: job,
          });
        }
      } catch (err) {
        logActivity('ERROR', 'theirstack', `TheirStack fetch error: ${String(err)}`);
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();
      return {
        status: 'ok',
        last_checked: new Date().toISOString(),
        latency_ms: Date.now() - t0,
      };
    },

    normalize(raw: RawJobPayload): NormalizedJob {
      const d = raw.raw_data;
      const description = d['description']
        ? String(d['description']).replace(/<[^>]+>/g, '').trim().slice(0, 1500) || undefined
        : undefined;

      return {
        external_job_id: raw.external_job_id,
        source_id: 'theirstack',
        title: String(d['job_title'] ?? ''),
        company: String(d['company_name'] ?? ''),
        url: raw.url,
        source_site: 'theirstack',
        location: d['location'] ? String(d['location']) : undefined,
        description,
        posted_at: d['posted_at'] ? String(d['posted_at']) : undefined,
      };
    },
  };
}
