import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, '../jobagent.sqlite');
const OPENPOSTINGS_DB_PATH = path.join(__dirname, '../openpostings_temp/OpenPostings-main/jobs.db');

export const db = new Database(DB_PATH);

// Initialize main schema
db.exec(`
  CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE,
    score INTEGER,
    status TEXT DEFAULT 'Backlog',
    summary TEXT,
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

// Attach OpenPostings DB for reference
try {
  db.exec(`ATTACH DATABASE '${OPENPOSTINGS_DB_PATH}' AS openpostings`);
  console.log('Successfully attached OpenPostings DB');
} catch (err) {
  console.error('Warning: Could not attach OpenPostings DB. Scout logic will be limited.', err);
}

export const logActivity = (level: 'INFO' | 'WARN' | 'ERROR', source: string, message: string, meta?: any) => {
  const stmt = db.prepare('INSERT INTO activity_log (level, source, message, meta) VALUES (?, ?, ?, ?)');
  stmt.run(level, source, message, meta ? JSON.stringify(meta) : null);
};
