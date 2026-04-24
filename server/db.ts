import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, '../jobagent.sqlite');

export const db = new Database(DB_PATH);

// Initialize schema — idempotent, safe to run on every boot
db.exec(`
  CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE,
    score INTEGER,
    status TEXT DEFAULT 'Backlog',
    summary TEXT,
    salary_range TEXT,
    recruiter_name TEXT,
    recruiter_url TEXT,
    source_site TEXT,
    rejection_stage TEXT,
    rejection_type TEXT,
    outcome_notes TEXT,
    interview_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    meta TEXT
  );

  CREATE TABLE IF NOT EXISTS profiles (
    key TEXT PRIMARY KEY,
    value TEXT
  );
`);

export const logActivity = (
  level: 'INFO' | 'WARN' | 'ERROR',
  source: string,
  message: string,
  meta?: any
) => {
  db.prepare('INSERT INTO activity_log (level, source, message, meta) VALUES (?, ?, ?, ?)')
    .run(level, source, message, meta ? JSON.stringify(meta) : null);
};
