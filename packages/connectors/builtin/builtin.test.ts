import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { RawJobPayload } from '../../../shared/types/connectors.js';

vi.mock('playwright-extra', () => ({
  chromium: {
    use: vi.fn(),
    launchPersistentContext: vi.fn(),
  },
}));

vi.mock('puppeteer-extra-plugin-stealth', () => ({
  default: vi.fn(() => ({})),
}));

// Import after mocks are hoisted
const { createBuiltInConnector } = await import('./index.js');
const { chromium } = await import('playwright-extra');

beforeEach(() => {
  vi.clearAllMocks();
});

describe('builtin connector', () => {
  it('exports sourceId as builtin', () => {
    const connector = createBuiltInConnector();
    expect(connector.sourceId).toBe('builtin');
  });

  it('fetchJobs returns [] when domain policy is blocked without launching browser', async () => {
    const connector = createBuiltInConnector({
      policyChecker: () => ({ status: 'blocked' }),
    });

    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(chromium.launchPersistentContext).not.toHaveBeenCalled();
  });

  it('fetchJobs returns [] when domain is not in policy table (unknown)', async () => {
    const connector = createBuiltInConnector({
      policyChecker: () => ({ status: 'unknown' }),
    });

    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(chromium.launchPersistentContext).not.toHaveBeenCalled();
  });

  it('fetchJobs returns [] when domain policy is paused', async () => {
    const connector = createBuiltInConnector({
      policyChecker: () => ({ status: 'paused' }),
    });

    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(chromium.launchPersistentContext).not.toHaveBeenCalled();
  });

  it('fetchJobs calls policyChecker with builtin.com domain', async () => {
    const policyChecker = vi.fn().mockReturnValue({ status: 'blocked' });
    const connector = createBuiltInConnector({ policyChecker });

    await connector.fetchJobs();

    expect(policyChecker).toHaveBeenCalledWith('builtin.com');
  });

  it('healthCheck returns degraded when policy blocks', async () => {
    const connector = createBuiltInConnector({
      policyChecker: () => ({ status: 'paused' }),
    });
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/paused/);
  });

  it('healthCheck returns ok when policy allows', async () => {
    const connector = createBuiltInConnector({
      policyChecker: () => ({ status: 'allowed' }),
    });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
  });

  it('normalize maps raw_data fields to NormalizedJob shape', () => {
    const connector = createBuiltInConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://builtin.com/job/pm-123',
      url: 'https://builtin.com/job/pm-123',
      source_id: 'builtin',
      raw_data: {
        title: 'Product Manager',
        company: 'Acme Corp',
        url: 'https://builtin.com/job/pm-123',
        description: 'Lead cross-functional teams',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Product Manager');
    expect(normalized.company).toBe('Acme Corp');
    expect(normalized.source_id).toBe('builtin');
    expect(normalized.source_site).toBe('builtin');
    expect(normalized.description).toBe('Lead cross-functional teams');
    expect(normalized.external_job_id).toBe('https://builtin.com/job/pm-123');
  });

  it('normalize returns undefined description for empty string', () => {
    const connector = createBuiltInConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://builtin.com/job/pm-456',
      url: 'https://builtin.com/job/pm-456',
      source_id: 'builtin',
      raw_data: { title: 'PM', company: 'Corp', url: 'https://builtin.com/job/pm-456', description: '' },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.description).toBeUndefined();
  });
});
