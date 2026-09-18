import { apiFetch } from './api';
import { STUCK_STALE_MINUTES } from '../types/pipelineQueue';
import type {
  PipelineLease,
  PipelineQueueCounts,
  PipelineQueueStats,
  PipelineQuarantineRow,
  PipelineStuckItem,
} from '../types/pipelineQueue';

export { STUCK_STALE_MINUTES };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function numberValue(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function stringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function normalizeCounts(value: unknown): PipelineQueueCounts {
  const source = isRecord(value) ? value : {};
  return {
    queued: numberValue(source.queued),
    leased: numberValue(source.leased),
    in_progress: numberValue(source.in_progress),
    paused: numberValue(source.paused),
    done: numberValue(source.done),
    quarantined: numberValue(source.quarantined),
  };
}

function normalizeLease(value: unknown, index: number): PipelineLease | null {
  if (!isRecord(value)) return null;
  const slug = stringValue(value.slug);
  if (!slug) return null;
  return {
    slug,
    company: stringValue(value.company, `company-${index}`),
    lockedBy: stringValue(value.lockedBy ?? value.locked_by),
    leaseExpiresAt: nullableString(value.leaseExpiresAt ?? value.lease_expires_at),
    leaseAgeMinutes: numberValue(value.leaseAgeMinutes ?? value.lease_age_minutes),
  };
}

function normalizeStuck(value: unknown, index: number): PipelineStuckItem | null {
  if (!isRecord(value)) return null;
  const slug = stringValue(value.slug);
  if (!slug) return null;
  const reason = value.reason === 'stale_receipt' ? 'stale_receipt' : 'expired_lease';
  return {
    slug,
    company: stringValue(value.company, `company-${index}`),
    status: stringValue(value.status),
    lockedBy: nullableString(value.lockedBy ?? value.locked_by),
    leaseExpiresAt: nullableString(value.leaseExpiresAt ?? value.lease_expires_at),
    reason,
    ageMinutes: numberValue(value.ageMinutes ?? value.age_minutes),
  };
}

export function normalizePipelineStats(value: unknown): PipelineQueueStats {
  const source = isRecord(value) ? value : {};
  const leases = Array.isArray(source.leases)
    ? source.leases.map(normalizeLease).filter((row): row is PipelineLease => row !== null)
    : [];
  const stuck = Array.isArray(source.stuck)
    ? source.stuck.map(normalizeStuck).filter((row): row is PipelineStuckItem => row !== null)
    : [];
  return {
    counts: normalizeCounts(source.counts),
    leases,
    stuck,
  };
}

export function normalizeQuarantineRows(value: unknown): PipelineQuarantineRow[] {
  const source = isRecord(value) ? value.items : value;
  if (!Array.isArray(source)) return [];
  return source.flatMap((row, index) => {
    if (!isRecord(row)) return [];
    if ('raw_payload' in row || 'networking_contacts_raw' in row) {
      // Drop PII fields if a server ever leaks them.
    }
    const id = numberValue(row.id, index);
    const errorCode = stringValue(row.errorCode ?? row.error_code);
    if (!errorCode) return [];
    const lineRaw = row.lineNumber ?? row.line_number;
    return [{
      id,
      sourceFile: stringValue(row.sourceFile ?? row.source_file),
      lineNumber: typeof lineRaw === 'number' ? lineRaw : null,
      errorCode,
      quarantineReason: stringValue(row.quarantineReason ?? row.quarantine_reason),
    }];
  });
}

export async function fetchPipelineQueueStats(): Promise<PipelineQueueStats> {
  const response = await apiFetch('/api/pipeline-queue/stats');
  if (!response.ok) {
    throw new Error('Pipeline queue stats could not load.');
  }
  return normalizePipelineStats(await response.json());
}

export async function fetchPipelineQuarantine(): Promise<PipelineQuarantineRow[]> {
  const response = await apiFetch('/api/pipeline-queue/quarantine');
  if (!response.ok) {
    throw new Error('Pipeline quarantine could not load.');
  }
  return normalizeQuarantineRows(await response.json());
}
