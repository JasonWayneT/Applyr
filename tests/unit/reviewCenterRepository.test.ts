import Database from 'better-sqlite3';
import { readFileSync } from 'fs';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import {
  answerReviewItem,
  canonicalSkillKey,
  createHardGateReview,
  createSkillConfirmation,
  listReviewItems,
  verifyEvidencePromotion,
} from '../../server/repository/reviewCenterRepository.js';

const migrations = [
  readFileSync(
    path.join(process.cwd(), 'server', 'migrations', '018_add_review_center.sql'),
    'utf8',
  ),
  readFileSync(
    path.join(process.cwd(), 'server', 'migrations', '020_add_review_answer_history.sql'),
    'utf8',
  ),
  readFileSync(
    path.join(process.cwd(), 'server', 'migrations', '021_add_evidence_promotion_proposals.sql'),
    'utf8',
  ),
  readFileSync(
    path.join(process.cwd(), 'server', 'migrations', '022_add_bad_data_answer.sql'),
    'utf8',
  ),
].join('\n');

describe('review center repository', () => {
  const databases: Database.Database[] = [];

  afterEach(() => {
    for (const database of databases.splice(0)) database.close();
  });

  function createDatabase(): Database.Database {
    const database = new Database(':memory:');
    database.exec(migrations);
    databases.push(database);
    return database;
  }

  function createReview(database: Database.Database) {
    return createSkillConfirmation(
      {
        skillKey: 'ServiceNow (ITSM)',
        title: 'ServiceNow',
        question: 'Have you used ServiceNow in your work?',
        summary: 'Answer before this opportunity continues.',
        requirement: 'Experience with ServiceNow',
        opportunityKey: 'acme',
        opportunityCompany: 'Acme',
        opportunityTitle: 'Product Manager',
      },
      database,
    );
  }

  it('uses a canonical key and groups repeated skill occurrences', () => {
    const database = createDatabase();
    expect(canonicalSkillKey('ServiceNow (ITSM)')).toBe('servicenow_itsm');
    createReview(database);
    const second = createSkillConfirmation(
      {
        skillKey: 'ServiceNow (ITSM)',
        title: 'ServiceNow',
        question: 'Same skill in another opportunity',
        summary: 'Answer before this opportunity continues.',
        opportunityKey: 'globex',
        opportunityCompany: 'Globex',
        opportunityTitle: 'Technical Product Manager',
      },
      database,
    );
    expect(second.created).toBe(true);
    expect(listReviewItems('open', database)).toHaveLength(1);
    expect(listReviewItems('open', database)[0].affectedOpportunities).toHaveLength(2);
  });

  it('keeps a Yes answer at attestation level and creates optional enrichment', () => {
    const database = createDatabase();
    createReview(database);
    expect(
      answerReviewItem('skill:servicenow_itsm', 'CONFIRMED_USE', undefined, false, database),
    ).toEqual({ ok: true, status: 'completed' });

    const open = listReviewItems('open', database);
    expect(open).toHaveLength(1);
    expect(open[0].type).toBe('evidence_enrichment');
    const memory = database
      .prepare('SELECT decision, evidence_level FROM skill_memory WHERE skill_key = ?')
      .get('servicenow_itsm') as { decision: string; evidence_level: number };
    expect(memory).toEqual({ decision: 'CONFIRMED_USE', evidence_level: 1 });
    expect(
      database
        .prepare('SELECT count(*) AS count FROM review_answer_history WHERE review_key = ?')
        .get('skill:servicenow_itsm'),
    ).toEqual({ count: 1 });
  });

  it('rejects promotion without minimum evidence and promotes only explicitly', () => {
    const database = createDatabase();
    createReview(database);
    expect(
      answerReviewItem(
        'skill:servicenow_itsm',
        'CONFIRMED_USE',
        { context: 'Acme', activity: 'configured workflows' },
        true,
        database,
      ),
    ).toEqual({
      ok: false,
      error: 'Verified evidence requires a Yes answer plus context, activity, and timeframe',
    });

    answerReviewItem('skill:servicenow_itsm', 'CONFIRMED_USE', undefined, false, database);
    const answerResult = answerReviewItem(
        'skill:servicenow_itsm:evidence',
        'CONFIRMED_USE',
        {
          context: 'Acme',
          activity: 'configured workflows',
          timeframe: '2024',
        },
        true,
        database,
      );
    expect(answerResult).toMatchObject({ ok: true, status: 'completed' });
    if (!answerResult.ok || !answerResult.promotionId) throw new Error('Promotion proposal was not created');
    const memory = database
      .prepare('SELECT decision, evidence_level FROM skill_memory WHERE skill_key = ?')
      .get('servicenow_itsm') as { decision: string; evidence_level: number };
    expect(memory).toEqual({ decision: 'CONFIRMED_USE', evidence_level: 1 });
    expect(
      verifyEvidencePromotion(
        answerResult.promotionId,
        'Acme configured workflows during 2024.',
        database,
      ),
    ).toEqual({ ok: true, status: 'verified' });
    expect(
      database
        .prepare('SELECT status FROM evidence_promotion_proposals WHERE id = ?')
        .get(answerResult.promotionId),
    ).toEqual({ status: 'VERIFIED' });
    const verifiedMemory = database
      .prepare('SELECT decision, evidence_level FROM skill_memory WHERE skill_key = ?')
      .get('servicenow_itsm') as { decision: string; evidence_level: number };
    expect(verifiedMemory).toEqual({ decision: 'VERIFIED_EVIDENCE', evidence_level: 2 });
    const repeated = answerReviewItem(
      'skill:servicenow_itsm',
      'CONFIRMED_USE',
      {
        context: 'Acme',
        activity: 'configured workflows',
        timeframe: '2024',
      },
      true,
      database,
    );
    expect(repeated).toMatchObject({
      ok: true,
      status: 'completed',
      promotionId: answerResult.promotionId,
    });
    expect(
      database
        .prepare('SELECT decision, evidence_level FROM skill_memory WHERE skill_key = ?')
        .get('servicenow_itsm'),
    ).toEqual({ decision: 'VERIFIED_EVIDENCE', evidence_level: 2 });
  });

  it('records BAD_DATA durably, creates no enrichment, and surfaces the answer', () => {
    // Implements FR-287 (CR-109): a bad-extraction flag teaches Applyr to never
    // re-ask the candidate and stays visible on the completed card.
    const database = createDatabase();
    createReview(database);
    expect(
      answerReviewItem('skill:servicenow_itsm', 'BAD_DATA', undefined, false, database),
    ).toEqual({ ok: true, status: 'completed' });

    expect(listReviewItems('open', database)).toHaveLength(0);
    const memory = database
      .prepare('SELECT decision, evidence_level FROM skill_memory WHERE skill_key = ?')
      .get('servicenow_itsm') as { decision: string; evidence_level: number };
    expect(memory).toEqual({ decision: 'BAD_DATA', evidence_level: 0 });
    const completed = listReviewItems('completed', database);
    expect(completed).toHaveLength(1);
    expect(completed[0].answer).toBe('BAD_DATA');
    expect(
      database
        .prepare('SELECT answer FROM review_answer_history WHERE review_key = ?')
        .get('skill:servicenow_itsm'),
    ).toEqual({ answer: 'BAD_DATA' });
  });

  it('rejects BAD_DATA on hard-gate reviews', () => {
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
    expect(
      answerReviewItem(review.reviewKey, 'BAD_DATA', undefined, false, database),
    ).toEqual({ ok: false, error: 'Invalid hard-gate answer' });
  });

  it('supports correcting a completed answer (change answer)', () => {
    // Implements FR-289 (CR-109): a completed card stays correctable and the
    // durable memory follows the latest answer.
    const database = createDatabase();
    createReview(database);
    answerReviewItem('skill:servicenow_itsm', 'NOT_PRESENT', undefined, false, database);
    answerReviewItem('skill:servicenow_itsm', 'CONFIRMED_USE', undefined, false, database);
    const memory = database
      .prepare('SELECT decision FROM skill_memory WHERE skill_key = ?')
      .get('servicenow_itsm') as { decision: string };
    expect(memory.decision).toBe('CONFIRMED_USE');
    expect(listReviewItems('completed', database)[0].answer).toBe('CONFIRMED_USE');
    expect(
      database
        .prepare('SELECT count(*) AS count FROM review_answer_history WHERE review_key = ?')
        .get('skill:servicenow_itsm'),
    ).toEqual({ count: 2 });
  });

  it('keeps a hard-gate review open for more information', () => {
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
    expect(
      answerReviewItem(
        review.reviewKey,
        'NEEDS_MORE_INFO',
        undefined,
        false,
        database,
      ),
    ).toEqual({ ok: true, status: 'open' });
    expect(listReviewItems('open', database)[0]).toMatchObject({
      id: review.reviewKey,
      type: 'hard_gate_review',
      requirement: 'Requires an active professional license',
    });
  });

  it('requires an explicit hard-gate confirmation before disqualification', () => {
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
    expect(answerReviewItem(review.reviewKey, 'CONFIRM_HARD', undefined, false, database)).toEqual({
      ok: true,
      status: 'completed',
    });
    expect(listReviewItems('open', database)).toHaveLength(0);
    expect(
      database
        .prepare('SELECT answer FROM review_answer_history WHERE review_key = ?')
        .get(review.reviewKey),
    ).toEqual({ answer: 'CONFIRM_HARD' });
  });
});
