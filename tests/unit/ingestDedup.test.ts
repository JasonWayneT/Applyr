import Database from 'better-sqlite3';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createIngestDedupService } from '../../server/services/ingestDedup.js';
import type { IngestDedupService } from '../../server/services/ingestDedup.js';
import type { RawJobPayload } from '../../shared/types/connectors.js';

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS job_ingest_raw (
    id TEXT PRIMARY KEY,
    source_id TEXT,
    fetched_at TEXT,
    external_job_id TEXT,
    payload_json TEXT,
    payload_hash TEXT,
    http_status INTEGER,
    request_url TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_job_ingest_raw_url ON job_ingest_raw(request_url);
`;

function makeJob(overrides: Partial<RawJobPayload> = {}): RawJobPayload {
  return {
    external_job_id: 'job-001',
    url: 'https://example.com/jobs/pm-001',
    source_id: 'remotive',
    raw_data: { title: 'Product Manager', company: 'Acme Corp' },
    ...overrides,
  };
}

describe('ingestDedup', () => {
  let testDb: Database.Database;
  let svc: IngestDedupService;

  beforeEach(() => {
    testDb = new Database(':memory:');
    testDb.exec(SCHEMA);
    svc = createIngestDedupService(testDb);
  });

  afterEach(() => {
    testDb.close();
  });

  describe('checkUrlExists', () => {
    it('returns null when URL is not in the table', () => {
      const result = svc.checkUrlExists('https://example.com/jobs/not-here');
      expect(result).toBeNull();
    });

    it('returns external_job_id after a row with that URL has been inserted', () => {
      const job = makeJob();
      svc.insertRawPayload('remotive', job);

      const result = svc.checkUrlExists(job.url);
      expect(result).toBe(job.external_job_id);
    });

    it('is case-sensitive — different URL case returns null', () => {
      const job = makeJob({ url: 'https://example.com/jobs/PM-001' });
      svc.insertRawPayload('remotive', job);

      const result = svc.checkUrlExists('https://example.com/jobs/pm-001');
      expect(result).toBeNull();
    });
  });

  describe('insertRawPayload', () => {
    it('returns a non-empty string id', () => {
      const id = svc.insertRawPayload('remotive', makeJob());
      expect(typeof id).toBe('string');
      expect(id.length).toBeGreaterThan(0);
    });

    it('inserts a row retrievable from the table', () => {
      const job = makeJob();
      const id = svc.insertRawPayload('remotive', job);

      const row = testDb
        .prepare('SELECT * FROM job_ingest_raw WHERE id = ?')
        .get(id) as Record<string, unknown> | undefined;

      expect(row).toBeDefined();
      expect(row!['source_id']).toBe('remotive');
      expect(row!['external_job_id']).toBe(job.external_job_id);
      expect(row!['request_url']).toBe(job.url);
      expect(row!['http_status']).toBe(200);
    });

    it('sets payload_hash to a 64-character hex string (SHA-256)', () => {
      const id = svc.insertRawPayload('remotive', makeJob());
      const row = testDb
        .prepare('SELECT payload_hash FROM job_ingest_raw WHERE id = ?')
        .get(id) as { payload_hash: string } | undefined;

      expect(row?.payload_hash).toMatch(/^[0-9a-f]{64}$/);
    });

    it('accepts a custom httpStatus', () => {
      const job = makeJob({ url: 'https://example.com/jobs/custom-status', external_job_id: 'job-002' });
      const id = svc.insertRawPayload('remotive', job, 201);

      const row = testDb
        .prepare('SELECT http_status FROM job_ingest_raw WHERE id = ?')
        .get(id) as { http_status: number } | undefined;

      expect(row?.http_status).toBe(201);
    });
  });

  describe('idempotency — duplicate URL prevention', () => {
    it('checkUrlExists gates duplicate inserts — row count stays at 1', () => {
      const job = makeJob();

      const existing = svc.checkUrlExists(job.url);
      if (!existing) svc.insertRawPayload('remotive', job);

      const existing2 = svc.checkUrlExists(job.url);
      if (!existing2) svc.insertRawPayload('remotive', job);

      const count = testDb
        .prepare('SELECT COUNT(*) as n FROM job_ingest_raw WHERE request_url = ?')
        .get(job.url) as { n: number };

      expect(count.n).toBe(1);
    });

    it('two different URLs both insert successfully', () => {
      const jobA = makeJob({ url: 'https://example.com/jobs/a', external_job_id: 'job-a' });
      const jobB = makeJob({ url: 'https://example.com/jobs/b', external_job_id: 'job-b' });

      svc.insertRawPayload('remotive', jobA);
      svc.insertRawPayload('remotive', jobB);

      const count = testDb
        .prepare('SELECT COUNT(*) as n FROM job_ingest_raw')
        .get() as { n: number };

      expect(count.n).toBe(2);
    });
  });
});
