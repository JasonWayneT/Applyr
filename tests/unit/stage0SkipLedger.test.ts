import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import Database from 'better-sqlite3';
import { describe, expect, it } from 'vitest';
import { normalizeSkipUrl, postingKey } from '../../server/stage0SkipLedger.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const migration016 = path.join(here, '../../server/migrations/016_add_stage0_skips.sql');

describe('normalizeSkipUrl', () => {
  it('strips utm and gh_src (AC-326)', () => {
    expect(
      normalizeSkipUrl(
        'https://Job-Boards.Greenhouse.io/expel/jobs/123?gh_src=abc&utm_source=li',
      ),
    ).toBe('https://job-boards.greenhouse.io/expel/jobs/123');
  });

  it('returns null for empty', () => {
    expect(normalizeSkipUrl(null)).toBeNull();
    expect(normalizeSkipUrl('')).toBeNull();
  });
});

describe('postingKey', () => {
  it('lowercases company and title', () => {
    expect(postingKey(' Oracle ', 'Product Manager')).toBe('oracle||product manager');
  });
});

describe('migration 016 (live-DB safety)', () => {
  it('creates stage0_skips without altering an existing jobs table', () => {
    const db = new Database(':memory:');
    db.exec(`CREATE TABLE jobs (id TEXT PRIMARY KEY, company TEXT, status TEXT)`);
    db.exec(`INSERT INTO jobs (id, company, status) VALUES ('j1', 'Expel', 'Drafted')`);
    db.exec(readFileSync(migration016, 'utf8'));
    const tables = (
      db.prepare(`SELECT name FROM sqlite_master WHERE type='table'`).all() as Array<{ name: string }>
    ).map((r) => r.name);
    expect(tables).toContain('stage0_skips');
    expect(tables).toContain('jobs');
    const job = db.prepare(`SELECT id, company, status FROM jobs WHERE id = 'j1'`).get() as {
      id: string;
      company: string;
      status: string;
    };
    expect(job).toEqual({ id: 'j1', company: 'Expel', status: 'Drafted' });
    const cols = (
      db.prepare(`PRAGMA table_info(jobs)`).all() as Array<{ name: string }>
    ).map((c) => c.name);
    expect(cols).toEqual(['id', 'company', 'status']);
    db.close();
  });
});

