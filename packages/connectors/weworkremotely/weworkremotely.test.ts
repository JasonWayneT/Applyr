import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createWeworkremotelyConnector } from './index.js';

const fixture = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>We Work Remotely: Remote Product Jobs</title>
<item>
<title><![CDATA[Acme Corp: Product Manager]]></title>
<link>https://weworkremotely.com/remote-jobs/view/601-product-manager</link>
<pubDate>Thu, 11 Jun 2026 00:00:00 +0000</pubDate>
<description><![CDATA[<p>Shape the product direction</p>]]></description>
</item>
<item>
<title><![CDATA[Beta Inc: Senior PM]]></title>
<link>https://weworkremotely.com/remote-jobs/view/602-senior-pm</link>
<pubDate>Thu, 01 Jan 2026 00:00:00 +0000</pubDate>
<description><![CDATA[]]></description>
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

describe('weworkremotely connector', () => {
  it('fetchJobs parses RSS and returns RawJobPayload array', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createWeworkremotelyConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe(
      'https://weworkremotely.com/remote-jobs/view/601-product-manager',
    );
    expect(jobs[0].source_id).toBe('weworkremotely');
    expect(jobs[0].url).toBe('https://weworkremotely.com/remote-jobs/view/601-product-manager');
  });

  it('fetchJobs correctly parses company and title from "Company: Title" format', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createWeworkremotelyConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs[0].raw_data['company']).toBe('Acme Corp');
    expect(jobs[0].raw_data['title']).toBe('Product Manager');
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createWeworkremotelyConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].url).toContain('601');
  });

  it('normalize maps raw_data to NormalizedJob', () => {
    const connector = createWeworkremotelyConnector();
    const rawData = {
      rawTitle: 'Acme Corp: Product Manager',
      title: 'Product Manager',
      company: 'Acme Corp',
      url: 'https://weworkremotely.com/remote-jobs/view/601-product-manager',
      pubDate: 'Thu, 11 Jun 2026 00:00:00 +0000',
      description: '<p>Shape the product direction</p>',
    };
    const raw: RawJobPayload = {
      external_job_id: rawData.url,
      url: rawData.url,
      source_id: 'weworkremotely',
      raw_data: rawData as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('weworkremotely');
    expect(normalized.description).toBe('Shape the product direction');
    expect(normalized.posted_at).toBe('Thu, 11 Jun 2026 00:00:00 +0000');
  });

  it('normalize returns undefined description for empty CDATA', () => {
    const connector = createWeworkremotelyConnector();
    const rawData = {
      title: 'Senior PM',
      company: 'Beta Inc',
      url: 'https://weworkremotely.com/remote-jobs/view/602-senior-pm',
      pubDate: 'Thu, 01 Jan 2026 00:00:00 +0000',
      description: '',
    };
    const raw: RawJobPayload = {
      external_job_id: rawData.url,
      url: rawData.url,
      source_id: 'weworkremotely',
      raw_data: rawData as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when feed is reachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse(fixture)));
    const connector = createWeworkremotelyConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockTextResponse('', false, 503)));
    const connector = createWeworkremotelyConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ENOTFOUND')));
    const connector = createWeworkremotelyConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('ENOTFOUND');
  });
});
