import { describe, expect, it } from 'vitest';
import { normalizePipelineStats, normalizeQuarantineRows, normalizeUploadResult } from './pipelineQueue';

describe('pipeline queue client normalize', () => {
  it('keeps counts, leases, and stuck rows and drops unexpected PII fields', () => {
    const stats = normalizePipelineStats({
      counts: { queued: 2, leased: 1, in_progress: 0, paused: 1, ready_to_finalize: 2, done: 3, quarantined: 4 },
      leases: [{
        slug: 'acme',
        company: 'Acme',
        lockedBy: 'harness-1',
        leaseExpiresAt: '2099-01-01T00:00:00Z',
        leaseAgeMinutes: 12,
        networking_contacts_raw: 'SECRET',
      }],
      waiting: [{
        slug: 'waitco',
        company: 'Wait',
        reason: 'The last run failed.',
        networking_contacts_raw: 'SECRET',
      }],
      stuck: [{
        slug: 'stuckco',
        company: 'Stuck',
        status: 'in_progress',
        reason: 'expired_lease',
        ageMinutes: 130,
      }],
    });
    expect(stats.counts.queued).toBe(2);
    expect(stats.counts.ready_to_finalize).toBe(2);
    expect(stats.counts.paused).toBe(1);
    expect(stats.leases[0].lockedBy).toBe('harness-1');
    expect(JSON.stringify(stats)).not.toContain('SECRET');
    expect(stats.stuck[0].reason).toBe('expired_lease');
    expect(stats.waiting[0].reason).toBe('The last run failed.');
  });

  it('normalizes quarantine rows without rendering payload fields', () => {
    const rows = normalizeQuarantineRows({
      items: [{
        id: 9,
        sourceFile: 'jobs.csv',
        lineNumber: 4,
        errorCode: 'NO_DEDUP_KEY',
        quarantineReason: 'no key',
        raw_payload: 'JD_TEXT_MUST_NOT_RENDER',
      }],
    });
    expect(rows).toEqual([{
      id: 9,
      sourceFile: 'jobs.csv',
      lineNumber: 4,
      errorCode: 'NO_DEDUP_KEY',
      quarantineReason: 'no key',
    }]);
    expect(JSON.stringify(rows)).not.toContain('JD_TEXT_MUST_NOT_RENDER');
  });

  it('normalizes upload counts and drops extra fields', () => {
    const result = normalizeUploadResult({
      queued: 4,
      duplicate: 1,
      quarantined: 2,
      raw_payload: 'JD_TEXT_MUST_NOT_RENDER',
    });
    expect(result).toEqual({ queued: 4, duplicate: 1, quarantined: 2 });
    expect(JSON.stringify(result)).not.toContain('JD_TEXT_MUST_NOT_RENDER');
  });
});
