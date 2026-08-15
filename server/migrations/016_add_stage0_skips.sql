-- CR-091 / FR-264: Stage 0 skip ledger (posting memory, not jobs.status).
-- Additive only: creates a new table + two unique indexes.
-- Does not ALTER, DROP, or rewrite `jobs` or any other existing table.
-- First server boot after this file lands will apply it once (schema_migrations)
-- against the live jobagent.sqlite. The new table starts empty; rows appear only
-- when a production Stage 0 Skip is recorded. Safe to re-run (IF NOT EXISTS).
-- Python scripts/stage0_skip_ledger.py.ensure_schema() uses the same DDL so
-- Stage 0 still works if a script runs before the server has migrated.
CREATE TABLE IF NOT EXISTS stage0_skips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT,
  url_key TEXT,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  posting_key TEXT NOT NULL,
  skip_reason TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  slug TEXT,
  archive_path TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_stage0_skips_url_key
  ON stage0_skips(url_key) WHERE url_key IS NOT NULL AND url_key != '';

CREATE UNIQUE INDEX IF NOT EXISTS idx_stage0_skips_posting_key
  ON stage0_skips(posting_key);
