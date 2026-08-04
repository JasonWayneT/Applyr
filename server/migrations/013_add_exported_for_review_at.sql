-- Migration 013: Mark jobs already exported to data/pending_review/ (Sync review queue).
-- Idempotency for the post-scrape export step that replaced silent auto-draft (2026-08-04).
--
-- Grandfather existing rows so the first Sync after deploy does not flood pending_review
-- with the entire historical Drafted backlog. Only jobs inserted after this migration
-- (exported_for_review_at still NULL) are written on Sync.

ALTER TABLE jobs ADD COLUMN exported_for_review_at DATETIME;

UPDATE jobs
SET exported_for_review_at = COALESCE(created_at, CURRENT_TIMESTAMP)
WHERE exported_for_review_at IS NULL;
