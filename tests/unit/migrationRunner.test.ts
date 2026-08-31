import Database from 'better-sqlite3';
import { mkdirSync, writeFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import path from 'path';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { runMigrations } from '../../server/migrationRunner.js';

describe('runMigrations', () => {
  let db: Database.Database;
  let migrationsDir: string;

  beforeEach(() => {
    db = new Database(':memory:');
    migrationsDir = path.join(tmpdir(), `migrations-test-${Date.now()}`);
    mkdirSync(migrationsDir);
  });

  afterEach(() => {
    db.close();
    rmSync(migrationsDir, { recursive: true });
  });

  it('creates schema_migrations table on first run', () => {
    runMigrations(db, migrationsDir);
    const row = db
      .prepare(`SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'`)
      .get();
    expect(row).toBeDefined();
  });

  it('schema_migrations has correct columns', () => {
    runMigrations(db, migrationsDir);
    const cols = db
      .prepare(`PRAGMA table_info(schema_migrations)`)
      .all() as Array<{ name: string; type: string; pk: number }>;
    const names = cols.map((c) => c.name);
    expect(names).toContain('id');
    expect(names).toContain('applied_at');
    const idCol = cols.find((c) => c.name === 'id')!;
    expect(idCol.pk).toBe(1);
  });

  it('applies pending migration files in ascending order', () => {
    writeFileSync(
      path.join(migrationsDir, '001_create_alpha.sql'),
      `CREATE TABLE IF NOT EXISTS alpha (id TEXT PRIMARY KEY);`,
    );
    writeFileSync(
      path.join(migrationsDir, '002_create_beta.sql'),
      `CREATE TABLE IF NOT EXISTS beta (id TEXT PRIMARY KEY);`,
    );

    runMigrations(db, migrationsDir);

    const alpha = db
      .prepare(`SELECT name FROM sqlite_master WHERE type='table' AND name='alpha'`)
      .get();
    const beta = db
      .prepare(`SELECT name FROM sqlite_master WHERE type='table' AND name='beta'`)
      .get();
    expect(alpha).toBeDefined();
    expect(beta).toBeDefined();
  });

  it('records applied migrations in schema_migrations', () => {
    writeFileSync(
      path.join(migrationsDir, '001_test.sql'),
      `CREATE TABLE IF NOT EXISTS recorded (id TEXT PRIMARY KEY);`,
    );

    runMigrations(db, migrationsDir);

    const row = db
      .prepare(`SELECT id, applied_at FROM schema_migrations WHERE id = ?`)
      .get('001_test.sql') as { id: string; applied_at: string } | undefined;
    expect(row).toBeDefined();
    expect(row!.id).toBe('001_test.sql');
    expect(row!.applied_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });

  it('skips already-applied migrations on re-run', () => {
    writeFileSync(
      path.join(migrationsDir, '001_idempotent.sql'),
      `CREATE TABLE IF NOT EXISTS idempotent (id TEXT PRIMARY KEY);`,
    );

    runMigrations(db, migrationsDir);
    runMigrations(db, migrationsDir);

    const count = db
      .prepare(`SELECT COUNT(*) as n FROM schema_migrations`)
      .get() as { n: number };
    expect(count.n).toBe(1);
  });

  it('handles missing migrations directory gracefully', () => {
    expect(() => runMigrations(db, '/nonexistent/path/migrations')).not.toThrow();
    const row = db
      .prepare(`SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'`)
      .get();
    expect(row).toBeDefined();
  });

  it('applies files in lexicographic (numeric prefix) order', () => {
    const applied: string[] = [];
    writeFileSync(
      path.join(migrationsDir, '002_second.sql'),
      `CREATE TABLE IF NOT EXISTS second (id TEXT PRIMARY KEY, seq INTEGER);`,
    );
    writeFileSync(
      path.join(migrationsDir, '001_first.sql'),
      `CREATE TABLE IF NOT EXISTS first (id TEXT PRIMARY KEY, seq INTEGER);`,
    );

    runMigrations(db, migrationsDir);

    const rows = db
      .prepare(`SELECT id FROM schema_migrations ORDER BY applied_at ASC`)
      .all() as Array<{ id: string }>;
    applied.push(...rows.map((r) => r.id));
    expect(applied[0]).toBe('001_first.sql');
    expect(applied[1]).toBe('002_second.sql');
  });

  it('rolls back on mid-migration failure and leaves migration unmarked', () => {
    // A migration with a valid statement followed by an invalid one — the
    // transaction must roll back the first statement so the migration can
    // be retried cleanly after the SQL is fixed.
    writeFileSync(
      path.join(migrationsDir, '001_partial.sql'),
      `CREATE TABLE partial (id TEXT PRIMARY KEY);\nINSERT INTO partial VALUES (1, 2);`,
    );

    expect(() => runMigrations(db, migrationsDir)).toThrow();

    // Table should NOT exist (rolled back)
    const table = db
      .prepare(`SELECT name FROM sqlite_master WHERE type='table' AND name='partial'`)
      .get();
    expect(table).toBeUndefined();

    // Migration should NOT be marked as applied
    const row = db
      .prepare(`SELECT id FROM schema_migrations WHERE id = ?`)
      .get('001_partial.sql');
    expect(row).toBeUndefined();
  });
});
