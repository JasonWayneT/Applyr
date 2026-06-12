import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createGreenhouseConnector } from './index.js';
import fixtureData from './fixtures/jobs.json';

const COMPANY = { slug: 'stripe', name: 'Stripe' };

function mockOk(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  } as unknown as Response;
}

function mockError(status: number): Response {
  return { ok: false, status, json: async () => ({}) } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('greenhouse connector', () => {
  it('fetchJobs returns PM jobs matching searchTerms', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('stripe-4001234');
    expect(jobs[0].source_id).toBe('greenhouse');
    expect(jobs[0].url).toBe('https://boards.greenhouse.io/stripe/jobs/4001234');
    expect(jobs[0].raw_data['_company_name']).toBe('Stripe');
  });

  it('fetchJobs filters out non-PM roles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createGreenhouseConnector({
      companies: [COMPANY],
      searchTerms: ['product manager'],
    });
    const jobs = await connector.fetchJobs();
    const titles = jobs.map((j) => String(j.raw_data['title']));
    expect(titles.every((t) => t.toLowerCase().includes('product manager'))).toBe(true);
  });

  it('fetchJobs returns [] when jobs array is empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk({ jobs: [] })));
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
  });

  it('fetchJobs skips a failed company board and returns partial results', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockError(404))
      .mockResolvedValueOnce(mockOk(fixtureData));
    vi.stubGlobal('fetch', fetchMock);
    const connector = createGreenhouseConnector({
      companies: [{ slug: 'missing', name: 'Missing Co' }, COMPANY],
    });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].raw_data['_company_name']).toBe('Stripe');
  });

  it('fetchJobs returns [] when all company boards fail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')));
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
  });

  it('normalize maps raw_data to NormalizedJob correctly', () => {
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const raw: RawJobPayload = {
      external_job_id: 'stripe-4001234',
      url: 'https://boards.greenhouse.io/stripe/jobs/4001234',
      source_id: 'greenhouse',
      raw_data: {
        ...(fixtureData.jobs[0] as unknown as Record<string, unknown>),
        _company_name: 'Stripe',
        _company_slug: 'stripe',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Senior Product Manager');
    expect(normalized.company).toBe('Stripe');
    expect(normalized.source_site).toBe('greenhouse');
    expect(normalized.location).toBe('Remote - US');
    expect(normalized.description).toBe('Lead product strategy for the core payments platform.');
    expect(normalized.posted_at).toBe('2026-06-01T10:00:00.000Z');
  });

  it('normalize returns undefined for missing optional fields', () => {
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const raw: RawJobPayload = {
      external_job_id: 'stripe-9999',
      url: 'https://boards.greenhouse.io/stripe/jobs/9999',
      source_id: 'greenhouse',
      raw_data: { title: 'PM', _company_name: 'Stripe' },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.location).toBeUndefined();
    expect(normalized.description).toBeUndefined();
    expect(normalized.posted_at).toBeUndefined();
  });

  it('healthCheck returns ok on 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk({ jobs: [] })));
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.last_checked).toBeDefined();
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockError(503)));
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('timeout')));
    const connector = createGreenhouseConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('timeout');
  });
});
