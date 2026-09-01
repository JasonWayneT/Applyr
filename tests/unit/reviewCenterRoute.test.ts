import express from 'express';
import http from 'http';
import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import { createHardGateReview, createSkillConfirmation } from '../../server/repository/reviewCenterRepository.js';
import { createReviewCenterRouter } from '../../server/routes/reviewCenter.js';

const migrations = [
  '018_add_review_center.sql',
  '020_add_review_answer_history.sql',
  '021_add_evidence_promotion_proposals.sql',
].map(file => readFileSync(path.join(process.cwd(), 'server', 'migrations', file), 'utf8')).join('\n');

const databases: Database.Database[] = [];
const servers: http.Server[] = [];

async function startTestServer(database: Database.Database): Promise<string> {
  const app = express();
  app.use(express.json());
  app.use(createReviewCenterRouter(database, () => undefined));
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
  database.exec(migrations);
  databases.push(database);
  return database;
}

async function request(baseUrl: string, pathName: string, init?: RequestInit): Promise<Response> {
  return fetch(`${baseUrl}${pathName}`, init);
}

afterEach(async () => {
  for (const server of servers.splice(0)) {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
  for (const database of databases.splice(0)) database.close();
  delete process.env.APPLYR_API_TOKEN;
});

describe('Review Center API routes', () => {
  it('requires a mutation token and reads from the injected database', async () => {
    const database = createDatabase();
    createSkillConfirmation(
      {
        skillKey: 'Trello',
        title: 'Trello',
        question: 'Have you used Trello?',
        summary: 'Answer this question.',
        opportunityKey: 'acme',
        opportunityCompany: 'Acme',
        opportunityTitle: 'Product Manager',
      },
      database,
    );
    process.env.APPLYR_API_TOKEN = 'test-token';
    const baseUrl = await startTestServer(database);

    const unauthorized = await request(baseUrl, '/api/review-center/items/skill%3Atrello/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'CONFIRMED_USE' }),
    });
    expect(unauthorized.status).toBe(401);

    const list = await request(baseUrl, '/api/review-center/items?status=open');
    expect(list.status).toBe(200);
    expect((await list.json()).items).toHaveLength(1);
  });

  it('answers grouped skills, supports repeats, and keeps enrichment separate', async () => {
    const database = createDatabase();
    createSkillConfirmation(
      {
        skillKey: 'ServiceNow (ITSM)',
        title: 'ServiceNow',
        question: 'Have you used ServiceNow?',
        summary: 'Answer this question.',
        opportunityKey: 'acme',
        opportunityCompany: 'Acme',
        opportunityTitle: 'Product Manager',
      },
      database,
    );
    createSkillConfirmation(
      {
        skillKey: 'servicenow_itsm',
        title: 'ServiceNow',
        question: 'Have you used ServiceNow?',
        summary: 'Answer this question.',
        opportunityKey: 'globex',
        opportunityCompany: 'Globex',
        opportunityTitle: 'Product Owner',
      },
      database,
    );
    const baseUrl = await startTestServer(database);
    const answer = await request(baseUrl, '/api/review-center/items/skill%3Aservicenow_itsm/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'CONFIRMED_USE' }),
    });
    expect(answer.status).toBe(200);

    const open = await request(baseUrl, '/api/review-center/items?status=open');
    const openItems = (await open.json()).items;
    expect(openItems).toHaveLength(1);
    expect(openItems[0].type).toBe('evidence_enrichment');
    expect(openItems[0].affectedOpportunities).toHaveLength(2);

    const repeat = await request(baseUrl, '/api/review-center/items/skill%3Aservicenow_itsm/answer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'CONFIRMED_USE' }),
    });
    expect(repeat.status).toBe(200);
  });

  it('supports hard-gate review actions and rejects mismatched answers', async () => {
    const database = createDatabase();
    const review = createHardGateReview(
      {
        itemKey: 'required:0:license',
        requirement: 'Requires an active professional license',
        opportunityKey: 'acme',
        opportunityCompany: 'Acme',
        opportunityTitle: 'Product Manager',
      },
      database,
    );
    const baseUrl = await startTestServer(database);

    const invalid = await request(baseUrl, `/api/review-center/items/${encodeURIComponent(review.reviewKey)}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'CONFIRMED_USE' }),
    });
    expect(invalid.status).toBe(400);

    const waiting = await request(baseUrl, `/api/review-center/items/${encodeURIComponent(review.reviewKey)}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'NEEDS_MORE_INFO' }),
    });
    expect(waiting.status).toBe(200);

    const confirmed = await request(baseUrl, `/api/review-center/items/${encodeURIComponent(review.reviewKey)}/answer`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answer: 'CONFIRM_HARD' }),
    });
    expect(confirmed.status).toBe(200);
    expect((await (await request(baseUrl, '/api/review-center/items?status=open')).json()).items).toHaveLength(0);
  });
});
