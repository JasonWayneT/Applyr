import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { PROJECT_ROOT } from '../shared.js';
import { pythonScriptPath, runBuffered } from '../pipeline/processRunner.js';

export const UPLOAD_MAX_BYTES = 10 * 1024 * 1024;
export const CSV_INBOX_DIR = path.join(PROJECT_ROOT, 'data', 'inbox', 'csv');
export const PIPELINE_DB_PATH = path.join(PROJECT_ROOT, 'data', 'jobagent.sqlite');

export type IngestCounts = {
  queued: number;
  duplicate: number;
  quarantined: number;
};

export function clientBasename(clientName: string | undefined): string {
  if (!clientName) return '';
  return path.posix.basename(clientName.replace(/\\/g, '/'));
}

export function isCsvUpload(contentType: string | undefined, clientName: string | undefined): boolean {
  const type = (contentType ?? '').toLowerCase();
  if (type.includes('text/csv') || type.includes('application/csv') || type.endsWith('+csv')) {
    return true;
  }
  const base = clientBasename(clientName).toLowerCase();
  return base.endsWith('.csv') && !base.includes('\0');
}

export function assertInsideInbox(dest: string, inboxDir: string): void {
  const resolvedDest = path.resolve(dest);
  const resolvedInbox = path.resolve(inboxDir);
  const prefix = resolvedInbox.endsWith(path.sep) ? resolvedInbox : resolvedInbox + path.sep;
  if (resolvedDest !== resolvedInbox && !resolvedDest.startsWith(prefix)) {
    throw new Error('upload path escaped inbox');
  }
}

export function chosenUploadFilename(
  now = new Date(),
  randomHex = crypto.randomBytes(8).toString('hex'),
): string {
  const stamp = now.toISOString().replace(/[:.]/g, '');
  return `upload_${stamp}_${randomHex}.csv`;
}

export function writeCsvUpload(buffer: Buffer, inboxDir: string): string {
  fs.mkdirSync(inboxDir, { recursive: true });
  const dest = path.join(inboxDir, chosenUploadFilename());
  assertInsideInbox(dest, inboxDir);
  const fd = fs.openSync(dest, 'wx');
  try {
    fs.writeFileSync(fd, buffer);
  } finally {
    fs.closeSync(fd);
  }
  return dest;
}

function numberField(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

export async function runInboxIngest(inboxDir: string, dbPath: string): Promise<IngestCounts> {
  const result = await runBuffered([
    pythonScriptPath('ingest_csv_queue.py'),
    '--json',
    '--inbox',
    inboxDir,
    '--db',
    dbPath,
  ]);
  if (result.code !== 0) {
    throw new Error('ingest failed');
  }
  const parsed = JSON.parse(result.stdout) as Record<string, unknown>;
  return {
    queued: numberField(parsed.queued),
    duplicate: numberField(parsed.duplicate),
    quarantined: numberField(parsed.quarantined),
  };
}
