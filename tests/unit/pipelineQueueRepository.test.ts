import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import {
  STUCK_STALE_MINUTES,
  activeLeases,
  quarantineRows,
  queueCounts,
  stuckItems,
  waitingItems,
  decisionItems,
} from '../../server/repository/pipelineQueueRepository.js';

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
  database.exec(migration);
  database.exec(migration026);
  database.exec(migration027);
  databases.push(database);
  return database;
}

afterEach(() => {
  for (const database of databases.splice(0)) database.close();
});

function insertQueue(
  database: Database.Database,
  values: {
    slug: string;
    status: string;
    lockedBy?: string | null;
    leaseExpiresAt?: string | null;
    claimedAt?: string | null;
    updatedAt?: string | null;
    contacts?: string | null;
    pausedReason?: string | null;
  },
) {
  database.prepare(
    `INSERT INTO pipeline_queue (
       slug, company, title, posting_key, folder_root, status, fencing_token,
       queued_at, locked_by, lease_expires_at, claimed_at, updated_at,
       networking_contacts_raw, paused_reason
     ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    values.slug,
    values.slug,
    'PM',
    `${values.slug}||pm`,
    'pending_review',
    values.status,
    '2026-09-18T00:00:00+00:00',
    values.lockedBy ?? null,
    values.leaseExpiresAt ?? null,
    values.claimedAt ?? null,
    values.updatedAt ?? '2026-09-18T12:00:00+00:00',
    values.contacts ?? 'SECRET_CONTACT',
    values.pausedReason ?? null,
  );
}

describe('pipelineQueueRepository', () => {
  it('returns seven counts and omits PII columns from leases and quarantine', () => {
    const database = createDatabase();
    insertQueue(database, { slug: 'queued_one', status: 'queued' });
    insertQueue(database, {
      slug: 'leased_one',
      status: 'leased',
      lockedBy: 'harness-1',
      leaseExpiresAt: '2099-01-01T00:00:00+00:00',
      claimedAt: new Date(Date.now() - 15 * 60_000).toISOString(),
    });
    database.prepare(
      `INSERT INTO csv_quarantine (scope, source_file, line_number, raw_payload, error_code, quarantine_reason)
       VALUES ('row', 'jobs.csv', 4, 'JD_TEXT_MUST_NOT_LEAVE', 'JD_TOO_SHORT', 'short')`,
    ).run();

    const counts = queueCounts(database);
    expect(counts).toEqual({
      queued: 1,
      leased: 1,
      in_progress: 0,
      paused: 0,
      ready_to_finalize: 0,
      done: 0,
      quarantined: 1,
    });
    expect(STUCK_STALE_MINUTES).toBe(120);

    const leases = activeLeases(database);
    expect(leases).toHaveLength(1);
    expect(leases[0].slug).toBe('leased_one');
    expect(leases[0].lockedBy).toBe('harness-1');
    expect(leases[0].leaseAgeMinutes).toBeGreaterThanOrEqual(14);
    expect(JSON.stringify(leases)).not.toContain('SECRET_CONTACT');
    expect(JSON.stringify(leases)).not.toContain('raw_payload');

    const quarantine = quarantineRows(database);
    expect(quarantine).toEqual([
      {
        id: 1,
        sourceFile: 'jobs.csv',
        lineNumber: 4,
        errorCode: 'JD_TOO_SHORT',
        quarantineReason: 'short',
      },
    ]);
    expect(JSON.stringify(quarantine)).not.toContain('JD_TEXT_MUST_NOT_LEAVE');
    expect(Object.keys(quarantine[0])).not.toContain('raw_payload');
  });

  it('flags expired leases and stale receipts as stuck', () => {
    const database = createDatabase();
    insertQueue(database, {
      slug: 'expired_one',
      status: 'in_progress',
      lockedBy: 'harness-1',
      leaseExpiresAt: '2000-01-01T00:00:00+00:00',
      claimedAt: '2000-01-01T00:00:00+00:00',
      updatedAt: new Date().toISOString(),
    });
    insertQueue(database, {
      slug: 'stale_one',
      status: 'paused',
      updatedAt: new Date(Date.now() - 3 * 60 * 60_000).toISOString(),
    });
    const stuck = stuckItems(120, database);
    const slugs = stuck.map(row => row.slug).sort();
    expect(slugs).toEqual(['expired_one', 'stale_one']);
    expect(stuck.find(row => row.slug === 'expired_one')?.reason).toBe('expired_lease');
    expect(stuck.find(row => row.slug === 'stale_one')?.reason).toBe('stale_receipt');
  });

  it('counts ready_to_finalize separately from paused and does not mark it stuck', () => {
    const database = createDatabase();
    insertQueue(database, { slug: 'needs_human', status: 'paused' });
    insertQueue(database, {
      slug: 'rentana',
      status: 'paused',
      pausedReason: 'ready_to_finalize',
      updatedAt: new Date(Date.now() - 3 * 60 * 60_000).toISOString(),
    });
    expect(queueCounts(database)).toEqual({
      queued: 0,
      leased: 0,
      in_progress: 0,
      paused: 1,
      ready_to_finalize: 1,
      done: 0,
      quarantined: 0,
    });
    expect(stuckItems(120, database).map(row => row.slug)).toEqual(['needs_human']);
    const waiting = waitingItems(database);
    expect(waiting.map(row => row.slug).sort()).toEqual(['needs_human', 'rentana']);
    expect(waiting.find(row => row.slug === 'rentana')?.reason).toBe(
      'Finished packet. The next run saves it into the app for review.',
    );
    const decisions = decisionItems(database, Date.parse('2026-09-18T13:00:00+00:00'));
    expect(decisions.find(row => row.slug === 'rentana')?.state).toBe('Continuing');
  });

  it('labels a score skip, a live run, a failed draft, and an expired lease', () => {
    const database = createDatabase();
    insertQueue(database, { slug: 'kept', status: 'queued' });
    insertQueue(database, {
      slug: 'healthcare',
      status: 'paused',
      pausedReason: 'decided_skip',
    });
    insertQueue(database, {
      slug: 'running',
      status: 'in_progress',
      lockedBy: 'worker',
      leaseExpiresAt: '2026-09-18T13:30:00+00:00',
    });
    insertQueue(database, {
      slug: 'allstate',
      status: 'in_progress',
      lockedBy: 'worker',
      leaseExpiresAt: '2026-09-18T12:00:00+00:00',
    });
    const decisions = decisionItems(database, Date.parse('2026-09-18T13:00:00+00:00'));
    expect(decisions.find(row => row.slug === 'kept')?.state).toBe('Continuing');
    expect(decisions.find(row => row.slug === 'healthcare')?.state).toBe('Skipped');
    expect(decisions.find(row => row.slug === 'running')?.state).toBe('Running');
    expect(decisions.find(row => row.slug === 'allstate')?.state).toBe('Failed');
    expect(decisions.some(row => row.state === 'Waiting' as string)).toBe(false);
  });
});
