-- CR-112 (Defect B, v3 manual judgment correction mechanism):
-- Append-only audit history for a manual correction of a cached Stage 0
-- item judgment (stage0_judgments), for the case where the requirement set
-- itself is *unchanged* (same run_key/item_key/request_hash as the row
-- being corrected) so a second stage0_judgments row cannot be inserted at
-- all under its own UNIQUE (run_key, item_key, request_hash) constraint.
--
-- Additive only, same pattern as 020_add_review_answer_history.sql's own
-- header: "Append-only audit history... current state remains on the live
-- table, each answer preserved separately." Pure CREATE TABLE IF NOT
-- EXISTS -- safe under stage0_checkpoint._connect()'s re-run-every-
-- migration-on-every-connect behavior, no rebuild, no per-connect table
-- copy (unlike 022_add_bad_data_answer.sql's CHECK-widening rebuild).
--
-- get_completed_judgment() needs zero changes: it keeps reading the single
-- live stage0_judgments row, which correct_judgment() updates in place
-- after appending the pre-correction state here.

CREATE TABLE IF NOT EXISTS stage0_judgment_corrections (
  id TEXT PRIMARY KEY,
  judgment_key TEXT NOT NULL,
  run_key TEXT NOT NULL,
  opportunity_key TEXT NOT NULL,
  item_key TEXT NOT NULL,
  item_text TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  previous_judgment_json TEXT NOT NULL,
  corrected_judgment_json TEXT NOT NULL,
  correction_source TEXT NOT NULL,
  reason TEXT,
  corrected_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stage0_judgment_corrections_judgment
  ON stage0_judgment_corrections(judgment_key, corrected_at);
