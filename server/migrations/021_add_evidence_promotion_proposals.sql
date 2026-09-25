-- CR-108 / FR-284 / DATA-003:
-- Explicit verified-evidence proposals remain pending until the local
-- workExperience.md source of truth is independently verified.
CREATE TABLE IF NOT EXISTS evidence_promotion_proposals (
  id TEXT PRIMARY KEY,
  skill_key TEXT NOT NULL,
  review_key TEXT NOT NULL,
  details_json TEXT NOT NULL,
  source_path TEXT NOT NULL DEFAULT 'data/workExperience.md',
  source_digest TEXT,
  status TEXT NOT NULL DEFAULT 'PENDING_SOURCE_UPDATE',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  verified_at TEXT,
  CHECK (status IN ('PENDING_SOURCE_UPDATE', 'VERIFIED', 'REJECTED'))
);

CREATE INDEX IF NOT EXISTS idx_evidence_promotion_skill
  ON evidence_promotion_proposals(skill_key, status, updated_at);
