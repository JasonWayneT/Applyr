import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';
import { runMigrations } from './migrationRunner.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, '../jobagent.sqlite');

export const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');
db.pragma('busy_timeout = 30000');

// Initialize schema — idempotent, safe to run on every boot
db.exec(`
  CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'PENDING',
    current_stage TEXT DEFAULT 'SCOUT',
    last_error TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT UNIQUE,
    score INTEGER,
    status TEXT DEFAULT 'Drafted',
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

  CREATE TABLE IF NOT EXISTS system_status (
    id TEXT PRIMARY KEY,
    process_type TEXT,
    status TEXT,
    current_item TEXT,
    items_completed INTEGER DEFAULT 0,
    items_total INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS stale_jobs (
    url TEXT PRIMARY KEY,
    company TEXT,
    title TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  INSERT OR IGNORE INTO system_status (id, process_type, status, current_item)
  VALUES ('global', 'all', 'idle', 'No active pipeline run');

  UPDATE system_status SET status = 'idle', current_item = 'Server restart detected. No active pipeline run.', updated_at = CURRENT_TIMESTAMP WHERE id = 'global';
`);

// CR-011: retry tracking + legacy status migration
try {
  db.exec(`ALTER TABLE jobs ADD COLUMN retry_count INTEGER DEFAULT 0`);
} catch {
  /* column exists */
}
try {
  db.prepare(`UPDATE jobs SET status = 'Needs Retry' WHERE status = 'Failed'`).run();
} catch {
  /* ignore */
}

// CR-021: extended job columns
for (const [col, typ] of [
  ['jd_vector', 'TEXT'],
  ['pre_score', 'INTEGER'],
  ['metadata_vector', 'TEXT'],
  ['jd_text', 'TEXT'],
  ['metadata_tags', 'TEXT'],
] as const) {
  try {
    db.exec(`ALTER TABLE jobs ADD COLUMN ${col} ${typ}`);
  } catch {
    /* exists */
  }
}

// CR-033 follow-up: extraction quality metadata
for (const [col, typ] of [
  ['extraction_confidence', 'TEXT'],
  ['data_quality_flags', 'TEXT'],
] as const) {
  try {
    db.exec(`ALTER TABLE jobs ADD COLUMN ${col} ${typ}`);
  } catch {
    /* exists */
  }
}

// FTS5 search (CR-020 / CR-021) — standalone index; no UPDATE triggers (BUG-011 / FTS url mismatch)
try {
  for (const trig of ['jobs_fts_ai', 'jobs_fts_ad', 'jobs_fts_au', 'jobs_ai', 'jobs_ad', 'jobs_au']) {
    db.exec(`DROP TRIGGER IF EXISTS ${trig}`);
  }
  const ftsRow = db.prepare(`SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'jobs_fts'`).get() as
    | { sql: string }
    | undefined;
  const ftsSql = ftsRow?.sql ?? '';
  const needsRebuild =
    !ftsRow || ftsSql.includes("content='jobs'") || !ftsSql.includes('url');
  if (needsRebuild) {
    db.exec(`DROP TABLE IF EXISTS jobs_fts`);
    db.exec(`
      CREATE VIRTUAL TABLE jobs_fts USING fts5(
        company, title, summary, url,
        tokenize='porter unicode61'
      );
    `);
    db.exec(`
      INSERT INTO jobs_fts(rowid, company, title, summary, url)
      SELECT rowid,
        COALESCE(company, ''),
        COALESCE(title, ''),
        COALESCE(summary, ''),
        COALESCE(url, '')
      FROM jobs;
    `);
  }
} catch (err) {
  console.warn('[db] jobs_fts repair skipped:', err);
}

// ---------------------------------------------------------------------------
// Numbered migration runner — applies server/migrations/*.sql in order.
// The schema_migrations table is bootstrapped by the runner itself.
// ---------------------------------------------------------------------------
runMigrations(db, path.join(__dirname, 'migrations'));

// ---------------------------------------------------------------------------
// Schema version tracking (additive — existing try/catch migrations remain).
// Increment CURRENT_SCHEMA_VERSION when adding a new migration block below.
// ---------------------------------------------------------------------------

const CURRENT_SCHEMA_VERSION = 1;

function getSchemaVersion(): number {
  try {
    const row = db.prepare(`SELECT value FROM profiles WHERE key = 'schema_version'`).get() as
      | { value: string }
      | undefined;
    return row ? parseInt(row.value, 10) : 0;
  } catch {
    return 0;
  }
}

function setSchemaVersion(version: number): void {
  db.prepare(`INSERT OR REPLACE INTO profiles (key, value) VALUES ('schema_version', ?)`).run(String(version));
}

const installedVersion = getSchemaVersion();
if (installedVersion < CURRENT_SCHEMA_VERSION) {
  // v1: baseline — all prior try/catch ADD COLUMN blocks handle the actual columns.
  // This entry just records that the schema is at least v1 on this installation.
  setSchemaVersion(CURRENT_SCHEMA_VERSION);
  console.log(`[db] Schema version set to ${CURRENT_SCHEMA_VERSION} (was ${installedVersion}).`);
}

// ---------------------------------------------------------------------------

export const logActivity = (
  level: 'INFO' | 'WARN' | 'ERROR',
  source: string,
  message: string,
  meta?: any
) => {
  db.prepare('INSERT INTO activity_log (level, source, message, meta) VALUES (?, ?, ?, ?)')
    .run(level, source, message, meta ? JSON.stringify(meta) : null);
};

/** Keep FTS5 index in sync after jobs table mutations (BUG-011 follow-up, CR-025). */
export function syncJobFts(jobRowid: number) {
  try {
    db.prepare('DELETE FROM jobs_fts WHERE rowid = ?').run(jobRowid);
    const job = db.prepare(
      'SELECT company, title, summary, url FROM jobs WHERE rowid = ?',
    ).get(jobRowid) as { company: string; title: string; summary: string | null; url: string | null } | undefined;
    if (!job) return;
    db.prepare(`
      INSERT INTO jobs_fts(rowid, company, title, summary, url)
      VALUES (?, ?, ?, ?, ?)
    `).run(
      jobRowid,
      job.company ?? '',
      job.title ?? '',
      job.summary ?? '',
      job.url ?? '',
    );
  } catch (err) {
    console.warn('[db] syncJobFts failed:', err);
  }
}

export function deleteJobFts(jobRowid: number) {
  try {
    db.prepare('DELETE FROM jobs_fts WHERE rowid = ?').run(jobRowid);
  } catch {
    /* ignore */
  }
}
