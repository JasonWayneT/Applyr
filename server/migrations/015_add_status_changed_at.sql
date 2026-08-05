-- Migration 015_add_status_changed_at.sql
-- Enables the Stage 0 reapply time-gate (2026-08-05 planning doc, Round 4): without this,
-- the only timestamp on a job row was created_at (when Applyr first scouted/drafted it), which
-- is not the same as when it was later marked Rejected/Closed -- there was no way to compute
-- "how long has it actually been since this was rejected."
-- No DEFAULT on this column deliberately: existing rows get NULL (unknown timing) rather than a
-- false CURRENT_TIMESTAMP backfill that would understate how long ago the rejection really
-- happened. Stage 0 treats NULL conservatively (still blocked) rather than guessing.
ALTER TABLE jobs ADD COLUMN status_changed_at DATETIME;
