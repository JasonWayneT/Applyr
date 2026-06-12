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

const { createLevelsFyiConnector } = await import('./index.js');
const { chromium } = await import('playwright-extra');

beforeEach(() => {
  vi.clearAllMocks();
});

describe('levelsfyi connector', () => {
  it('exports sourceId as levelsfyi', () => {
    const connector = createLevelsFyiConnector();
    expect(connector.sourceId).toBe('levelsfyi');
  });

  it('fetchJobs returns [] when domain policy is blocked without launching browser', async () => {
    const connector = createLevelsFyiConnector({
      policyChecker: () => ({ status: 'blocked' }),
    });

    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(chromium.launchPersistentContext).not.toHaveBeenCalled();
  });

  it('fetchJobs returns [] when domain is not in policy table (unknown)', async () => {
    const connector = createLevelsFyiConnector({
      policyChecker: () => ({ status: 'unknown' }),
    });

    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(chromium.launchPersistentContext).not.toHaveBeenCalled();
  });

  it('fetchJobs returns [] when domain policy is manual_review', async () => {
    const connector = createLevelsFyiConnector({
      policyChecker: () => ({ status: 'manual_review' }),
    });

    const jobs = await connector.fetchJobs();

    expect(jobs).toHaveLength(0);
    expect(chromium.launchPersistentContext).not.toHaveBeenCalled();
  });

  it('fetchJobs calls policyChecker with levels.fyi domain', async () => {
    const policyChecker = vi.fn().mockReturnValue({ status: 'blocked' });
    const connector = createLevelsFyiConnector({ policyChecker });

    await connector.fetchJobs();

    expect(policyChecker).toHaveBeenCalledWith('levels.fyi');
  });

  it('healthCheck returns degraded when policy blocks', async () => {
    const connector = createLevelsFyiConnector({
      policyChecker: () => ({ status: 'blocked' }),
    });
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
    expect(health.error).toMatch(/blocked/);
  });

  it('healthCheck returns degraded when policy is manual_review', async () => {
    const connector = createLevelsFyiConnector({
      policyChecker: () => ({ status: 'manual_review' }),
    });
    const health = await connector.healthCheck();
    expect(health.status).toBe('degraded');
  });

  it('healthCheck returns ok when policy allows', async () => {
    const connector = createLevelsFyiConnector({
      policyChecker: () => ({ status: 'allowed' }),
    });
    const health = await connector.healthCheck();
    expect(health.status).toBe('ok');
  });

  it('normalize maps raw_data fields to NormalizedJob shape', () => {
    const connector = createLevelsFyiConnector();
    const raw: RawJobPayload = {
      external_job_id: 'https://www.levels.fyi/jobs/product-manager/123',
      url: 'https://www.levels.fyi/jobs/product-manager/123',
      source_id: 'levelsfyi',
      raw_data: {
        title: 'Senior Product Manager',
        company: 'Stripe',
        url: 'https://www.levels.fyi/jobs/product-manager/123',
      },
    };
    const normalized = connector.normalize(raw);
    expect(normalized.title).toBe('Senior Product Manager');
    expect(normalized.company).toBe('Stripe');
    expect(normalized.source_id).toBe('levelsfyi');
    expect(normalized.source_site).toBe('levelsfyi');
    expect(normalized.external_job_id).toBe('https://www.levels.fyi/jobs/product-manager/123');
  });
});
