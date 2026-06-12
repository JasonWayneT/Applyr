import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

const FEED_URL = 'https://remotefirstjobs.com/remote-product-jobs.rss';

function extractXmlField(item: string, tag: string): string {
  const m =
    item.match(new RegExp(`<${tag}><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`)) ||
    item.match(new RegExp(`<${tag}>([\\s\\S]*?)<\\/${tag}>`));
  return m ? m[1].trim() : '';
}

export function createJobscolliderConnector(): JobConnector {
  return {
    sourceId: 'jobscollider',

    async fetchJobs(since?: string): Promise<RawJobPayload[]> {
      const res = await fetch(FEED_URL);
      if (!res.ok) throw new Error(`JobsCollider HTTP ${res.status}`);
      const xml = await res.text();

      const items = xml.match(/<item>[\s\S]*?<\/item>/g) ?? [];
      const results: RawJobPayload[] = [];
      const seenUrls = new Set<string>();

      for (const item of items) {
        const rawTitle = extractXmlField(item, 'title');
        const url = extractXmlField(item, 'link');
        const pubDate = extractXmlField(item, 'pubDate');
        const description = extractXmlField(item, 'description');

        if (!url || seenUrls.has(url)) continue;

        if (since && pubDate) {
          const pub = new Date(pubDate);
          if (!isNaN(pub.getTime()) && pub < new Date(since)) continue;
        }

        // Title format from this feed: "Job Title at Company Name"
        const lastAt = rawTitle.lastIndexOf(' at ');
        const title = lastAt > 0 ? rawTitle.slice(0, lastAt).trim() : rawTitle;
        const company = lastAt > 0 ? rawTitle.slice(lastAt + 4).trim() : 'Unknown';

        seenUrls.add(url);
        results.push({
          external_job_id: url,
          url,
          source_id: 'jobscollider',
          raw_data: { rawTitle, title, company, url, pubDate, description },
        });
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      const t0 = Date.now();
      try {
        const res = await fetch(FEED_URL);
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
        source_id: 'jobscollider',
        title: String(d['title'] ?? ''),
        company: String(d['company'] ?? ''),
        url: raw.url,
        source_site: 'jobscollider',
        description: rawDesc || undefined,
        posted_at: d['pubDate'] ? String(d['pubDate']) : undefined,
      };
    },
  };
}
