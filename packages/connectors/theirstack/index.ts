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

}



export function createTheirstackConnector(config?: TheirStackConfig): JobConnector {

  const searchTerms = config?.searchTerms ?? ['product manager'];



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



      const results: RawJobPayload[] = [];

      const titleTerms = searchTerms.length ? searchTerms : ['product manager'];

      const requestLimit = Math.min(settings.fetchLimitPerRun, remaining, THEIRSTACK_MAX_PAGE_SIZE);



      try {

        const res = await fetch('https://api.theirstack.com/v1/jobs/search', {

          method: 'POST',

          headers: {

            'Content-Type': 'application/json',

            'Authorization': `Bearer ${apiKey}`,

          },

          body: JSON.stringify({

            job_title_or: titleTerms,

            job_country_code_or: ['US'],

            posted_at_max_age_days: 14,

            limit: requestLimit,

          }),

        });



        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = (await res.json()) as { data?: Record<string, unknown>[] };

        if (!data || !Array.isArray(data.data)) {
          return [];
        }

        const jobs = data.data.slice(0, remaining);

        if (jobs.length === 0) {
          return [];
        }



        incrementTheirstackCredits(jobs.length);



        const nextUsed = used + jobs.length;

        if (nextUsed >= cap) {

          logActivity('WARN', 'theirstack', `Credit cap reached after fetch: ${nextUsed}/${cap} used`);

          pauseTheirstackSource();

        }



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

