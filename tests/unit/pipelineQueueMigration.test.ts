// Tests/unit/pipelineQueueMigration.test.ts
// Story 1.2 (CR-119, DATA-006, FR-342, FR-343)
// Applies server/migrations/025_add_pipeline_queue.sql to an in-memory database
// and asserts the full schema shape: three tables, CHECK constraint, partial unique
// indexes, sha256 PK, nullable networking_contacts_raw, nullable line_number,
// and fencing_token default.

import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

const SQL_PATH = path.resolve(
  'server/migrations/025_add_pipeline_queue.sql',
);

function tableExists(db: Database.Database, name: string): boolean {
  const row = db
    .prepare(`SELECT name FROM sqlite_master WHERE type='table' AND name=?`)
    .get(name);
  return row !== undefined;
}

function getColumns(
  db: Database.Database,
  table: string,
): Array<{ name: string; type: string; notnull: number; dflt_value: string | null; pk: number }> {
  return db.prepare(`PRAGMA table_info(${table})`).all() as Array<{
    name: string;
    type: string;
    notnull: number;
    dflt_value: string | null;
    pk: number;
  }>;
}

function getIndexes(
  db: Database.Database,
  table: string,
): Array<{ name: string; unique: number }> {
  return db.prepare(`PRAGMA index_list(${table})`).all() as Array<{
    name: string;
    unique: number;
  }>;
}

describe('025_add_pipeline_queue migration', () => {
  let db: Database.Database;

  beforeEach(() => {
    db = new Database(':memory:');
    const sql = readFileSync(SQL_PATH, 'utf-8');
    // Execute all statements in the file
    db.exec(sql);
  });

  afterEach(() => {
    db.close();
  });

  // ── Table existence ───────────────────────────────────────────────────────

  it('creates pipeline_queue table', () => {
    expect(tableExists(db, 'pipeline_queue')).toBe(true);
  });

  it('creates csv_ingest_ledger table', () => {
    expect(tableExists(db, 'csv_ingest_ledger')).toBe(true);
  });

  it('creates csv_quarantine table', () => {
    expect(tableExists(db, 'csv_quarantine')).toBe(true);
  });

  // ── pipeline_queue columns ─────────────────────────────────────────────────

  it('pipeline_queue has slug column', () => {
    const cols = getColumns(db, 'pipeline_queue');
    expect(cols.some((c) => c.name === 'slug')).toBe(true);
  });

  it('pipeline_queue.networking_contacts_raw is nullable', () => {
    const cols = getColumns(db, 'pipeline_queue');
    const col = cols.find((c) => c.name === 'networking_contacts_raw');
    expect(col).toBeDefined();
    // notnull=0 means nullable
    expect(col!.notnull).toBe(0);
  });

  it('pipeline_queue.fencing_token is NOT NULL with default 0', () => {
    const cols = getColumns(db, 'pipeline_queue');
    const col = cols.find((c) => c.name === 'fencing_token');
    expect(col).toBeDefined();
    expect(col!.notnull).toBe(1);
    expect(col!.dflt_value).toBe('0');
  });

  // ── status CHECK constraint (all five values must be accepted) ────────────

  const VALID_STATUSES = ['queued', 'leased', 'in_progress', 'paused', 'done'] as const;

  for (const status of VALID_STATUSES) {
    it(`pipeline_queue accepts status='${status}'`, () => {
      expect(() =>
        db
          .prepare(
            `INSERT INTO pipeline_queue
              (slug, company, title, posting_key, folder_root, status, fencing_token, queued_at)
             VALUES (?, 'Acme', 'PM', 'acme-pm', 'pending_review', ?, 0, '2026-09-18T00:00:00Z')`,
          )
          .run(`test-slug-${status}`, status),
      ).not.toThrow();
    });
  }

  it('pipeline_queue rejects an invalid status value', () => {
    expect(() =>
      db
        .prepare(
          `INSERT INTO pipeline_queue
            (slug, company, title, posting_key, folder_root, status, fencing_token, queued_at)
           VALUES ('bad-slug', 'Acme', 'PM', 'acme-pm', 'pending_review', 'invalid_status', 0, '2026-09-18T00:00:00Z')`,
        )
        .run(),
    ).toThrow();
  });

  // ── Partial unique indexes on pipeline_queue ──────────────────────────────

  it('pipeline_queue has a partial unique index on url_key', () => {
    const indexes = getIndexes(db, 'pipeline_queue');
    // Find the url_key index
    const idx = indexes.find((i) => i.name.includes('url_key'));
    expect(idx).toBeDefined();
    expect(idx!.unique).toBe(1);
  });

  it('pipeline_queue has a partial unique index on posting_key', () => {
    const indexes = getIndexes(db, 'pipeline_queue');
    const idx = indexes.find((i) => i.name.includes('posting_key'));
    expect(idx).toBeDefined();
    expect(idx!.unique).toBe(1);
  });

  it('url_key partial index: two rows with same url_key both non-empty raises', () => {
    db.prepare(
      `INSERT INTO pipeline_queue
        (slug, company, title, posting_key, url_key, folder_root, status, fencing_token, queued_at)
       VALUES ('slug-1', 'Acme', 'PM', 'key-1', 'https://example.com/job/1', 'pending_review', 'queued', 0, '2026-09-18T00:00:00Z')`,
    ).run();
    expect(() =>
      db
        .prepare(
          `INSERT INTO pipeline_queue
            (slug, company, title, posting_key, url_key, folder_root, status, fencing_token, queued_at)
           VALUES ('slug-2', 'Acme', 'PM', 'key-2', 'https://example.com/job/1', 'pending_review', 'queued', 0, '2026-09-18T00:00:00Z')`,
        )
        .run(),
    ).toThrow();
  });

  it('posting_key partial index: two URL-less rows with same posting_key raises', () => {
    db.prepare(
      `INSERT INTO pipeline_queue
        (slug, company, title, posting_key, url_key, folder_root, status, fencing_token, queued_at)
       VALUES ('slug-a', 'Acme', 'PM', 'acme-pm', NULL, 'pending_review', 'queued', 0, '2026-09-18T00:00:00Z')`,
    ).run();
    expect(() =>
      db
        .prepare(
          `INSERT INTO pipeline_queue
            (slug, company, title, posting_key, url_key, folder_root, status, fencing_token, queued_at)
           VALUES ('slug-b', 'Acme', 'PM', 'acme-pm', NULL, 'pending_review', 'queued', 0, '2026-09-18T00:00:00Z')`,
        )
        .run(),
    ).toThrow();
  });

  it('posting_key partial index: two rows with different URL-backed posting_keys do NOT conflict', () => {
    // When url_key is non-empty, the posting_key partial index does NOT apply,
    // so two rows with the same posting_key but different url_keys must coexist.
    expect(() => {
      db.prepare(
        `INSERT INTO pipeline_queue
          (slug, company, title, posting_key, url_key, folder_root, status, fencing_token, queued_at)
         VALUES ('slug-x', 'Acme', 'PM', 'acme-pm', 'https://example.com/a', 'pending_review', 'queued', 0, '2026-09-18T00:00:00Z')`,
      ).run();
      db.prepare(
        `INSERT INTO pipeline_queue
          (slug, company, title, posting_key, url_key, folder_root, status, fencing_token, queued_at)
         VALUES ('slug-y', 'Acme', 'PM', 'acme-pm', 'https://example.com/b', 'pending_review', 'queued', 0, '2026-09-18T00:00:00Z')`,
      ).run();
    }).not.toThrow();
  });

  // ── csv_ingest_ledger ─────────────────────────────────────────────────────

  it('csv_ingest_ledger has sha256 as PRIMARY KEY', () => {
    const cols = getColumns(db, 'csv_ingest_ledger');
    const sha256col = cols.find((c) => c.name === 'sha256');
    expect(sha256col).toBeDefined();
    expect(sha256col!.pk).toBe(1);
  });

  it('csv_ingest_ledger.filename is not unique (display-only)', () => {
    // Two rows with different sha256 but same filename must both insert
    expect(() => {
      db.prepare(
        `INSERT INTO csv_ingest_ledger (sha256, filename, ingested_at, row_count, quarantine_count, status)
         VALUES ('aaa111', 'applyr_jobs.csv', '2026-09-18T00:00:00Z', 10, 0, 'ingested')`,
      ).run();
      db.prepare(
        `INSERT INTO csv_ingest_ledger (sha256, filename, ingested_at, row_count, quarantine_count, status)
         VALUES ('bbb222', 'applyr_jobs.csv', '2026-09-18T00:00:00Z', 5, 1, 'ingested')`,
      ).run();
    }).not.toThrow();
  });

  // ── csv_quarantine ────────────────────────────────────────────────────────

  it('csv_quarantine has scope column', () => {
    const cols = getColumns(db, 'csv_quarantine');
    expect(cols.some((c) => c.name === 'scope')).toBe(true);
  });

  it('csv_quarantine.line_number is nullable', () => {
    const cols = getColumns(db, 'csv_quarantine');
    const col = cols.find((c) => c.name === 'line_number');
    expect(col).toBeDefined();
    expect(col!.notnull).toBe(0);
  });

  it('csv_quarantine accepts file-scope row with null line_number', () => {
    expect(() =>
      db
        .prepare(
          `INSERT INTO csv_quarantine (scope, source_file, line_number, raw_payload, error_code, quarantine_reason)
           VALUES ('file', 'applyr_jobs.csv', NULL, '{}', 'FILE_UNPARSEABLE', 'CSV could not be parsed')`,
        )
        .run(),
    ).not.toThrow();
  });

  it('csv_quarantine accepts row-scope row with a line_number', () => {
    expect(() =>
      db
        .prepare(
          `INSERT INTO csv_quarantine (scope, source_file, line_number, raw_payload, error_code, quarantine_reason)
           VALUES ('row', 'applyr_jobs.csv', 5, '{"company":""}', 'EMPTY_COMPANY', 'Company field is blank')`,
        )
        .run(),
    ).not.toThrow();
  });

  // ── Idempotency ───────────────────────────────────────────────────────────

  it('re-executing the SQL (CREATE TABLE IF NOT EXISTS) does not throw', () => {
    const sql = readFileSync(SQL_PATH, 'utf-8');
    expect(() => db.exec(sql)).not.toThrow();
  });
});
