-- CR-119 addendum / pack 4 item 9f: paused_reason for ready_to_finalize.
-- Additive only. Does not rewrite pipeline_queue. SQLite places the new column
-- at the end of the table, matching scripts/pipeline_queue.py:_SCHEMA_SQL.
-- Python ensure_schema() also ALTER-if-missing so a Python-first DB still
-- accepts this file on the next Node boot.

ALTER TABLE pipeline_queue ADD COLUMN paused_reason TEXT;
