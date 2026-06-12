import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createJobscolliderConnector } from './index.js';

const fixture = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Remote Product Jobs — JobsCollider</title>
<item>
<title><![CDATA[Product Manager at Acme Corp]]></title>
<link>https://remotefirstjobs.com/jobs/701-product-manager-acme</link>
<pubDate>Thu, 11 Jun 2026 00:00:00 +0000</pubDate>
<description><![CDATA[<p>Define and ship great products</p>]]></description>
</item>
<item>
<title><![CDATA[Senior Product Owner at Beta Inc]]></title>
<link>https://remotefirstjobs.com/jobs/702-senior-po-beta</link>
<pubDate>Thu, 15 Jan 2026 00:00:00 +0000</pubDate>
<description><![CDATA[]]></description>
</item>
<item>
<title><![CDATA[No Company Separator Title]]></title>
<link>https://remotefirstjobs.com/jobs/703-no-separator</link>
<pubDate>Thu, 11 Jun 2026 00:00:00 +0000</pubDate>
<description></description>
</item>
</channel>
</rss>`;

function mockTextResponse(text: string, ok = true, status = 200): Response {
  return {
    ok,
    status,
    text: async () => text,
    json: async () => ({}),
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('jobscollider connector', () => {
  it('fetchJobs parses RSS and returns correct shape', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createJobscolliderConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(3);
    expect(jobs[0].source_id).toBe('jobscollider');
    expect(jobs[0].url).toBe('https://remotefirstjobs.com/jobs/701-product-manager-acme');
    expect(jobs[0].external_job_id).toBe(jobs[0].url);
  });

  it('fetchJobs parses "Title at Company" format correctly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createJobscolliderConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs[0].raw_data['title']).toBe('Product Manager');
    expect(jobs[0].raw_data['company']).toBe('Acme Corp');
    expect(jobs[1].raw_data['title']).toBe('Senior Product Owner');
    expect(jobs[1].raw_data['company']).toBe('Beta Inc');
  });

  it('fetchJobs falls back to rawTitle and "Unknown" company when no " at " separator', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createJobscolliderConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs[2].raw_data['title']).toBe('No Company Separator Title');
    expect(jobs[2].raw_data['company']).toBe('Unknown');
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createJobscolliderConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    // job 702 pubDate Jan 2026 is stale, jobs 701 and 703 (Jun 2026) pass
    expect(jobs).toHaveLength(2);
    expect(jobs.every((j) => !j.url.includes('702'))).toBe(true);
  });

  it('normalize maps raw_data to NormalizedJob', () => {
    const connector = createJobscolliderConnector();
    const rawData = {
      rawTitle: 'Product Manager at Acme Corp',
      title: 'Product Manager',
      company: 'Acme Corp',
      url: 'https://remotefirstjobs.com/jobs/701-product-manager-acme',
      pubDate: 'Thu, 11 Jun 2026 00:00:00 +0000',
      description: '<p>Define and ship great products</p>',
    };
    const raw: RawJobPayload = {
      external_job_id: rawData.url,
      url: rawData.url,
      source_id: 'jobscollider',
      raw_data: rawData as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('jobscollider');
    expect(normalized.description).toBe('Define and ship great products');
    expect(normalized.posted_at).toBe('Thu, 11 Jun 2026 00:00:00 +0000');
  });

  it('normalize returns undefined description for empty CDATA', () => {
    const connector = createJobscolliderConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://remotefirstjobs.com/jobs/702-senior-po-beta',
      url: 'https://remotefirstjobs.com/jobs/702-senior-po-beta',
      source_id: 'jobscollider',
      raw_data: { title: 'Senior Product Owner', company: 'Beta Inc', url: '', pubDate: '', description: '' },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when feed is reachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createJobscolliderConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse('', false, 503)));
    const connector = createJobscolliderConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ENOTFOUND')));
    const connector = createJobscolliderConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('ENOTFOUND');
  });
});
