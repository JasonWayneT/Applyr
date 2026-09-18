import type Database from 'better-sqlite3';
import { db } from '../db.js';

export const STUCK_STALE_MINUTES = 120;

export interface QueueCounts {
  queued: number;
  leased: number;
  in_progress: number;
  paused: number;
  done: number;
  quarantined: number;
}

export interface ActiveLease {
  slug: string;
  company: string;
  lockedBy: string;
  leaseExpiresAt: string | null;
  leaseAgeMinutes: number;
}

export interface StuckItem {
  slug: string;
  company: string;
  status: string;
  lockedBy: string | null;
  leaseExpiresAt: string | null;
  reason: 'expired_lease' | 'stale_receipt';
  ageMinutes: number;
}

export interface QuarantineRow {
  id: number;
  sourceFile: string;
  lineNumber: number | null;
  errorCode: string;
  quarantineReason: string;
}

type CountRow = { status: string; n: number };
type LeaseRow = {
  slug: string;
  company: string;
  locked_by: string | null;
  lease_expires_at: string | null;
  claimed_at: string | null;
  updated_at: string | null;
  status: string;
};
type QuarantineDbRow = {
  id: number;
  source_file: string;
  line_number: number | null;
  error_code: string;
  quarantine_reason: string;
};

function minutesSince(iso: string | null, nowMs: number): number {
  if (!iso) return 0;
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return 0;
  return Math.max(0, Math.round((nowMs - then) / 60000));
}

export function queueCounts(database: Database.Database = db): QueueCounts {
  const rows = database.prepare(
    "SELECT status, COUNT(*) AS n FROM pipeline_queue GROUP BY status",
  ).all() as CountRow[];
  const counts: QueueCounts = {
    queued: 0,
    leased: 0,
    in_progress: 0,
    paused: 0,
    done: 0,
    quarantined: 0,
  };
  for (const row of rows) {
    if (row.status === 'queued') counts.queued = row.n;
    else if (row.status === 'leased') counts.leased = row.n;
    else if (row.status === 'in_progress') counts.in_progress = row.n;
    else if (row.status === 'paused') counts.paused = row.n;
    else if (row.status === 'done') counts.done = row.n;
  }
  const quarantined = database.prepare(
    'SELECT COUNT(*) AS n FROM csv_quarantine',
  ).get() as { n: number };
  counts.quarantined = quarantined.n;
  return counts;
}

export function activeLeases(database: Database.Database = db): ActiveLease[] {
  const now = Date.now();
  const rows = database.prepare(
    `SELECT slug, company, locked_by, lease_expires_at, claimed_at, updated_at, status
     FROM pipeline_queue
     WHERE locked_by IS NOT NULL AND status IN ('leased', 'in_progress')
     ORDER BY claimed_at`,
  ).all() as LeaseRow[];
  return rows.map(row => ({
    slug: row.slug,
    company: row.company,
    lockedBy: row.locked_by ?? '',
    leaseExpiresAt: row.lease_expires_at,
    leaseAgeMinutes: minutesSince(row.claimed_at, now),
  }));
}

export function stuckItems(
  staleMinutes: number = STUCK_STALE_MINUTES,
  database: Database.Database = db,
): StuckItem[] {
  const now = Date.now();
  const staleMs = staleMinutes * 60_000;
  const rows = database.prepare(
    `SELECT slug, company, locked_by, lease_expires_at, claimed_at, updated_at, status
     FROM pipeline_queue
     WHERE status IN ('leased', 'in_progress', 'paused')`,
  ).all() as LeaseRow[];
  const items: StuckItem[] = [];
  for (const row of rows) {
    const expired = Boolean(
      row.lease_expires_at && Date.parse(row.lease_expires_at) <= now
      && (row.status === 'leased' || row.status === 'in_progress'),
    );
    const stale = Boolean(
      row.updated_at && (now - Date.parse(row.updated_at) >= staleMs),
    );
    if (!expired && !stale) continue;
    items.push({
      slug: row.slug,
      company: row.company,
      status: row.status,
      lockedBy: row.locked_by,
      leaseExpiresAt: row.lease_expires_at,
      reason: expired ? 'expired_lease' : 'stale_receipt',
      ageMinutes: minutesSince(row.updated_at, now),
    });
  }
  return items;
}

export function quarantineRows(database: Database.Database = db): QuarantineRow[] {
  const rows = database.prepare(
    `SELECT id, source_file, line_number, error_code, quarantine_reason
     FROM csv_quarantine
     ORDER BY id`,
  ).all() as QuarantineDbRow[];
  return rows.map(row => ({
    id: row.id,
    sourceFile: row.source_file,
    lineNumber: row.line_number,
    errorCode: row.error_code,
    quarantineReason: row.quarantine_reason,
  }));
}
