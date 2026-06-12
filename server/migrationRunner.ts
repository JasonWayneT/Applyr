import Database from 'better-sqlite3';
import { readdirSync, readFileSync } from 'fs';
import path from 'path';

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

    const sql = readFileSync(path.join(migrationsDir, file), 'utf-8');
    db.exec(sql);
    db.prepare(`INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)`)
      .run(file, new Date().toISOString());
  }
}
