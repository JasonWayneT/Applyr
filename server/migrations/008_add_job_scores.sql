CREATE TABLE IF NOT EXISTS job_scores (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  score_total INTEGER NOT NULL,
  score_breakdown_json TEXT NOT NULL,
  reason_summary TEXT,
  review_state TEXT,
  scored_at TEXT NOT NULL,
  is_latest INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_job_scores_job_id ON job_scores(job_id);
