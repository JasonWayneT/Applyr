-- CR-108 / FR-282 / DATA-002:
-- durable Stage 0 run and per-item judgment checkpoints.
-- Additive only. Request/response spool files remain local to the submission
-- workspace and are referenced by hash/path, never stored as unbounded blobs.

CREATE TABLE IF NOT EXISTS stage0_runs (
  run_key TEXT PRIMARY KEY,
  opportunity_key TEXT NOT NULL,
  jd_hash TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  provider_policy_hash TEXT NOT NULL,
  evidence_index_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'REQUESTED',
  request_hash TEXT,
  request_spool_path TEXT,
  response_spool_path TEXT,
  response_hash TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  completed_at TEXT,
  CHECK (status IN ('REQUESTED', 'RUNNING', 'WAITING_FOR_INPUT', 'COMPLETE', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_stage0_runs_opportunity
  ON stage0_runs(opportunity_key, updated_at);

CREATE TABLE IF NOT EXISTS stage0_judgments (
  judgment_key TEXT PRIMARY KEY,
  run_key TEXT NOT NULL,
  opportunity_key TEXT NOT NULL,
  item_key TEXT NOT NULL,
  item_text TEXT NOT NULL,
  bucket TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'REQUESTED',
  request_hash TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  evidence_index_hash TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  judgment_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (status IN ('REQUESTED', 'COMPLETE', 'HELD', 'FAILED')),
  UNIQUE (run_key, item_key, request_hash)
);

CREATE INDEX IF NOT EXISTS idx_stage0_judgments_run
  ON stage0_judgments(run_key, status);

CREATE INDEX IF NOT EXISTS idx_stage0_judgments_item
  ON stage0_judgments(opportunity_key, item_key, content_hash);
