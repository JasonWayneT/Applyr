import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createRemotiveConnector } from './index.js';

const fixture = {
  jobs: [
    {
      id: 101,
      title: 'Product Manager',
      company_name: 'Acme Corp',
      url: 'https://remotive.com/job/101',
      publication_date: '2026-06-01T00:00:00.000Z',
      salary: '$120k - $150k',
      description: '<p>Lead product strategy</p>',
    },
    {
      id: 102,
      title: 'Senior Product Manager',
      company_name: 'Beta Inc',
      url: 'https://remotive.com/job/102',
      publication_date: '2026-01-01T00:00:00.000Z',
      salary: null,
      description: '',
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

describe('remotive connector', () => {
  it('fetchJobs returns RawJobPayload array with correct shape', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemotiveConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('101');
    expect(jobs[0].source_id).toBe('remotive');
    expect(jobs[0].url).toBe('https://remotive.com/job/101');
    expect(jobs[0].raw_data).toBeDefined();
  });

  it('fetchJobs deduplicates results across search terms', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemotiveConnector({ searchTerms: ['pm', 'product manager'] });
    const jobs = await connector.fetchJobs();
    const ids = jobs.map((j) => j.external_job_id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemotiveConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('101');
  });

  it('normalize maps raw_data to NormalizedJob correctly', () => {
    const connector = createRemotiveConnector();
    const raw: RawJobPayload = {
      external_job_id: '101',
      url: 'https://remotive.com/job/101',
      source_id: 'remotive',
      raw_data: fixture.jobs[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('remotive');
    expect(normalized.salary_range).toBe('$120k - $150k');
    expect(normalized.description).toBe('Lead product strategy');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00.000Z');
  });

  it('normalize returns undefined for missing optional fields', () => {
    const connector = createRemotiveConnector();
    const raw: RawJobPayload = {
      external_job_id: '102',
      url: 'https://remotive.com/job/102',
      source_id: 'remotive',
      raw_data: fixture.jobs[1] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.salary_range).toBeUndefined();
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemotiveConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.last_checked).toBeDefined();
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(503)));
    const connector = createRemotiveConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')));
    const connector = createRemotiveConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('network error');
  });
});
