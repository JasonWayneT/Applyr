import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createWorkableConnector } from './index.js';
import fixtureData from './fixtures/jobs.json';

const COMPANY = { slug: 'linear', name: 'Linear' };

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

describe('workable connector', () => {
  it('fetchJobs returns PM jobs matching searchTerms', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createWorkableConnector({ companies: [COMPANY], searchTerms: ['Platform Product Manager'] });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('linear-workable-job-1');
    expect(jobs[0].source_id).toBe('workable');
    expect(jobs[0].url).toBe('https://apply.workable.com/linear/j/workable-job-1');
    expect(jobs[0].raw_data['_company_name']).toBe('Linear');
  });

  it('fetchJobs filters out non-PM roles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createWorkableConnector({
      companies: [COMPANY],
      searchTerms: ['product manager'],
    });
    const jobs = await connector.fetchJobs();
    const titles = jobs.map((j) => String(j.raw_data['title']));
    expect(titles.every((t) => t.toLowerCase().includes('product manager'))).toBe(true);
  });

  it('fetchJobs returns [] when jobs array is empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk({ jobs: [] })));
    const connector = createWorkableConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
  });

  it('fetchJobs skips a failed company board and returns partial results', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockError(404))
      .mockResolvedValueOnce(mockOk(fixtureData));
    vi.stubGlobal('fetch', fetchMock);
    const connector = createWorkableConnector({
      companies: [{ slug: 'missing', name: 'Missing Co' }, COMPANY],
    });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].raw_data['_company_name']).toBe('Linear');
  });

  it('normalize maps raw_data to NormalizedJob correctly', () => {
    const connector = createWorkableConnector({ companies: [COMPANY] });
    const raw: RawJobPayload = {
      external_job_id: 'linear-workable-job-1',
      url: 'https://apply.workable.com/linear/j/workable-job-1',
      source_id: 'workable',
      raw_data: {
        ...(fixtureData.jobs[0] as unknown as Record<string, unknown>),
        _company_name: 'Linear',
        _company_slug: 'linear',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Platform Product Manager');
    expect(normalized.company).toBe('Linear');
    expect(normalized.source_site).toBe('workable');
    expect(normalized.location).toBe('San Francisco, California, United States');
    expect(normalized.description).toBe('Own developer tooling and infrastructure platform products.');
    expect(normalized.posted_at).toBe('2026-06-07T10:00:00.000Z');
  });

  it('healthCheck returns ok on 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk({ jobs: [] })));
    const connector = createWorkableConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
  });
});
