import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createRemoteokConnector } from './index.js';

// RemoteOK returns an array; first element is a legal notice without id/position
const fixture = [
  { legal: 'This data is provided for informational purposes only.' },
  {
    id: 201,
    position: 'Product Manager',
    company: 'Acme Corp',
    url: 'https://remoteok.com/jobs/201',
    apply_url: 'https://acme.com/apply/201',
    epoch: 1748736000, // 2025-06-01 (recent)
    description: '<p>Drive product roadmap</p>',
    salary_min: 120000,
    salary_max: 150000,
  },
  {
    id: 202,
    position: 'Senior PM',
    company: 'Beta Inc',
    url: 'https://remoteok.com/jobs/202',
    apply_url: '',
    epoch: 1704067200, // 2024-01-01 (stale)
    description: '',
    salary_min: null,
    salary_max: null,
  },
];

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

describe('remoteok connector', () => {
  it('fetchJobs skips the legal notice entry and returns valid jobs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemoteokConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('201');
    expect(jobs[0].source_id).toBe('remoteok');
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemoteokConnector();
    const jobs = await connector.fetchJobs('2025-01-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('201');
  });

  it('normalize maps position/company fields to NormalizedJob', () => {
    const connector = createRemoteokConnector();
    const raw: RawJobPayload = {
      external_job_id: '201',
      url: 'https://remoteok.com/jobs/201',
      source_id: 'remoteok',
      raw_data: fixture[1] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('remoteok');
    expect(normalized.salary_range).toBe('$120k - $150k');
    expect(normalized.description).toBe('Drive product roadmap');
  });

  it('normalize returns undefined for missing salary and empty description', () => {
    const connector = createRemoteokConnector();
    const raw: RawJobPayload = {
      external_job_id: '202',
      url: 'https://remoteok.com/jobs/202',
      source_id: 'remoteok',
      raw_data: fixture[2] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.salary_range).toBeUndefined();
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createRemoteokConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(429)));
    const connector = createRemoteokConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/429/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('timeout')));
    const connector = createRemoteokConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('timeout');
  });
});
