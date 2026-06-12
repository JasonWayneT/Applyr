import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createAdzunaConnector } from './index.js';

const fixture = {
  results: [
    {
      id: 'adzuna-801',
      title: 'Product Manager',
      company: { display_name: 'Acme Corp' },
      redirect_url: 'https://api.adzuna.com/redirect/801',
      created: '2026-06-01T00:00:00Z',
      description: 'Lead cross-functional product teams',
      salary_min: 120000,
      salary_max: 150000,
    },
    {
      id: 'adzuna-802',
      title: 'Senior Product Manager',
      company: { display_name: 'Beta Inc' },
      redirect_url: 'https://api.adzuna.com/redirect/802',
      created: '2026-05-15T00:00:00Z',
      description: '',
      salary_min: null,
      salary_max: null,
    },
  ],
};

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

describe('adzuna connector', () => {
  it('fetchJobs returns empty array without making any request when credentials are missing', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const connector = createAdzunaConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('fetchJobs returns RawJobPayload array with correct shape when credentials are provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createAdzunaConnector({ appId: 'test-id', appKey: 'test-key' });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('https://api.adzuna.com/redirect/801');
    expect(jobs[0].source_id).toBe('adzuna');
  });

  it('fetchJobs deduplicates by redirect_url across search terms', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createAdzunaConnector({
      appId: 'id',
      appKey: 'key',
      searchTerms: ['pm', 'product manager'],
      maxCallsPerRun: 10,
      callGapMs: 0,
    });
    const jobs = await connector.fetchJobs();
    const urls = jobs.map((j) => j.external_job_id);
    expect(new Set(urls).size).toBe(urls.length);
  });

  it('fetchJobs respects maxCallsPerRun cap', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(mockOkResponse({ results: [] }));
    vi.stubGlobal('fetch', fetchSpy);
    const connector = createAdzunaConnector({
      appId: 'id',
      appKey: 'key',
      searchTerms: ['pm', 'product manager', 'product owner'],
      maxCallsPerRun: 2,
      callGapMs: 0,
    });
    await connector.fetchJobs();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it('normalize maps Adzuna fields to NormalizedJob including salary', () => {
    const connector = createAdzunaConnector({ appId: 'id', appKey: 'key' });
    const raw: RawJobPayload = {
      external_job_id: 'https://api.adzuna.com/redirect/801',
      url: 'https://api.adzuna.com/redirect/801',
      source_id: 'adzuna',
      raw_data: fixture.results[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('adzuna');
    expect(normalized.salary_range).toBe('$120k - $150k');
    expect(normalized.description).toBe('Lead cross-functional product teams');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00Z');
  });

  it('normalize returns undefined for missing salary and empty description', () => {
    const connector = createAdzunaConnector({ appId: 'id', appKey: 'key' });
    const raw: RawJobPayload = {
      external_job_id: 'https://api.adzuna.com/redirect/802',
      url: 'https://api.adzuna.com/redirect/802',
      source_id: 'adzuna',
      raw_data: fixture.results[1] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.salary_range).toBeUndefined();
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns error immediately when credentials are missing', async () => {
    const connector = createAdzunaConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toMatch(/credentials/i);
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createAdzunaConnector({ appId: 'id', appKey: 'key' });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(401)));
    const connector = createAdzunaConnector({ appId: 'bad-id', appKey: 'bad-key' });
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/401/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')));
    const connector = createAdzunaConnector({ appId: 'id', appKey: 'key' });
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('connection refused');
  });
});
