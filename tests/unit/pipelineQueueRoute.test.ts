import express from 'express';
import http from 'http';
import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import { createPipelineQueueRouter } from '../../server/routes/pipelineQueue.js';

const migration = readFileSync(
  path.join(process.cwd(), 'server', 'migrations', '025_add_pipeline_queue.sql'),
  'utf8',
);

const databases: Database.Database[] = [];
const servers: http.Server[] = [];

async function startTestServer(database: Database.Database): Promise<string> {
  const app = express();
  app.use(express.json());
  app.use(createPipelineQueueRouter(database));
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
  database.exec(migration);
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
  delete process.env.APPLYR_API_TOKEN;
});

describe('pipeline queue API routes', () => {
  it('serves read-only stats and quarantine without PII and without POST handlers', async () => {
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
});
