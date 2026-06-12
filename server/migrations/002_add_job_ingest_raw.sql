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
