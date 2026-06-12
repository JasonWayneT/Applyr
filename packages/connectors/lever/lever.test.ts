import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createLeverConnector } from './index.js';
import fixtureData from './fixtures/postings.json';

const COMPANY = { slug: 'netflix', name: 'Netflix' };

function mockOk(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  } as unknown as Response;
}

function mockError(status: number): Response {
  return { ok: false, status, json: async () => [] } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('lever connector', () => {
  it('fetchJobs returns PM jobs matching searchTerms', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('abc-123-def-456');
    expect(jobs[0].source_id).toBe('lever');
    expect(jobs[0].url).toBe('https://jobs.lever.co/netflix/abc-123-def-456');
    expect(jobs[0].raw_data['_company_name']).toBe('Netflix');
  });

  it('fetchJobs filters out non-PM roles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createLeverConnector({
      companies: [COMPANY],
      searchTerms: ['product manager'],
    });
    const jobs = await connector.fetchJobs();
    const titles = jobs.map((j) => String(j.raw_data['text']));
    expect(titles.every((t) => t.toLowerCase().includes('product manager'))).toBe(true);
  });

  it('fetchJobs returns [] on empty response array', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk([])));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
  });

  it('fetchJobs skips a failed company and returns partial results', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockError(404))
      .mockResolvedValueOnce(mockOk(fixtureData));
    vi.stubGlobal('fetch', fetchMock);
    const connector = createLeverConnector({
      companies: [{ slug: 'missing', name: 'Missing Co' }, COMPANY],
    });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].raw_data['_company_name']).toBe('Netflix');
  });

  it('fetchJobs returns [] when all company boards fail', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
  });

  it('fetchJobs skips non-published postings', async () => {
    const withDraft = [
      { ...fixtureData[0], state: 'published' },
      { ...fixtureData[0], id: 'draft-id', text: 'Product Manager Draft', state: 'draft' },
    ];
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(withDraft)));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs.every((j) => j.external_job_id !== 'draft-id')).toBe(true);
  });

  it('normalize maps raw_data to NormalizedJob correctly', () => {
    const connector = createLeverConnector({ companies: [COMPANY] });
    const raw: RawJobPayload = {
      external_job_id: 'abc-123-def-456',
      url: 'https://jobs.lever.co/netflix/abc-123-def-456',
      source_id: 'lever',
      raw_data: {
        ...(fixtureData[0] as unknown as Record<string, unknown>),
        _company_name: 'Netflix',
        _company_slug: 'netflix',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager, Platform');
    expect(normalized.company).toBe('Netflix');
    expect(normalized.source_site).toBe('lever');
    expect(normalized.location).toBe('Remote, United States');
    expect(normalized.description).toBe('Join the Platform team as a Product Manager.');
    expect(normalized.posted_at).toBe('2026-06-01T00:00:00.000Z');
  });

  it('normalize returns undefined for missing optional fields', () => {
    const connector = createLeverConnector({ companies: [COMPANY] });
    const raw: RawJobPayload = {
      external_job_id: 'minimal-id',
      url: 'https://jobs.lever.co/netflix/minimal-id',
      source_id: 'lever',
      raw_data: { text: 'Product Manager', _company_name: 'Netflix' },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.location).toBeUndefined();
    expect(normalized.description).toBeUndefined();
    expect(normalized.posted_at).toBeUndefined();
  });

  it('healthCheck returns ok on 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk([])));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
    expect(health.last_checked).toBeDefined();
    expect(health.latency_ms).toBeGreaterThanOrEqual(0);
  });

  it('healthCheck returns degraded on non-200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockError(503)));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/503/);
  });

  it('healthCheck returns error on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connection refused')));
    const connector = createLeverConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('error');
    expect(health.error).toContain('connection refused');
  });
});
