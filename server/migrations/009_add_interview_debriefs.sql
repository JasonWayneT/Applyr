CREATE TABLE IF NOT EXISTS interview_debriefs (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  debrief_date TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  outcome TEXT NOT NULL DEFAULT 'Pending',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_interview_debriefs_job_id ON interview_debriefs(job_id);
