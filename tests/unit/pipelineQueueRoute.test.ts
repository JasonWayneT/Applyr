import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'fs';
import http from 'http';
import os from 'os';
import path from 'path';
import Database from 'better-sqlite3';
import express from 'express';
import { afterEach, describe, expect, it } from 'vitest';
import { createPipelineQueueRouter } from '../../server/routes/pipelineQueue.js';
import {
  assertInsideInbox,
  chosenUploadFilename,
  clientBasename,
  isCsvUpload,
  writeCsvUpload,
} from '../../server/services/pipelineQueueUpload.js';

const migration025 = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '025_add_pipeline_queue.sql'),
  'utf8',
);
const migration026 = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '026_add_pipeline_queue_paused_at.sql'),
  'utf8',
);

const databases: Database.Database[] = [];
const servers: http.Server[] = [];
const tempDirs: string[] = [];

async function startTestServer(
  database: Database.Database,
  deps: Parameters<typeof createPipelineQueueRouter>[1] = {},
): Promise<string> {
  const app = express();
  app.use(express.json());
  app.use(createPipelineQueueRouter(database, deps));
  const server = http.createServer(app);
  servers.push(server);
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => resolve());
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Test server did not bind to a port');
  return `http://127.0.0.1:${address.port}`;
}

function createDatabase(): Database.Database {
  const database = new Database(':memory:');
  database.exec(migration025);
  database.exec(migration026);
  database.prepare(
    `INSERT INTO pipeline_queue (
       slug, company, title, posting_key, folder_root, status, fencing_token,
       queued_at, locked_by, lease_expires_at, claimed_at, networking_contacts_raw
     ) VALUES ('leased_one', 'Leased Co', 'PM', 'leased||pm', 'pending_review', 'leased', 1,
       '2026-09-18T00:00:00+00:00', 'harness-1', '2099-01-01T00:00:00+00:00',
       '2026-09-18T12:00:00+00:00', 'SECRET_CONTACT')`,
  ).run();
  database.prepare(
    `INSERT INTO csv_quarantine (scope, source_file, line_number, raw_payload, error_code, quarantine_reason)
     VALUES ('row', 'jobs.csv', 3, 'JD_TEXT_MUST_NOT_LEAVE', 'EMPTY_COMPANY', 'empty')`,
  ).run();
  databases.push(database);
  return database;
}

afterEach(async () => {
  for (const server of servers.splice(0)) {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
  for (const database of databases.splice(0)) database.close();
  for (const dir of tempDirs.splice(0)) rmSync(dir, { recursive: true, force: true });
  delete process.env.APPLYR_API_TOKEN;
});

describe('pipeline queue API routes', () => {
  it('serves stats and quarantine without PII; POST stats stays unauthorized without token', async () => {
    const database = createDatabase();
    process.env.APPLYR_API_TOKEN = 'test-token';
    const baseUrl = await startTestServer(database);

    const unauthenticated = await fetch(`${baseUrl}/api/pipeline-queue/stats`);
    expect(unauthenticated.status).toBe(200);

    const stats = await unauthenticated.json() as {
      counts: { leased: number; quarantined: number };
      leases: Array<Record<string, unknown>>;
    };
    expect(stats.counts.leased).toBe(1);
    expect(stats.counts.quarantined).toBe(1);
    expect(JSON.stringify(stats)).not.toContain('SECRET_CONTACT');
    expect(JSON.stringify(stats)).not.toContain('raw_payload');
    expect(JSON.stringify(stats)).not.toContain('JD_TEXT_MUST_NOT_LEAVE');

    const unauthorizedPost = await fetch(`${baseUrl}/api/pipeline-queue/stats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'claim' }),
    });
    expect(unauthorizedPost.status).toBe(401);

    const quarantine = await fetch(`${baseUrl}/api/pipeline-queue/quarantine`);
    expect(quarantine.status).toBe(200);
    const body = await quarantine.json() as { items: Array<Record<string, unknown>> };
    expect(body.items).toHaveLength(1);
    expect(body.items[0].errorCode).toBe('EMPTY_COMPANY');
    expect(body.items[0].sourceFile).toBe('jobs.csv');
    expect(body.items[0].lineNumber).toBe(3);
    expect(JSON.stringify(body)).not.toContain('JD_TEXT_MUST_NOT_LEAVE');
    expect(body.items[0].raw_payload).toBeUndefined();
  });

  it('rejects upload without the API token', async () => {
    const database = createDatabase();
    process.env.APPLYR_API_TOKEN = 'test-token';
    const inboxDir = mkdtempSync(path.join(os.tmpdir(), 'applyr-inbox-'));
    tempDirs.push(inboxDir);
    const baseUrl = await startTestServer(database, { inboxDir, ingest: async () => ({ queued: 0, duplicate: 0, quarantined: 0 }) });

    const response = await fetch(`${baseUrl}/api/pipeline-queue/upload`, {
      method: 'POST',
      headers: { 'Content-Type': 'text/csv' },
      body: 'Company,Position\n',
    });
    expect(response.status).toBe(401);
    expect(readdirSync(inboxDir)).toEqual([]);
  });

  it('writes a server-chosen csv under the inbox and returns ingest counts', async () => {
    const database = createDatabase();
    process.env.APPLYR_API_TOKEN = 'test-token';
    const inboxDir = mkdtempSync(path.join(os.tmpdir(), 'applyr-inbox-'));
    tempDirs.push(inboxDir);
    const payload = 'Company,Position,Job Description,URL,Networking Contacts\nAcme,PM,long enough jd text here,https://example.test/a,\n';
    const baseUrl = await startTestServer(database, {
      inboxDir,
      ingest: async () => ({ queued: 2, duplicate: 1, quarantined: 3 }),
    });

    const response = await fetch(`${baseUrl}/api/pipeline-queue/upload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'text/csv',
        'X-Applyr-Token': 'test-token',
        'X-Applyr-Upload-Name': '..\\..\\Windows\\evil.csv',
      },
      body: payload,
    });
    expect(response.status).toBe(200);
    const body = await response.json() as { queued: number; duplicate: number; quarantined: number };
    expect(body).toEqual({ queued: 2, duplicate: 1, quarantined: 3 });
    const names = readdirSync(inboxDir);
    expect(names).toHaveLength(1);
    expect(names[0].startsWith('upload_')).toBe(true);
    expect(names[0].endsWith('.csv')).toBe(true);
    expect(names[0]).not.toContain('evil');
    expect(names[0]).not.toContain('Windows');
    expect(JSON.stringify(body)).not.toContain('long enough jd');
  });

  it('rejects a non-csv body and writes nothing', async () => {
    const database = createDatabase();
    process.env.APPLYR_API_TOKEN = 'test-token';
    const inboxDir = mkdtempSync(path.join(os.tmpdir(), 'applyr-inbox-'));
    tempDirs.push(inboxDir);
    const baseUrl = await startTestServer(database, {
      inboxDir,
      ingest: async () => ({ queued: 9, duplicate: 0, quarantined: 0 }),
    });

    const response = await fetch(`${baseUrl}/api/pipeline-queue/upload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-msdownload',
        'X-Applyr-Token': 'test-token',
        'X-Applyr-Upload-Name': 'payload.exe',
      },
      body: 'MZ not a csv',
    });
    expect(response.status).toBe(415);
    expect(readdirSync(inboxDir)).toEqual([]);
  });

  it('rejects an oversized csv and writes nothing', async () => {
    const database = createDatabase();
    process.env.APPLYR_API_TOKEN = 'test-token';
    const inboxDir = mkdtempSync(path.join(os.tmpdir(), 'applyr-inbox-'));
    tempDirs.push(inboxDir);
    const baseUrl = await startTestServer(database, {
      inboxDir,
      maxBytes: 16,
      ingest: async () => ({ queued: 9, duplicate: 0, quarantined: 0 }),
    });

    const response = await fetch(`${baseUrl}/api/pipeline-queue/upload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'text/csv',
        'X-Applyr-Token': 'test-token',
      },
      body: 'this-is-more-than-sixteen-bytes',
    });
    expect(response.status).toBe(413);
    expect(readdirSync(inboxDir)).toEqual([]);
  });
});

describe('pipeline queue upload path helpers', () => {
  it('never uses the client path as the on-disk name', () => {
    expect(clientBasename('C:\\\\Users\\\\Jason\\\\Downloads\\\\jobs.csv')).toBe('jobs.csv');
    expect(chosenUploadFilename(new Date('2026-09-18T21:00:00.000Z'), 'abcd1234')).toBe(
      'upload_2026-09-18T210000000Z_abcd1234.csv',
    );
    expect(isCsvUpload('text/csv', 'anything.exe')).toBe(true);
    expect(isCsvUpload('application/octet-stream', '..\\secret.csv')).toBe(true);
    expect(isCsvUpload('application/octet-stream', 'secret.exe')).toBe(false);
  });

  it('refuses a destination outside the inbox', () => {
    const inbox = path.resolve('/tmp/applyr-inbox');
    expect(() => assertInsideInbox(path.join(inbox, 'upload_x.csv'), inbox)).not.toThrow();
    expect(() => assertInsideInbox(path.join(inbox, '..', 'outside.csv'), inbox)).toThrow();
  });

  it('writes only under the inbox directory', () => {
    const inboxDir = mkdtempSync(path.join(os.tmpdir(), 'applyr-inbox-'));
    tempDirs.push(inboxDir);
    const dest = writeCsvUpload(Buffer.from('Company,Position\n'), inboxDir);
    expect(path.dirname(dest)).toBe(inboxDir);
    expect(path.basename(dest).startsWith('upload_')).toBe(true);
  });
});
