-- Migration 014: Grandfather exported_for_review_at for rows that got the column
-- from 013 before the grandfather UPDATE was added to that file (same-day fix).
-- Idempotent: only touches NULL values.

UPDATE jobs
SET exported_for_review_at = COALESCE(created_at, CURRENT_TIMESTAMP)
WHERE exported_for_review_at IS NULL;
