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
} from '../../server/repository/pipelineQueueRepository.js';

const migration = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '025_add_pipeline_queue.sql'),
  'utf8',
);

const databases: Database.Database[] = [];

function createDatabase(): Database.Database {
  const database = new Database(':memory:');
  database.exec(migration);
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
  },
) {
  database.prepare(
    `INSERT INTO pipeline_queue (
       slug, company, title, posting_key, folder_root, status, fencing_token,
       queued_at, locked_by, lease_expires_at, claimed_at, updated_at, networking_contacts_raw
     ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)`,
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
  );
}

describe('pipelineQueueRepository', () => {
  it('returns six counts and omits PII columns from leases and quarantine', () => {
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
});
