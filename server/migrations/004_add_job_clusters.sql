CREATE TABLE IF NOT EXISTS job_clusters (
  id TEXT PRIMARY KEY,
  canonical_job_id TEXT,
  created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_clusters_canonical ON job_clusters(canonical_job_id);
