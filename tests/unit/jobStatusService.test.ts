import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import { applyJobStatusUpdate } from '../../server/services/jobStatusService.js';
import { normalizeSkipUrl, postingKey } from '../../server/stage0SkipLedger.js';

const migration = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '025_add_pipeline_queue.sql'),
  'utf8',
);
const migration026 = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '026_add_pipeline_queue_paused_at.sql'),
  'utf8',
);
const migration027 = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '027_add_pipeline_queue_paused_reason.sql'),
  'utf8',
);

const databases: Database.Database[] = [];

function createDatabase(): Database.Database {
  const database = new Database(':memory:');
  database.exec(`
    CREATE TABLE jobs (
      id TEXT PRIMARY KEY,
      company TEXT NOT NULL,
      title TEXT NOT NULL,
      url TEXT,
      status TEXT DEFAULT 'New',
      interview_date DATETIME,
      applied_at DATETIME,
      rejection_stage TEXT,
      rejection_type TEXT,
      outcome_notes TEXT,
      status_changed_at DATETIME
    );
  `);
  database.exec(migration);
  database.exec(migration026);
  database.exec(migration027);
  databases.push(database);
  return database;
}

afterEach(() => {
  for (const database of databases.splice(0)) database.close();
});

function insertJob(
  database: Database.Database,
  values: {
    id: string;
    company: string;
    title: string;
    url?: string | null;
    status?: string;
    interviewDate?: string | null;
  },
): void {
  database.prepare(
    `INSERT INTO jobs (id, company, title, url, status, interview_date)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).run(
    values.id,
    values.company,
    values.title,
    values.url ?? null,
    values.status ?? 'New',
    values.interviewDate ?? null,
  );
}

function insertQueue(
  database: Database.Database,
  values: {
    slug: string;
    company: string;
    title: string;
    url?: string | null;
    status: string;
    lockedBy?: string | null;
    pausedReason?: string | null;
  },
): void {
  const urlKey = normalizeSkipUrl(values.url);
  database.prepare(
    `INSERT INTO pipeline_queue (
       slug, company, title, url, url_key, posting_key, folder_root, status,
       fencing_token, queued_at, locked_by, updated_at, paused_reason
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)`,
  ).run(
    values.slug,
    values.company,
    values.title,
    values.url ?? null,
    urlKey,
    postingKey(values.company, values.title),
    'pending_review',
    values.status,
    '2026-09-18T00:00:00+00:00',
    values.lockedBy ?? null,
    '2026-09-18T12:00:00+00:00',
    values.pausedReason ?? 'waiting_for_llm',
  );
}

function queueRow(database: Database.Database, slug: string): {
  status: string;
  paused_reason: string | null;
  locked_by: string | null;
  updated_at: string | null;
} {
  return database.prepare(
    `SELECT status, paused_reason, locked_by, updated_at
     FROM pipeline_queue WHERE slug = ?`,
  ).get(slug) as {
    status: string;
    paused_reason: string | null;
    locked_by: string | null;
    updated_at: string | null;
  };
}

function seedPausedMatch(
  database: Database.Database,
  slug: string,
  extras?: { jobStatus?: string; queueStatus?: string; lockedBy?: string | null },
): { id: string; company: string; title: string; url: string } {
  const company = `Synth Status ${slug} Co`;
  const title = 'Platform Product Manager';
  const url = `https://example.test/jobs/${slug}?utm_source=board`;
  const id = `synth-status-${slug}`;
  insertJob(database, {
    id,
    company,
    title,
    url,
    status: extras?.jobStatus ?? 'New',
  });
  insertQueue(database, {
    slug,
    company,
    title,
    url,
    status: extras?.queueStatus ?? 'paused',
    lockedBy: extras?.lockedBy ?? null,
  });
  return { id, company, title, url };
}

describe('applyJobStatusUpdate queue close (CR-123 / FR-364 / AC-473)', () => {
  it.each([
    'Applied',
    'Recruiter Screen',
    'Core Interviews',
    'Offer and Negotiation',
  ] as const)('closes a paused match when status becomes %s', (status) => {
    const database = createDatabase();
    const slug = status.toLowerCase().replace(/[^a-z]+/g, '-');
    const seeded = seedPausedMatch(database, slug);
    const interviewDate =
      status === 'Recruiter Screen' || status === 'Core Interviews'
        ? '2026-10-01T15:00:00'
        : undefined;

    const result = applyJobStatusUpdate(
      seeded.id,
      { status, interview_date: interviewDate },
      database,
    );

    expect(result).toEqual({ kind: 'updated', status });
    const row = queueRow(database, slug);
    expect(row.status).toBe('done');
    expect(row.paused_reason).toBeNull();
    expect(row.updated_at).not.toBe('2026-09-18T12:00:00+00:00');
  });

  it.each(['Backlog', 'Drafted'] as const)(
    'leaves a paused match when status becomes %s',
    (status) => {
      const database = createDatabase();
      const slug = status.toLowerCase();
      const seeded = seedPausedMatch(database, slug, { jobStatus: status });

      const result = applyJobStatusUpdate(seeded.id, { status }, database);

      expect(result).toEqual({ kind: 'updated', status });
      const row = queueRow(database, slug);
      expect(row.status).toBe('paused');
      expect(row.paused_reason).toBe('waiting_for_llm');
    },
  );

  it('leaves a leased match leased', () => {
    const database = createDatabase();
    const slug = 'leased-match';
    const seeded = seedPausedMatch(database, slug, {
      queueStatus: 'leased',
      lockedBy: 'harness-1',
    });

    const result = applyJobStatusUpdate(seeded.id, { status: 'Applied' }, database);

    expect(result).toEqual({ kind: 'updated', status: 'Applied' });
    const row = queueRow(database, slug);
    expect(row.status).toBe('leased');
    expect(row.locked_by).toBe('harness-1');
  });
});
