-- CR-119 addendum / FIXQUEUE 9l: audit columns for manual requeue.
-- Additive only. Does not rewrite pipeline_queue. SQLite places new columns
-- at the end of the table, matching scripts/pipeline_queue.py:_SCHEMA_SQL.
-- Python ensure_schema() also ALTER-if-missing so a Python-first DB still
-- accepts this file on the next Node boot.

ALTER TABLE pipeline_queue ADD COLUMN requeued_by TEXT;
ALTER TABLE pipeline_queue ADD COLUMN requeue_reason TEXT;
ALTER TABLE pipeline_queue ADD COLUMN requeued_at TEXT;
