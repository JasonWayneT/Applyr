import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createWorkingnomadsConnector } from './index.js';

// Mixed-category fixture — only product/management rows should pass through
const fixture = [
  {
    title: 'Product Manager',
    company_name: 'Acme Corp',
    url: 'https://www.workingnomads.com/jobs/product-manager-acme',
    category_name: 'Product Management',
    pub_date: '2026-06-01T00:00:00Z',
    description: '<p>Own the product roadmap</p>',
  },
  {
    title: 'Sales Executive',
    company_name: 'Gamma Ltd',
    url: 'https://www.workingnomads.com/jobs/sales-exec-gamma',
    category_name: 'Sales',
    pub_date: '2026-06-05T00:00:00Z',
    description: '<p>Close deals</p>',
  },
  {
    title: 'Technical Product Manager',
    company_name: 'Beta Inc',
    url: 'https://www.workingnomads.com/jobs/tpm-beta',
    category_name: 'Product',
    pub_date: '2026-01-10T00:00:00Z',
    description: '',
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
  return { ok: false, status, json: async () => [], text: async () => '' } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('workingnomads connector', () => {
  it('fetchJobs includes only product/management category rows', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createWorkingnomadsConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(2);
    expect(jobs.map((j) => j.external_job_id)).not.toContain(
      'https://www.workingnomads.com/jobs/sales-exec-gamma',
    );
  });

  it('fetchJobs uses URL as external_job_id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createWorkingnomadsConnector();
    const jobs = await connector.fetchJobs();
    expect(jobs[0].external_job_id).toBe(
      'https://www.workingnomads.com/jobs/product-manager-acme',
    );
    expect(jobs[0].source_id).toBe('workingnomads');
  });

  it('fetchJobs filters stale jobs when since is provided', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createWorkingnomadsConnector();
    const jobs = await connector.fetchJobs('2026-04-01T00:00:00.000Z');
    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toContain('product-manager-acme');
  });

  it('normalize maps Working Nomads fields to NormalizedJob', () => {
    const connector = createWorkingnomadsConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://www.workingnomads.com/jobs/product-manager-acme',
      url: 'https://www.workingnomads.com/jobs/product-manager-acme',
      source_id: 'workingnomads',
      raw_data: fixture[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_site).toBe('workingnomads');
    expect(normalized.description).toBe('Own the product roadmap');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00Z');
  });

  it('normalize returns undefined for empty description', () => {
    const connector = createWorkingnomadsConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://www.workingnomads.com/jobs/tpm-beta',
      url: 'https://www.workingnomads.com/jobs/tpm-beta',
      source_id: 'workingnomads',
      raw_data: fixture[2] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
  });

  it('healthCheck returns ok when API responds 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOkResponse(fixture)));
    const connector = createWorkingnomadsConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockErrorResponse(503)));
    const connector = createWorkingnomadsConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('ETIMEDOUT')));
    const connector = createWorkingnomadsConnector();
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('ETIMEDOUT');
  });
});
