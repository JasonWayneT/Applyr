import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createAshbyConnector } from './index.js';
import fixtureData from './fixtures/posts.json';

const COMPANY = { slug: 'figma', name: 'Figma' };

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

describe('ashby connector', () => {
  it('fetchJobs returns PM jobs matching searchTerms', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createAshbyConnector({ companies: [COMPANY], searchTerms: ['Technical Product Manager'] });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(1);
    expect(jobs[0].external_job_id).toBe('figma-ashby-post-1');
    expect(jobs[0].source_id).toBe('ashby');
    expect(jobs[0].url).toBe('https://jobs.ashbyhq.com/figma/ashby-post-1');
    expect(jobs[0].raw_data['_company_name']).toBe('Figma');
  });

  it('fetchJobs filters out non-PM roles', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createAshbyConnector({
      companies: [COMPANY],
      searchTerms: ['product manager'],
    });
    const jobs = await connector.fetchJobs();
    const titles = jobs.map((j) => String(j.raw_data['title']));
    expect(titles.every((t) => t.toLowerCase().includes('product manager'))).toBe(true);
  });

  it('fetchJobs returns [] when posts array is empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk([])));
    const connector = createAshbyConnector({ companies: [COMPANY] });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(0);
  });

  it('fetchJobs skips a failed company board and returns partial results', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(mockError(404))
      .mockResolvedValueOnce(mockOk(fixtureData));
    vi.stubGlobal('fetch', fetchMock);
    const connector = createAshbyConnector({
      companies: [{ slug: 'missing', name: 'Missing Co' }, COMPANY],
    });
    const jobs = await connector.fetchJobs();
    expect(jobs).toHaveLength(1);
    expect(jobs[0].raw_data['_company_name']).toBe('Figma');
  });

  it('normalize maps raw_data to NormalizedJob correctly', () => {
    const connector = createAshbyConnector({ companies: [COMPANY] });
    const raw: RawJobPayload = {
      external_job_id: 'figma-ashby-post-1',
      url: 'https://jobs.ashbyhq.com/figma/ashby-post-1',
      source_id: 'ashby',
      raw_data: {
        ...(fixtureData[0] as unknown as Record<string, unknown>),
        _company_name: 'Figma',
        _company_slug: 'figma',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Technical Product Manager');
    expect(normalized.company).toBe('Figma');
    expect(normalized.source_site).toBe('ashby');
    expect(normalized.location).toBe('Remote - United States');
    expect(normalized.description).toBe('Drive backend and API platform products.');
    expect(normalized.posted_at).toBe('2026-06-05T12:00:00.000Z');
  });

  it('healthCheck returns ok on 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk([])));
    const connector = createAshbyConnector({ companies: [COMPANY] });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
  });
});
