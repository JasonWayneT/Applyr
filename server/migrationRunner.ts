import Database from 'better-sqlite3';
import { readdirSync, readFileSync } from 'fs';
import path from 'path';

function columnExists(db: Database.Database, table: string, column: string): boolean {
  const rows = db.prepare(`PRAGMA table_info(${table})`).all() as Array<{ name: string }>;
  return rows.some((row) => row.name === column);
}

export function runMigrations(db: Database.Database, migrationsDir: string): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id TEXT PRIMARY KEY,
      applied_at TEXT NOT NULL
    )
  `);

  let files: string[];
  try {
    files = readdirSync(migrationsDir)
      .filter((f) => f.endsWith('.sql'))
      .sort();
  } catch {
    return;
  }

  for (const file of files) {
    const already = db
      .prepare(`SELECT id FROM schema_migrations WHERE id = ?`)
      .get(file);
    if (already) continue;

    // 026 ADD COLUMN is also applied by Python ensure_schema(). Skip the ALTER
    // when the column already exists so a Python-first DB still boots.
    if (file === '026_add_pipeline_queue_paused_at.sql' && columnExists(db, 'pipeline_queue', 'paused_at')) {
      db.prepare(`INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)`)
        .run(file, new Date().toISOString());
      continue;
    }
    if (file === '027_add_pipeline_queue_paused_reason.sql' && columnExists(db, 'pipeline_queue', 'paused_reason')) {
      db.prepare(`INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)`)
        .run(file, new Date().toISOString());
      continue;
    }
    if (file === '028_add_pipeline_queue_requeue_audit.sql' && columnExists(db, 'pipeline_queue', 'requeued_by')) {
      db.prepare(`INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)`)
        .run(file, new Date().toISOString());
      continue;
    }

    const sql = readFileSync(path.join(migrationsDir, file), 'utf-8');
    // Wrap in a transaction so a mid-migration failure rolls back all changes,
    // leaving the migration unmarked and cleanly retriable on next startup.
    db.transaction(() => {
      db.exec(sql);
      db.prepare(`INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)`)
        .run(file, new Date().toISOString());
    })();
  }
}
