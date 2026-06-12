import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createJobicyConnector } from './index.js';

const fixture = {
  jobs: [
    {
      id: 501,
      jobTitle: 'Product Manager',
      companyName: 'Acme Corp',
      url: 'https://jobicy.com/jobs/501-product-manager',
      pubDate: '2026-06-01T00:00:00.000Z',
      jobDescription: '<p>Own the product lifecycle</p>',
      annualSalaryMin: 110000,
      annualSalaryMax: 140000,
    },
    {
      id: 502,
      jobTitle: 'Growth Product Manager',
      companyName: 'Beta Inc',
      url: 'https://jobicy.com/jobs/502-growth-pm',
      pubDate: '2026-01-10T00:00:00.000Z',
      jobDescription: '',
      annualSalaryMin: null,
      annualSalaryMax: null,
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

describe('jobicy connector', () => {
  it('fetchJobs returns RawJobPayload array with correct shape', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createJobicyConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('501');
    expect(jobs[0].source_id).toBe('jobicy');
    expect(jobs[0].url).toBe('https://jobicy.com/jobs/501-product-manager');
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createJobicyConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('501');
  });

  it('normalize maps Jobicy fields to NormalizedJob', () => {
    const connector = createJobicyConnector();
    const raw: RawJobPayload = {
      external_job_id: '501',
      url: 'https://jobicy.com/jobs/501-product-manager',
      source_id: 'jobicy',
      raw_data: fixture.jobs[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('jobicy');
    expect(normalized.salary_range).toBe('$110k - $140k');
    expect(normalized.description).toBe('Own the product lifecycle');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00.000Z');
  });

  it('normalize returns undefined for null salary and empty description', () => {
    const connector = createJobicyConnector();
    const raw: RawJobPayload = {
      external_job_id: '502',
      url: 'https://jobicy.com/jobs/502-growth-pm',
      source_id: 'jobicy',
      raw_data: fixture.jobs[1] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.salary_range).toBeUndefined();
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createJobicyConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(503)));
    const connector = createJobicyConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ECONNREFUSED')));
    const connector = createJobicyConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('ECONNREFUSED');
  });
});
