import { describe, it, expect, vi, afterEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';

vi.mock('fs', async (importOriginal) => {
  const actual = await importOriginal<typeof import('fs')>();
  return { ...actual, default: { ...actual, existsSync: vi.fn() } };
});

vi.mock('child_process', () => ({
  spawn: vi.fn(),
}));

const { createOpenPostingsConnector } = await import('./index.js');
const fs = (await import('fs')).default;

afterEach(() => {
  vi.clearAllMocks();
});

describe('openpostings connector', () => {
  it('exports sourceId as openpostings', () => {
    const connector = createOpenPostingsConnector();
    expect(connector.sourceId).toBe('openpostings');
  });

  it('fetchJobs returns [] without spawning a process when dir does not exist', async () => {
    const { spawn } = await import('child_process');
    vi.mocked(fs.existsSync).mockReturnValue(false);

    const connector = createOpenPostingsConnector({ openPostingsDir: '/nonexistent/path' });
    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(spawn).not.toHaveBeenCalled();
  });

  it('healthCheck returns error when dir does not exist', async () => {
    vi.mocked(fs.existsSync).mockReturnValue(false);

    const connector = createOpenPostingsConnector({ openPostingsDir: '/nonexistent/path' });
    const health = await connector.healthCheck();

    expect(health.status).toBe('error');
    expect(health.error).toMatch(/not found/i);
  });

  it('healthCheck returns ok when dir exists', async () => {
    vi.mocked(fs.existsSync).mockReturnValue(true);

    const connector = createOpenPostingsConnector({ openPostingsDir: '/valid/path' });
    const health = await connector.healthCheck();

    expect(health.status).toBe('ok');
  });

  it('normalize maps OpenPostings fields to NormalizedJob shape', () => {
    const connector = createOpenPostingsConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://company.com/jobs/123',
      url: 'https://company.com/jobs/123',
      source_id: 'openpostings',
      raw_data: {
        position_name: 'Senior Product Manager',
        company_name: 'Stripe',
        job_posting_url: 'https://company.com/jobs/123',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Senior Product Manager');
    expect(normalized.company).toBe('Stripe');
    expect(normalized.source_id).toBe('openpostings');
    expect(normalized.source_site).toBe('openpostings');
    expect(normalized.url).toBe('https://company.com/jobs/123');
  });

  it('normalize returns undefined description when absent', () => {
    const connector = createOpenPostingsConnector();
    const raw: RawJobPayload = {
      external_job_id: 'id',
      url: '',
      source_id: 'openpostings',
      raw_data: { position_name: 'PM', company_name: 'Corp' },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
  });
});
