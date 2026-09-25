-- CR-108 / DATA-004:
-- Append-only audit history for Review Center decisions. Current state remains
-- on pending_skill_confirmations, while each answer is preserved separately.

CREATE TABLE IF NOT EXISTS review_answer_history (
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
    'NEEDS_MORE_INFO'
  ))
);

CREATE INDEX IF NOT EXISTS idx_review_answer_history_key
  ON review_answer_history(review_key, answered_at);
