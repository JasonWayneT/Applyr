-- Migration 010: Track when a job was marked Applied (separate from created_at = discovered)

ALTER TABLE jobs ADD COLUMN applied_at DATETIME;

-- Existing Applied+ (and Closed-from-Applied+) rows: treat discovered date as applied date
UPDATE jobs
SET applied_at = created_at
WHERE applied_at IS NULL
  AND (
    status IN ('Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation')
    OR (
      status = 'Closed'
      AND rejection_stage IN ('Applied', 'Recruiter Screen', 'Core Interviews', 'Offer and Negotiation')
    )
  );
