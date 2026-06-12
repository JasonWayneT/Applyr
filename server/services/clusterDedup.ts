import { randomUUID } from 'crypto';
import type BetterSqlite3 from 'better-sqlite3';

function normalizeUrl(rawUrl: string): string {
  try {
    const u = new URL(rawUrl.trim());
    u.search = '';
    u.hash = '';
    u.pathname = u.pathname.replace(/\/+$/, '') || '/';
    return `${u.hostname.toLowerCase()}${u.pathname.toLowerCase()}`;
  } catch {
    return rawUrl.toLowerCase().trim();
  }
}

function normalizeText(s: string): string {
  return s.toLowerCase().trim().replace(/\s+/g, ' ');
}

interface IngestRow {
  id: string;
  source_id: string;
  external_job_id: string;
  request_url: string;
}

interface JobRow {
  id: string;
  url: string | null;
  company: string;
  title: string;
}

interface ClusterRow {
  id: string;
  canonical_job_id: string;
}

export interface ClusterDedupService {
  runClusterDedup(): void;
}

export function createClusterDedupService(db: BetterSqlite3.Database): ClusterDedupService {
  const getUnprocessed = db.prepare<[], IngestRow>(`
    SELECT r.id, r.source_id, r.external_job_id, r.request_url
    FROM job_ingest_raw r
    LEFT JOIN job_source_links sl ON sl.raw_ingest_id = r.id
    WHERE sl.id IS NULL
  `);

  const getAllJobs = db.prepare<[], JobRow>(
    'SELECT id, url, company, title FROM jobs',
  );

  const getExistingClusters = db.prepare<[], ClusterRow>(
    'SELECT id, canonical_job_id FROM job_clusters',
  );

  const insertCluster = db.prepare<[string, string, string]>(
    'INSERT INTO job_clusters (id, canonical_job_id, created_at) VALUES (?, ?, ?)',
  );

  const insertLink = db.prepare<[string, string, string, string, string]>(
    `INSERT OR IGNORE INTO job_source_links
       (id, cluster_id, source_id, external_job_id, raw_ingest_id)
     VALUES (?, ?, ?, ?, ?)`,
  );

  function runClusterDedup(): void {
    const unprocessed = getUnprocessed.all();
    if (unprocessed.length === 0) return;

    // Build URL → job lookup
    const allJobs = getAllJobs.all();
    const urlToJob = new Map<string, JobRow>();
    const companyTitleToCanonical = new Map<string, string>();

    for (const job of allJobs) {
      if (job.url) {
        urlToJob.set(normalizeUrl(job.url), job);
      }
      const ctKey = `${normalizeText(job.company)}::${normalizeText(job.title)}`;
      if (!companyTitleToCanonical.has(ctKey)) {
        companyTitleToCanonical.set(ctKey, job.id);
      }
    }

    // Seed cluster map from existing rows (idempotency)
    const clusterByCanonical = new Map<string, string>();
    for (const c of getExistingClusters.all()) {
      clusterByCanonical.set(c.canonical_job_id, c.id);
    }

    const now = new Date().toISOString();

    for (const row of unprocessed) {
      // Step 1: find candidate job by normalized URL
      const candidateJob =
        urlToJob.get(normalizeUrl(row.request_url)) ??
        urlToJob.get(normalizeUrl(row.external_job_id));

      let canonicalJobId: string;

      if (candidateJob) {
        // Step 2: resolve to canonical via Company+Title (merges cross-source duplicates)
        const ctKey = `${normalizeText(candidateJob.company)}::${normalizeText(candidateJob.title)}`;
        canonicalJobId = companyTitleToCanonical.get(ctKey) ?? candidateJob.id;
      } else {
        // No jobs entry yet — use external_job_id as placeholder canonical
        canonicalJobId = row.external_job_id;
      }

      // Step 3: find or create cluster
      let clusterId = clusterByCanonical.get(canonicalJobId);
      if (!clusterId) {
        clusterId = randomUUID();
        insertCluster.run(clusterId, canonicalJobId, now);
        clusterByCanonical.set(canonicalJobId, clusterId);
      }

      // Step 4: create source link (INSERT OR IGNORE handles re-runs)
      insertLink.run(randomUUID(), clusterId, row.source_id, row.external_job_id, row.id);
    }
  }

  return { runClusterDedup };
}
