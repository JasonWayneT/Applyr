import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createThemuseConnector } from './index.js';

const fixture = {
  results: [
    {
      id: 401,
      name: 'Product Manager',
      company: { name: 'Acme Corp', id: 10 },
      refs: { landing_page: 'https://www.themuse.com/jobs/acme/pm-401' },
      publication_date: '2026-06-01T00:00:00.000Z',
      contents: '<p>Drive our product vision</p>',
    },
    {
      id: 402,
      name: 'Senior Product Manager',
      company: { name: 'Beta Inc', id: 11 },
      refs: { landing_page: 'https://www.themuse.com/jobs/beta/spm-402' },
      publication_date: '2026-02-01T00:00:00.000Z',
      contents: null,
    },
  ],
};

const emptyFixture = { results: [] };

function mockOkResponse(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
    text: async () => JSON.stringify(data),
  } as unknown as Response;
}

function mockErrorResponse(status: number): Response {
  return { ok: false, status, json: async () => ({}), text: async () => '' } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('themuse connector', () => {
  it('fetchJobs returns RawJobPayload array with correct shape', async () => {
    // page 0 returns results, page 1 returns empty (stops pagination)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockOkResponse(fixture))
      .mockResolvedValueOnce(mockOkResponse(emptyFixture));
    vi.stubGlobal('fetch', fetchMock);
    const connector = createThemuseConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('401');
    expect(jobs[0].source_id).toBe('themuse');
    expect(jobs[0].url).toBe('https://www.themuse.com/jobs/acme/pm-401');
  });

  it('fetchJobs stops paginating when a page returns empty results', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockOkResponse(emptyFixture));
    vi.stubGlobal('fetch', fetchMock);
    const connector = createThemuseConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn()
        .mockResolvedValueOnce(mockOkResponse(fixture))
        .mockResolvedValueOnce(mockOkResponse(emptyFixture)),
    );
    const connector = createThemuseConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('401');
  });

  it('normalize maps Muse fields to NormalizedJob', () => {
    const connector = createThemuseConnector();
    const raw: RawJobPayload = {
      external_job_id: '401',
      url: 'https://www.themuse.com/jobs/acme/pm-401',
      source_id: 'themuse',
      raw_data: fixture.results[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('themuse');
    expect(normalized.description).toBe('Drive our product vision');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00.000Z');
  });

  it('normalize returns undefined description when contents is null', () => {
    const connector = createThemuseConnector();
    const raw: RawJobPayload = {
      external_job_id: '402',
      url: 'https://www.themuse.com/jobs/beta/spm-402',
      source_id: 'themuse',
      raw_data: fixture.results[1] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createThemuseConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(429)));
    const connector = createThemuseConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/429/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')));
    const connector = createThemuseConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('connection refused');
  });
});
