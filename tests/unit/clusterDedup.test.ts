import Database from 'better-sqlite3';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { createClusterDedupService } from '../../server/services/clusterDedup.js';
import type { ClusterDedupService } from '../../server/services/clusterDedup.js';

const JOB_INGEST_RAW_SCHEMA = `
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
`;

const JOBS_SCHEMA = `
  CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE
  );
`;

const CLUSTER_SCHEMA = `
  CREATE TABLE IF NOT EXISTS job_clusters (
    id TEXT PRIMARY KEY,
    canonical_job_id TEXT,
    created_at TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_job_clusters_canonical ON job_clusters(canonical_job_id);
`;

const SOURCE_LINKS_SCHEMA = `
  CREATE TABLE IF NOT EXISTS job_source_links (
    id TEXT PRIMARY KEY,
    cluster_id TEXT,
    source_id TEXT,
    external_job_id TEXT,
    raw_ingest_id TEXT
  );
  CREATE INDEX IF NOT EXISTS idx_job_source_links_raw_ingest ON job_source_links(raw_ingest_id);
`;

function setupDb(): Database.Database {
  const db = new Database(':memory:');
  db.exec(JOB_INGEST_RAW_SCHEMA);
  db.exec(JOBS_SCHEMA);
  db.exec(CLUSTER_SCHEMA);
  db.exec(SOURCE_LINKS_SCHEMA);
  return db;
}

function insertRaw(
  db: Database.Database,
  opts: { id: string; sourceId: string; externalJobId: string; requestUrl: string },
) {
  db.prepare(
    `INSERT INTO job_ingest_raw (id, source_id, fetched_at, external_job_id, payload_json, payload_hash, http_status, request_url)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(opts.id, opts.sourceId, new Date().toISOString(), opts.externalJobId, '{}', 'abc', 200, opts.requestUrl);
}

function insertJob(
  db: Database.Database,
  opts: { id: string; company: string; title: string; url: string },
) {
  db.prepare('INSERT INTO jobs (id, company, title, url) VALUES (?, ?, ?, ?)').run(
    opts.id,
    opts.company,
    opts.title,
    opts.url,
  );
}

function clusterCount(db: Database.Database): number {
  return (db.prepare('SELECT COUNT(*) as n FROM job_clusters').get() as { n: number }).n;
}

function linkCount(db: Database.Database): number {
  return (db.prepare('SELECT COUNT(*) as n FROM job_source_links').get() as { n: number }).n;
}

describe('clusterDedup', () => {
  let testDb: Database.Database;
  let svc: ClusterDedupService;

  beforeEach(() => {
    testDb = setupDb();
    svc = createClusterDedupService(testDb);
  });

  afterEach(() => {
    testDb.close();
  });

  it('no-ops when job_ingest_raw is empty', () => {
    svc.runClusterDedup();
    expect(clusterCount(testDb)).toBe(0);
    expect(linkCount(testDb)).toBe(0);
  });

  it('creates one cluster and one source link for a single raw entry', () => {
    insertJob(testDb, { id: 'job-1', company: 'Acme', title: 'PM', url: 'https://example.com/job/1' });
    insertRaw(testDb, {
      id: 'raw-1',
      sourceId: 'remotive',
      externalJobId: 'https://example.com/job/1',
      requestUrl: 'https://example.com/job/1',
    });

    svc.runClusterDedup();

    expect(clusterCount(testDb)).toBe(1);
    expect(linkCount(testDb)).toBe(1);

    const cluster = testDb.prepare('SELECT canonical_job_id FROM job_clusters').get() as {
      canonical_job_id: string;
    };
    expect(cluster.canonical_job_id).toBe('job-1');
  });

  describe('URL normalization dedup', () => {
    it('http vs https same path → same cluster', () => {
      insertJob(testDb, { id: 'job-1', company: 'Acme', title: 'PM', url: 'https://example.com/job/1' });
      insertRaw(testDb, {
        id: 'raw-a',
        sourceId: 'remotive',
        externalJobId: 'http://example.com/job/1',
        requestUrl: 'http://example.com/job/1',
      });
      insertRaw(testDb, {
        id: 'raw-b',
        sourceId: 'remoteok',
        externalJobId: 'https://example.com/job/1',
        requestUrl: 'https://example.com/job/1',
      });

      svc.runClusterDedup();

      expect(clusterCount(testDb)).toBe(1);
      expect(linkCount(testDb)).toBe(2);
    });

    it('trailing slash difference → same cluster', () => {
      insertJob(testDb, { id: 'job-1', company: 'Acme', title: 'PM', url: 'https://example.com/job/1' });
      insertRaw(testDb, {
        id: 'raw-a',
        sourceId: 'remotive',
        externalJobId: 'https://example.com/job/1/',
        requestUrl: 'https://example.com/job/1/',
      });
      insertRaw(testDb, {
        id: 'raw-b',
        sourceId: 'remoteok',
        externalJobId: 'https://example.com/job/1',
        requestUrl: 'https://example.com/job/1',
      });

      svc.runClusterDedup();

      expect(clusterCount(testDb)).toBe(1);
      expect(linkCount(testDb)).toBe(2);
    });

    it('query string stripped → same cluster', () => {
      insertJob(testDb, { id: 'job-1', company: 'Acme', title: 'PM', url: 'https://example.com/job/1' });
      insertRaw(testDb, {
        id: 'raw-a',
        sourceId: 'remotive',
        externalJobId: 'https://example.com/job/1?utm_source=linkedin',
        requestUrl: 'https://example.com/job/1?utm_source=linkedin',
      });
      insertRaw(testDb, {
        id: 'raw-b',
        sourceId: 'remoteok',
        externalJobId: 'https://example.com/job/1',
        requestUrl: 'https://example.com/job/1',
      });

      svc.runClusterDedup();

      expect(clusterCount(testDb)).toBe(1);
      expect(linkCount(testDb)).toBe(2);
    });
  });

  describe('Company+Title dedup', () => {
    it('same company+title from different sources → same cluster', () => {
      // Two different job board URLs for the same role at the same company
      insertJob(testDb, {
        id: 'job-greenhouse',
        company: 'Acme Corp',
        title: 'Senior Product Manager',
        url: 'https://greenhouse.io/job/123',
      });
      insertJob(testDb, {
        id: 'job-lever',
        company: 'Acme Corp',
        title: 'Senior Product Manager',
        url: 'https://lever.co/job/456',
      });

      insertRaw(testDb, {
        id: 'raw-gh',
        sourceId: 'greenhouse',
        externalJobId: 'https://greenhouse.io/job/123',
        requestUrl: 'https://greenhouse.io/job/123',
      });
      insertRaw(testDb, {
        id: 'raw-lv',
        sourceId: 'lever',
        externalJobId: 'https://lever.co/job/456',
        requestUrl: 'https://lever.co/job/456',
      });

      svc.runClusterDedup();

      // Both should land in ONE cluster
      expect(clusterCount(testDb)).toBe(1);
      expect(linkCount(testDb)).toBe(2);

      const links = testDb
        .prepare('SELECT cluster_id FROM job_source_links ORDER BY source_id')
        .all() as Array<{ cluster_id: string }>;
      expect(links[0].cluster_id).toBe(links[1].cluster_id);
    });

    it('case-insensitive company+title match', () => {
      insertJob(testDb, {
        id: 'job-1',
        company: 'ACME CORP',
        title: 'Product Manager',
        url: 'https://site-a.com/job/1',
      });
      insertJob(testDb, {
        id: 'job-2',
        company: 'acme corp',
        title: 'product manager',
        url: 'https://site-b.com/job/2',
      });

      insertRaw(testDb, {
        id: 'raw-a',
        sourceId: 'sitea',
        externalJobId: 'https://site-a.com/job/1',
        requestUrl: 'https://site-a.com/job/1',
      });
      insertRaw(testDb, {
        id: 'raw-b',
        sourceId: 'siteb',
        externalJobId: 'https://site-b.com/job/2',
        requestUrl: 'https://site-b.com/job/2',
      });

      svc.runClusterDedup();

      expect(clusterCount(testDb)).toBe(1);
      expect(linkCount(testDb)).toBe(2);
    });
  });

  describe('idempotency', () => {
    it('calling runClusterDedup twice does not create duplicate clusters or links', () => {
      insertJob(testDb, { id: 'job-1', company: 'Acme', title: 'PM', url: 'https://example.com/job/1' });
      insertRaw(testDb, {
        id: 'raw-1',
        sourceId: 'remotive',
        externalJobId: 'https://example.com/job/1',
        requestUrl: 'https://example.com/job/1',
      });

      svc.runClusterDedup();
      svc.runClusterDedup();

      expect(clusterCount(testDb)).toBe(1);
      expect(linkCount(testDb)).toBe(1);
    });
  });

  it('raw entry with no matching jobs entry gets clustered with external_job_id as canonical', () => {
    insertRaw(testDb, {
      id: 'raw-orphan',
      sourceId: 'remotive',
      externalJobId: 'https://orphan.com/job/999',
      requestUrl: 'https://orphan.com/job/999',
    });

    svc.runClusterDedup();

    expect(clusterCount(testDb)).toBe(1);
    const cluster = testDb.prepare('SELECT canonical_job_id FROM job_clusters').get() as {
      canonical_job_id: string;
    };
    expect(cluster.canonical_job_id).toBe('https://orphan.com/job/999');
  });

  it('distinct jobs with different company+title produce separate clusters', () => {
    insertJob(testDb, { id: 'job-1', company: 'Acme', title: 'PM', url: 'https://a.com/1' });
    insertJob(testDb, { id: 'job-2', company: 'Beta', title: 'Engineer', url: 'https://b.com/2' });

    insertRaw(testDb, {
      id: 'raw-1',
      sourceId: 'remotive',
      externalJobId: 'https://a.com/1',
      requestUrl: 'https://a.com/1',
    });
    insertRaw(testDb, {
      id: 'raw-2',
      sourceId: 'remoteok',
      externalJobId: 'https://b.com/2',
      requestUrl: 'https://b.com/2',
    });

    svc.runClusterDedup();

    expect(clusterCount(testDb)).toBe(2);
    expect(linkCount(testDb)).toBe(2);
  });
});
