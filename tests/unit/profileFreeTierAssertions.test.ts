// CR-112 Story 7.3 (FR-326/AC-424) — the llm_settings profile blob must preserve
// freeTierAssertions verbatim through the Settings route, and CR-104 secret masking
// must not touch it. Uses an in-memory SQLite profiles table (never the production
// database) and the real express router, per the pattern in
// tests/unit/reviewCenterRoute.test.ts plus the db.js mock pattern from
// tests/unit/groqClient.test.ts.
import express from 'express';
import http from 'http';
import type Database from 'better-sqlite3';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../server/db.js', async () => {
  const BetterSqlite3 = (await import('better-sqlite3')).default;
  const database = new BetterSqlite3(':memory:');
  database.exec('CREATE TABLE IF NOT EXISTS profiles (key TEXT PRIMARY KEY, value TEXT)');
  return { db: database, logActivity: vi.fn() };
});
vi.mock('../../server/shared.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../server/shared.js')>();
  return { ...actual, materializeJobSearchPrefs: vi.fn() };
});
vi.mock('../../server/pipeline/processRunner.js', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../server/pipeline/processRunner.js')>();
  return { ...actual, runDetached: vi.fn() };
});

const { db } = await import('../../server/db.js');
const profileRouter = (await import('../../server/routes/profile.js')).default;

const servers: http.Server[] = [];

async function startTestServer(): Promise<string> {
  const app = express();
  app.use(express.json());
  app.use(profileRouter);
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

function storedBlob(): Record<string, unknown> {
  const row = (db as Database.Database)
    .prepare("SELECT value FROM profiles WHERE key = 'llm_settings'")
    .get() as { value: string } | undefined;
  return row ? (JSON.parse(row.value) as Record<string, unknown>) : {};
}

afterEach(async () => {
  for (const server of servers.splice(0)) {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
  (db as Database.Database).prepare('DELETE FROM profiles').run();
});

const ATTESTATION = {
  provider: 'groq',
  acknowledged: true,
  statement:
    "I certify that this Applyr account's Groq configuration is on a free tier with billing disabled, that the configured Stage 0 call cannot incur a charge, and that I will re-certify if the provider terms or my account change.",
  asserted_at: '2026-09-15T00:00:00Z',
};

describe('POST /api/profile/llm_settings freeTierAssertions round-trip', () => {
  it('preserves freeTierAssertions verbatim while still masking secret API keys', async () => {
    const baseUrl = await startTestServer();
    const blob = {
      groqApiKey: 'gsk_1234567890abcd',
      costClasses: { groq: 'free_only' },
      freeTierAssertions: { groq: ATTESTATION },
    };
    const post = await fetch(`${baseUrl}/api/profile/llm_settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(blob),
    });
    expect(post.status).toBe(200);
    expect(storedBlob().freeTierAssertions).toEqual({ groq: ATTESTATION });

    const get = await fetch(`${baseUrl}/api/profile/llm_settings`);
    expect(get.status).toBe(200);
    const returned = (await get.json()) as Record<string, unknown>;
    // CR-104 masking still applies to secrets...
    expect(String(returned.groqApiKey)).toMatch(/^••••••••abcd$/);
    // ...but the attestation blob is not a secret and is returned untouched.
    expect(returned.freeTierAssertions).toEqual({ groq: ATTESTATION });
    expect(returned.costClasses).toEqual({ groq: 'free_only' });
  });

  it('keeps freeTierAssertions intact when a masked secret is saved back', async () => {
    const baseUrl = await startTestServer();
    const first = await fetch(`${baseUrl}/api/profile/llm_settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        groqApiKey: 'gsk_1234567890abcd',
        freeTierAssertions: { groq: ATTESTATION },
      }),
    });
    expect(first.status).toBe(200);

    // Client saves back the masked key it received, unchanged attestation in tow.
    const second = await fetch(`${baseUrl}/api/profile/llm_settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        groqApiKey: '••••••••abcd',
        freeTierAssertions: { groq: ATTESTATION },
      }),
    });
    expect(second.status).toBe(200);

    const stored = storedBlob();
    expect(stored.groqApiKey).toBe('gsk_1234567890abcd');
    expect(stored.freeTierAssertions).toEqual({ groq: ATTESTATION });
  });
});
