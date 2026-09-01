-- CR-108 / FR-282 / FR-283 / FR-285 / DATA-002 / DATA-003 / DATA-004:
-- durable Review Center state for Stage 0 confirmations and hard-gate reviews.
-- Additive only: creates new tables and indexes. Does not alter jobs, profiles,
-- workflow receipts, or source-of-truth career files.

CREATE TABLE IF NOT EXISTS skill_memory (
  skill_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  decision TEXT NOT NULL,
  evidence_level INTEGER NOT NULL DEFAULT 0,
  details_json TEXT,
  source TEXT NOT NULL DEFAULT 'user_confirmation',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (decision IN ('CONFIRMED_USE', 'NOT_PRESENT', 'UNSURE_NO_REASK', 'VERIFIED_EVIDENCE')),
  CHECK (evidence_level BETWEEN 0 AND 4)
);

CREATE TABLE IF NOT EXISTS pending_skill_confirmations (
  id TEXT PRIMARY KEY,
  review_key TEXT NOT NULL,
  question_type TEXT NOT NULL,
  skill_key TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  title TEXT NOT NULL,
  question TEXT NOT NULL,
  summary TEXT NOT NULL,
  requirement TEXT,
  evidence_excerpt TEXT,
  opportunity_key TEXT NOT NULL,
  opportunity_company TEXT NOT NULL,
  opportunity_title TEXT NOT NULL,
  opportunity_status TEXT,
  answer TEXT,
  answer_details_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  resolved_at TEXT,
  CHECK (question_type IN ('skill_presence', 'evidence_enrichment', 'hard_gate_review')),
  CHECK (status IN ('open', 'completed')),
  CHECK (answer IN (
    'CONFIRMED_USE',
    'NOT_PRESENT',
    'UNSURE_NO_REASK',
    'KEEP_ELIGIBLE',
    'CONFIRM_HARD',
    'NEEDS_MORE_INFO'
  ) OR answer IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_pending_review_key
  ON pending_skill_confirmations(review_key, status);

CREATE INDEX IF NOT EXISTS idx_pending_skill_key
  ON pending_skill_confirmations(skill_key, status);

CREATE INDEX IF NOT EXISTS idx_pending_opportunity
  ON pending_skill_confirmations(opportunity_key, status);
