import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import { readStage0EvidenceUsage } from '../../server/routes/llmUsage.js';

const migrations = [
  '018_add_review_center.sql',
  '019_add_stage0_checkpoints.sql',
  '020_add_review_answer_history.sql',
]
  .map(file => readFileSync(path.join(process.cwd(), 'server', 'migrations', file), 'utf8'))
  .join('\n');

describe('Stage 0 usage summary', () => {
  const databases: Database.Database[] = [];

  afterEach(() => {
    for (const database of databases.splice(0)) database.close();
  });

  it('aggregates run telemetry without exposing payload contents', () => {
    const database = new Database(':memory:');
    databases.push(database);
    database.exec(migrations);
    const now = new Date().toISOString();
    const insert = database.prepare(`
      INSERT INTO stage0_runs (
        run_key, opportunity_key, jd_hash, prompt_version, provider_policy_hash,
        evidence_index_hash, status, metadata_json, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    insert.run(
      'run-1',
      'acme',
      'jd',
      'prompt',
      'policy',
      'evidence',
      'COMPLETE',
      JSON.stringify({
        stage0_cascade_batches: 1,
        stage0_cascade_provider_calls: 2,
        stage0_cascade_fallbacks: 1,
        raw_response: 'must not be returned',
      }),
      now,
      now,
    );
    insert.run(
      'run-2',
      'globex',
      'jd',
      'prompt',
      'policy',
      'evidence',
      'WAITING_FOR_INPUT',
      JSON.stringify({ stage0_cascade_batches: 1, stage0_cascade_provider_calls: 1 }),
      now,
      now,
    );
    database.prepare(`
      INSERT INTO pending_skill_confirmations (
        id, review_key, question_type, status, title, question, summary,
        opportunity_key, opportunity_company, opportunity_title, created_at, updated_at
      ) VALUES (?, ?, 'hard_gate_review', 'open', ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      'review-1',
      'hard:acme:license',
      'Hard gate',
      'Review',
      'Summary',
      'acme',
      'Acme',
      'Product Manager',
      now,
      now,
    );

    expect(readStage0EvidenceUsage(database)).toEqual({
      runs: 2,
      completedRuns: 1,
      waitingRuns: 1,
      failedRuns: 0,
      batches: 2,
      providerCalls: 3,
      fallbacks: 1,
      pendingConfirmations: 1,
    });
  });
});
