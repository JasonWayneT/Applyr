-- CR-109 / FR-287 / DATA-005:
-- Add the BAD_DATA review answer (user flags an extracted candidate as not a
-- real skill/tool, so Applyr learns and never asks it again) to the CHECK
-- vocabularies of skill_memory.decision, pending_skill_confirmations.answer,
-- and review_answer_history.answer.
--
-- SQLite cannot ALTER a CHECK constraint, so the three tables are rebuilt.
-- The rebuild is idempotent on purpose: scripts/stage0_confirmations.py
-- executes every migration file on each connection, so this script must be
-- safe to run repeatedly (second run recreates the _cr109 staging tables,
-- copies, drops, and renames again with identical content).

CREATE TABLE IF NOT EXISTS skill_memory_cr109 (
  skill_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  decision TEXT NOT NULL,
  evidence_level INTEGER NOT NULL DEFAULT 0,
  details_json TEXT,
  source TEXT NOT NULL DEFAULT 'user_confirmation',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (decision IN ('CONFIRMED_USE', 'NOT_PRESENT', 'UNSURE_NO_REASK', 'VERIFIED_EVIDENCE', 'BAD_DATA')),
  CHECK (evidence_level BETWEEN 0 AND 4)
);
INSERT OR REPLACE INTO skill_memory_cr109
  SELECT skill_key, display_name, decision, evidence_level, details_json,
         source, created_at, updated_at
  FROM skill_memory;
DROP TABLE skill_memory;
ALTER TABLE skill_memory_cr109 RENAME TO skill_memory;

CREATE TABLE IF NOT EXISTS pending_skill_confirmations_cr109 (
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
    'NEEDS_MORE_INFO',
    'BAD_DATA'
  ) OR answer IS NULL)
);
INSERT OR REPLACE INTO pending_skill_confirmations_cr109
  SELECT id, review_key, question_type, skill_key, status, title, question,
         summary, requirement, evidence_excerpt, opportunity_key,
         opportunity_company, opportunity_title, opportunity_status, answer,
         answer_details_json, created_at, updated_at, resolved_at
  FROM pending_skill_confirmations;
DROP TABLE pending_skill_confirmations;
ALTER TABLE pending_skill_confirmations_cr109 RENAME TO pending_skill_confirmations;

CREATE INDEX IF NOT EXISTS idx_pending_review_key
  ON pending_skill_confirmations(review_key, status);
CREATE INDEX IF NOT EXISTS idx_pending_skill_key
  ON pending_skill_confirmations(skill_key, status);
CREATE INDEX IF NOT EXISTS idx_pending_opportunity
  ON pending_skill_confirmations(opportunity_key, status);

CREATE TABLE IF NOT EXISTS review_answer_history_cr109 (
  id TEXT PRIMARY KEY,
  review_key TEXT NOT NULL,
  question_type TEXT NOT NULL,
  answer TEXT NOT NULL,
  details_json TEXT,
  answered_at TEXT NOT NULL,
  CHECK (question_type IN ('skill_presence', 'evidence_enrichment', 'hard_gate_review')),
  CHECK (answer IN (
    'CONFIRMED_USE',
    'NOT_PRESENT',
    'UNSURE_NO_REASK',
    'KEEP_ELIGIBLE',
    'CONFIRM_HARD',
    'NEEDS_MORE_INFO',
    'BAD_DATA'
  ))
);
INSERT OR REPLACE INTO review_answer_history_cr109
  SELECT id, review_key, question_type, answer, details_json, answered_at
  FROM review_answer_history;
DROP TABLE review_answer_history;
ALTER TABLE review_answer_history_cr109 RENAME TO review_answer_history;

CREATE INDEX IF NOT EXISTS idx_review_answer_history_key
  ON review_answer_history(review_key, answered_at);
