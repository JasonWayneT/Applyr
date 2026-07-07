import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';
import { createTheirstackConnector } from './index.js';
import fixtureData from './fixtures/jobs.json';
import { db } from '../../../server/db.js';
import { currentMonthKey } from '../../../shared/domain/theirstackCredits.js';

function mockOk(data: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  } as unknown as Response;
}

function resetTheirstackCredits(used = 0) {
  db.prepare(`
    INSERT OR IGNORE INTO sources (id, name, type, status, credits_used_this_month, credits_reset_at)
    VALUES ('theirstack', 'TheirStack', 'vendor_api', 'active', 0, ?)
  `).run(new Date().toISOString());
  db.prepare(`
    UPDATE sources SET credits_used_this_month = ?, status = 'active', credits_reset_at = ?
    WHERE id = 'theirstack'
  `).run(used, new Date().toISOString());
}

beforeEach(() => {
  resetTheirstackCredits(0);
  db.prepare("DELETE FROM profiles WHERE key = 'theirstack_settings'").run();
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

  it('fetchJobs handles malformed JSON response gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk({ data: "not an array" })));
    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();
    expect(jobs).toEqual([]);
  });

  it('fetchJobs sends configurable limit in request body (default 10)', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(mockOk({ data: [] }));
    vi.stubGlobal('fetch', fetchSpy);

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    await connector.fetchJobs();

    const body = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(body.limit).toBe(10);
  });

  it('fetchJobs uses theirstack_settings fetchLimitPerRun', async () => {
    db.prepare(`
      INSERT OR REPLACE INTO profiles (key, value) VALUES ('theirstack_settings', ?)
    `).run(JSON.stringify({ fetchLimitPerRun: 7 }));

    const fetchSpy = vi.fn().mockResolvedValue(mockOk({ data: [] }));
    vi.stubGlobal('fetch', fetchSpy);

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    await connector.fetchJobs();

    const body = JSON.parse(String((fetchSpy.mock.calls[0][1] as RequestInit).body));
    expect(body.limit).toBe(7);
  });

  it('fetchJobs aborts immediately and returns [] when credit limit (200) is hit', async () => {
    resetTheirstackCredits(200);

    const fetchSpy = vi.fn().mockResolvedValue(mockOk(fixtureData));
    vi.stubGlobal('fetch', fetchSpy);

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(fetchSpy).not.toHaveBeenCalled();

    const row = db.prepare("SELECT status FROM sources WHERE id = 'theirstack'").get() as { status: string };
    expect(row.status).toBe('paused');
  });

  it('fetchJobs clips to remaining credits when near cap', async () => {
    resetTheirstackCredits(199);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(1);

    const row = db.prepare(
      "SELECT credits_used_this_month, status FROM sources WHERE id = 'theirstack'",
    ).get() as { credits_used_this_month: number; status: string };
    expect(row.credits_used_this_month).toBe(200);
    expect(row.status).toBe('paused');
  });

  it('resetTheirstackCreditsIfNewMonth runs before fetch when month rolled over', async () => {
    const priorMonth = new Date();
    priorMonth.setMonth(priorMonth.getMonth() - 1);
    db.prepare(`
      UPDATE sources SET credits_used_this_month = 200, status = 'paused', credits_reset_at = ?
      WHERE id = 'theirstack'
    `).run(priorMonth.toISOString());

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockOk(fixtureData)));

    const connector = createTheirstackConnector({ apiKey: 'test-key' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(2);
    const row = db.prepare(
      "SELECT credits_used_this_month, status FROM sources WHERE id = 'theirstack'",
    ).get() as { credits_used_this_month: number; status: string };
    expect(row.credits_used_this_month).toBe(2);
    expect(row.status).toBe('active');
    expect(currentMonthKey(new Date())).toBe(currentMonthKey());
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
