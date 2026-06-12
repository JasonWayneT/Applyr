import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createTheirstackConnector } from './index.js';
import fixtureData from './fixtures/jobs.json';
import { db } from '../../../server/db.js';

function mockOk(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  } as unknown as Response;
}

beforeEach(() => {
  try {
    db.prepare("INSERT OR IGNORE INTO sources (id, name, type, status, credits_used_this_month) VALUES ('theirstack', 'TheirStack', 'vendor_api', 'active', 0)").run();
    db.prepare("UPDATE sources SET credits_used_this_month = 0, status = 'active' WHERE id = 'theirstack'").run();
  } catch { /* exists */ }
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('theirstack connector', () => {
  it('fetchJobs returns jobs when under credit limit', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));
    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(2);
    expect(jobs[0].external_job_id).toBe('ts-job-1');
  });

  it('fetchJobs aborts immediately and returns [] when credit limit (200) is hit', async () => {
    db.prepare("UPDATE sources SET credits_used_this_month = 200 WHERE id = 'theirstack'").run();

    const fetchSpy = vi.fn().mockResolvedValue(mockOk(fixtureData));
    vi.stubGlobal('fetch', fetchSpy);

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(fetchSpy).not.toHaveBeenCalled();

    const row = db.prepare("SELECT status FROM sources WHERE id = 'theirstack'").get() as { status: string };
    expect(row.status).toBe('paused');
  });

  it('fetchJobs aborts and returns [] if the incoming batch would exceed 200', async () => {
    db.prepare("UPDATE sources SET credits_used_this_month = 199 WHERE id = 'theirstack'").run();

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);

    const row = db.prepare("SELECT status FROM sources WHERE id = 'theirstack'").get() as { status: string };
    expect(row.status).toBe('paused');
  });

  it('normalize maps raw_data to NormalizedJob correctly', () => {
    const connector = createTheirstackConnector();
    const raw: RawJobPayload = {
      external_job_id: 'ts-job-1',
      url: 'https://theirstack.com/jobs/ts-job-1',
      source_id: 'theirstack',
      raw_data: fixtureData.data[0] as unknown as Record<string, unknown>,
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager Growth');
    expect(normalized.company).toBe('Stripe');
    expect(normalized.source_site).toBe('theirstack');
    expect(normalized.location).toBe('Remote, US');
    expect(normalized.description).toBe('Focus on Stripe growth loops and activation metrics.');
    expect(normalized.posted_at).toBe('2026-06-09T00:00:00.000Z');
  });
});
