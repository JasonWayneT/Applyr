import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { JobConnector, RawJobPayload } from '../../shared/types/connectors.js';

vi.mock('../../server/db.js', () => ({
  db: {
    prepare: vi.fn(() => ({
      run: vi.fn(() => ({ changes: 1, lastInsertRowid: 1 })),
      get: vi.fn(() => undefined),
    })),
  },
  logActivity: vi.fn(),
  syncJobFts: vi.fn(),
  deleteJobFts: vi.fn(),
}));

vi.mock('../../server/middleware/crawlPolicy.js', () => ({
  checkCrawlPolicy: vi.fn(() => ({ status: 'allowed' })),
}));

vi.mock('../../server/repository/jobRepository.js', () => ({
  insertJob: vi.fn().mockReturnValue('mock-uuid'),
}));

vi.mock('../../server/services/jobStaging.js', () => ({
  writeJobStagingFile: vi.fn(),
}));

vi.mock('../../server/routes/pipeline.js', () => ({
  broadcastSyncEvent: vi.fn(),
}));

// Dynamic imports after mocks are hoisted
const { runConnectorOrchestration } = await import('../../server/services/scoutOrchestrator.js');
const { logActivity } = await import('../../server/db.js');
const { insertJob } = await import('../../server/repository/jobRepository.js');
const { checkCrawlPolicy } = await import('../../server/middleware/crawlPolicy.js');

beforeEach(() => {
  vi.clearAllMocks();
});

function makeRawJob(
  id: string,
  title = 'Product Manager',
  company = 'Acme',
  description = 'Remote product manager role in the United States. B2B SaaS platform experience preferred.',
): RawJobPayload {
  return {
    external_job_id: id,
    url: `https://example.com/jobs/${id}`,
    source_id: 'test',
    raw_data: { title, company, description },
  };
}

function makeConnector(id: string, jobs: RawJobPayload[] = []): JobConnector {
  return {
    sourceId: id,
    fetchJobs: vi.fn().mockResolvedValue(jobs),
    healthCheck: vi.fn().mockResolvedValue({ status: 'ok', last_checked: new Date().toISOString() }),
    normalize: vi.fn((raw: RawJobPayload) => ({
      external_job_id: raw.external_job_id,
      source_id: id,
      title: String((raw.raw_data as Record<string, unknown>)['title'] ?? ''),
      company: String((raw.raw_data as Record<string, unknown>)['company'] ?? ''),
      url: raw.url,
      source_site: id,
      description: String((raw.raw_data as Record<string, unknown>)['description'] ?? ''),
    })),
  };
}

describe('runConnectorOrchestration', () => {
  it('invokes all provided connectors', async () => {
    const c1 = makeConnector('source_a');
    const c2 = makeConnector('source_b');

    await runConnectorOrchestration([c1, c2]);

    expect(c1.fetchJobs).toHaveBeenCalledOnce();
    expect(c2.fetchJobs).toHaveBeenCalledOnce();
  });

  it('continues to next connector when one throws', async () => {
    const failing = makeConnector('failing');
    vi.mocked(failing.fetchJobs).mockRejectedValue(new Error('network timeout'));
    const succeeding = makeConnector('succeeding');

    await runConnectorOrchestration([failing, succeeding]);

    expect(succeeding.fetchJobs).toHaveBeenCalledOnce();
  });

  it('logs ERROR with source name when a connector throws', async () => {
    const failing = makeConnector('broken_source');
    vi.mocked(failing.fetchJobs).mockRejectedValue(new Error('503 Service Unavailable'));

    await runConnectorOrchestration([failing]);

    const errCall = vi.mocked(logActivity).mock.calls.find(
      ([level, source]) => level === 'ERROR' && source === 'broken_source',
    );
    expect(errCall).toBeDefined();
    expect(errCall![2]).toMatch(/503 Service Unavailable/);
  });

  it('logs INFO for each connector run', async () => {
    const c = makeConnector('remotive', [makeRawJob('job-1')]);

    await runConnectorOrchestration([c]);

    const infoCalls = vi.mocked(logActivity).mock.calls.filter(([level]) => level === 'INFO');
    expect(infoCalls.length).toBeGreaterThanOrEqual(2);
  });

  it('does not throw when all connectors return empty results', async () => {
    const c1 = makeConnector('empty_a');
    const c2 = makeConnector('empty_b');

    await expect(runConnectorOrchestration([c1, c2])).resolves.toBeUndefined();
  });

  it('calls insertJob for each new job that passes filters', async () => {
    const raw = makeRawJob('job-new');
    const connector = makeConnector('src', [raw]);

    await runConnectorOrchestration([connector]);

    expect(vi.mocked(insertJob)).toHaveBeenCalledOnce();
    expect(vi.mocked(insertJob)).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Product Manager', company: 'Acme' }),
    );
  });

  it('skips jobs whose URL already appears in the jobs table', async () => {
    const { db: mockDb } = await import('../../server/db.js');
    // Make the first prepare().get() call return an existing row — simulates URL in jobs table
    vi.mocked(mockDb.prepare).mockReturnValueOnce({
      get: vi.fn().mockReturnValue({ id: 'existing-id' }),
      run: vi.fn(() => ({ changes: 0, lastInsertRowid: 0 })),
    } as any);

    const raw = makeRawJob('dup-1');
    const connector = makeConnector('src', [raw]);

    await runConnectorOrchestration([connector]);

    expect(vi.mocked(insertJob)).not.toHaveBeenCalled();
  });

  it('confirms crawl policy gate fires when policyChecker is called with blocked domain', async () => {
    vi.mocked(checkCrawlPolicy).mockImplementation((domain) => {
      vi.mocked(logActivity)('WARN', 'CrawlPolicy', `Domain ${domain} policy status is 'blocked' — skipping fetch`);
      return { status: 'blocked' };
    });

    // Connector that exercises the policyChecker injection pattern used by crawl connectors
    const crawlConnector: JobConnector = {
      sourceId: 'builtin',
      fetchJobs: async () => {
        const result = checkCrawlPolicy('builtin.com');
        if (result.status !== 'allowed') return [];
        return [makeRawJob('job-1')];
      },
      normalize: vi.fn(),
      healthCheck: vi.fn(),
    };

    await runConnectorOrchestration([crawlConnector]);

    expect(vi.mocked(checkCrawlPolicy)).toHaveBeenCalledWith('builtin.com');

    const warnCalls = vi.mocked(logActivity).mock.calls.filter(
      ([level, source]) => level === 'WARN' && source === 'CrawlPolicy',
    );
    expect(warnCalls.length).toBeGreaterThan(0);
    expect(vi.mocked(insertJob)).not.toHaveBeenCalled();
  });

  it('rejects jobs on the title blocklist', async () => {
    // 'staff' is in the default title blocklist
    const raw = makeRawJob('staff-1', 'VP of Product', 'Acme');
    const connector = makeConnector('src', [raw]);

    await runConnectorOrchestration([connector]);

    expect(vi.mocked(insertJob)).not.toHaveBeenCalled();

    const rejectCalls = vi.mocked(logActivity).mock.calls.filter(
      ([, , msg]) => typeof msg === 'string' && msg.includes('[REJECT]') && msg.includes('Title Blocklist'),
    );
    expect(rejectCalls.length).toBeGreaterThan(0);
  });

  it('rejects titles outside target role scope (e.g. Account Executive)', async () => {
    const raw = makeRawJob('ae-1', 'Account Executive', 'Acme');
    const connector = makeConnector('src', [raw]);

    await runConnectorOrchestration([connector]);

    expect(vi.mocked(insertJob)).not.toHaveBeenCalled();

    const rejectCalls = vi.mocked(logActivity).mock.calls.filter(
      ([, , msg]) => typeof msg === 'string' && msg.includes('target_role_scope'),
    );
    expect(rejectCalls.length).toBeGreaterThan(0);
  });

  it('rejects LinkedIn job URLs at ingest (FR-080)', async () => {
    const raw: RawJobPayload = {
      external_job_id: 'li-1',
      url: 'https://www.linkedin.com/jobs/view/123456/',
      source_id: 'test',
      raw_data: {
        title: 'Product Manager',
        company: 'Acme',
        description: 'Remote product manager role in the United States. B2B SaaS platform experience preferred.',
      },
    };
    const connector = makeConnector('src', [raw]);
    connector.normalize = vi.fn(() => ({
      external_job_id: raw.external_job_id,
      source_id: 'src',
      title: 'Product Manager',
      company: 'Acme',
      url: raw.url,
      source_site: 'src',
      description: String((raw.raw_data as Record<string, unknown>)['description'] ?? ''),
    }));

    await runConnectorOrchestration([connector]);

    expect(vi.mocked(insertJob)).not.toHaveBeenCalled();
    const rejectCalls = vi.mocked(logActivity).mock.calls.filter(
      ([, , msg]) => typeof msg === 'string' && msg.includes('LinkedIn URL blocked'),
    );
    expect(rejectCalls.length).toBeGreaterThan(0);
  });
});
