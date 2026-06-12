import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createHimalayasConnector } from './index.js';

const fixture = {
  jobs: [
    {
      id: 'himal-301',
      title: 'Product Manager',
      companyName: 'Acme Corp',
      applicationLink: 'https://himalayas.app/companies/acme/jobs/pm',
      publishedAt: '2026-06-01T00:00:00.000Z',
      description: '<p>Shape the roadmap</p>',
      salaryRange: '$110k - $140k',
    },
    {
      id: 'himal-302',
      title: 'Technical Product Manager',
      companyName: 'Beta Inc',
      applicationLink: 'https://himalayas.app/companies/beta/jobs/tpm',
      publishedAt: '2026-01-15T00:00:00.000Z',
      description: null,
      salaryRange: null,
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

describe('himalayas connector', () => {
  it('fetchJobs returns RawJobPayload array with correct shape', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createHimalayasConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('himal-301');
    expect(jobs[0].source_id).toBe('himalayas');
    expect(jobs[0].url).toBe('https://himalayas.app/companies/acme/jobs/pm');
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createHimalayasConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('himal-301');
  });

  it('normalize maps Himalayas fields to NormalizedJob', () => {
    const connector = createHimalayasConnector();
    const raw: RawJobPayload = {
      external_job_id: 'himal-301',
      url: 'https://himalayas.app/companies/acme/jobs/pm',
      source_id: 'himalayas',
      raw_data: fixture.jobs[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('himalayas');
    expect(normalized.salary_range).toBe('$110k - $140k');
    expect(normalized.description).toBe('Shape the roadmap');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00.000Z');
  });

  it('normalize returns undefined for null optional fields', () => {
    const connector = createHimalayasConnector();
    const raw: RawJobPayload = {
      external_job_id: 'himal-302',
      url: 'https://himalayas.app/companies/beta/jobs/tpm',
      source_id: 'himalayas',
      raw_data: fixture.jobs[1] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
    expect(normalized.salary_range).toBeUndefined();
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createHimalayasConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(503)));
    const connector = createHimalayasConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('DNS failure')));
    const connector = createHimalayasConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('DNS failure');
  });
});
