CREATE TABLE IF NOT EXISTS contacts (
  id TEXT PRIMARY KEY,
  job_id TEXT,                          -- nullable, no role open yet is a valid case (Type C)
  company TEXT NOT NULL,
  contact_name TEXT NOT NULL,
  contact_title TEXT,
  contact_type TEXT NOT NULL,           -- 'hiring_manager' | 'warm_connection' | 'informational'
  source TEXT,                          -- 'LinkedIn alum', 'mutual connection', 'cold search', etc.
  message_sent_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active', -- 'active' | 'responded' | 'closed'
  next_follow_up_due TEXT,              -- set = active thread awaiting reply; NULL = maintained relationship, no pending ask
  last_touch_at TEXT NOT NULL DEFAULT (datetime('now')), -- bumped on any logged interaction, drives staleness for "Worth reconnecting"
  follow_up_count INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  confirmed BOOLEAN NOT NULL DEFAULT 0, -- 0 = drafted stub from the skill, awaiting Jason's one-tap confirm; 1 = confirmed sent
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_contacts_job_id ON contacts(job_id);
CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);
