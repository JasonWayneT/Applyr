import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';
import { db, logActivity } from '../../../server/db.js';
import { THEIRSTACK_MAX_PAGE_SIZE } from '../../../shared/domain/theirstackCredits.js';
import {
  checkTheirstackCredits,
  incrementTheirstackCredits,
  loadTheirstackSettings,
  pauseTheirstackSource,
} from '../../../server/services/theirstackCreditLedger.js';

interface TheirStackConfig {
  apiKey?: string;
  searchTerms?: string[];
  /** Local-area location patterns for the "remote OR local" pass (CR pending, 2026-08-26). */
  localAreaTerms?: string[];
}

/** One TheirStack /v1/jobs/search request body. Each job returned costs 1 credit regardless
 *  of which pass found it, so passes must stay narrow (remote-only, or a named local area) —
 *  never an unfiltered US-wide pull the app's own gates would mostly discard anyway. */
interface TheirstackQuery {
  label: string;
  body: Record<string, unknown>;
}

function buildQueries(titleTerms: string[], localAreaTerms: string[]): TheirstackQuery[] {
  const base = {
    job_title_or: titleTerms,
    job_country_code_or: ['US'],
    posted_at_max_age_days: 14,
  };

  const queries: TheirstackQuery[] = [
    {
      label: 'remote',
      body: { ...base, workplace_types_or: ['remote'] },
    },
  ];

  if (localAreaTerms.length) {
    queries.push({
      label: 'local-area',
      // job_location_pattern_or is deprecated in favor of job_location_or (structured location
      // IDs), but it needs no extra catalog lookup for a small local tool — a case-insensitive
      // regex against a handful of San Diego-area names is enough here.
      body: { ...base, job_location_pattern_or: localAreaTerms },
    });
  }

  return queries;
}

async function runQuery(
  apiKey: string,
  query: TheirstackQuery,
  limit: number,
): Promise<Record<string, unknown>[]> {
  if (limit <= 0) return [];

  const res = await fetch('https://api.theirstack.com/v1/jobs/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ ...query.body, limit }),
  });

  if (!res.ok) throw new Error(`HTTP ${res.status} (${query.label})`);
  const data = (await res.json()) as { data?: Record<string, unknown>[] };
  return Array.isArray(data.data) ? data.data : [];
}

export function createTheirstackConnector(config?: TheirStackConfig): JobConnector {
  const searchTerms = config?.searchTerms ?? ['product manager'];
  const localAreaTerms = config?.localAreaTerms ?? [];

  return {
    sourceId: 'theirstack',

    async fetchJobs(): Promise<RawJobPayload[]> {
      const settings = loadTheirstackSettings();
      const { allowed, used, remaining, cap, warnThreshold } = checkTheirstackCredits(settings);

      if (!allowed || remaining <= 0) {
        logActivity('ERROR', 'theirstack', 'Credit cap reached: fetch aborted');
        pauseTheirstackSource();
        return [];
      }

      if (used >= warnThreshold) {
        logActivity('WARN', 'theirstack', `Approaching credit cap: ${used}/${cap} used`);
      }

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

      const titleTerms = searchTerms.length ? searchTerms : ['product manager'];
      const totalLimit = Math.min(settings.fetchLimitPerRun, remaining, THEIRSTACK_MAX_PAGE_SIZE);
      const queries = buildQueries(titleTerms, localAreaTerms);

      // Split the per-run budget across passes so total credits spent this run can't exceed
      // totalLimit — a second (local-area) pass only ever narrows what remote would have spent
      // anyway, it never adds new budget.
      const perQueryLimit = Math.max(1, Math.floor(totalLimit / queries.length));

      const seenIds = new Set<string>();
      const collected: Record<string, unknown>[] = [];
      let creditsSpent = 0;

      for (const query of queries) {
        if (creditsSpent >= totalLimit) break;
        const limit = Math.min(perQueryLimit, totalLimit - creditsSpent);
        try {
          const jobs = await runQuery(apiKey, query, limit);
          // Clip to the requested limit — the API may return more than asked for,
          // but we only budgeted `limit` credits for this pass. TheirStack bills
          // per job returned, so this also prevents overshooting the credit cap.
          const clipped = jobs.slice(0, limit);
          creditsSpent += clipped.length;
          for (const job of clipped) {
            const id = String(job['id'] ?? job['url'] ?? '');
            if (!id || seenIds.has(id)) continue;
            seenIds.add(id);
            collected.push(job);
          }
        } catch (err) {
          logActivity('ERROR', 'theirstack', `TheirStack fetch error (${query.label}): ${String(err)}`);
        }
      }

      if (creditsSpent === 0) return [];

      incrementTheirstackCredits(creditsSpent);

      const nextUsed = used + creditsSpent;
      if (nextUsed >= cap) {
        logActivity('WARN', 'theirstack', `Credit cap reached after fetch: ${nextUsed}/${cap} used`);
        pauseTheirstackSource();
      }

      return collected.map((job) => ({
        external_job_id: String(job['id'] ?? ''),
        url: String(job['url'] ?? ''),
        source_id: 'theirstack',
        raw_data: job,
      }));
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
