CREATE TABLE IF NOT EXISTS job_source_links (
  id TEXT PRIMARY KEY,
  cluster_id TEXT,
  source_id TEXT,
  external_job_id TEXT,
  raw_ingest_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_job_source_links_cluster ON job_source_links(cluster_id);
CREATE INDEX IF NOT EXISTS idx_job_source_links_raw_ingest ON job_source_links(raw_ingest_id);
