import { createHash, randomUUID } from 'crypto';
import type Database from 'better-sqlite3';
import { db } from '../db.js';

export type ReviewQuestionType = 'skill_presence' | 'evidence_enrichment' | 'hard_gate_review';
export type ReviewStatus = 'open' | 'completed';
export type EvidencePromotionStatus = 'PENDING_SOURCE_UPDATE' | 'VERIFIED' | 'REJECTED';
export type ReviewAnswer =
  | 'CONFIRMED_USE'
  | 'NOT_PRESENT'
  | 'UNSURE_NO_REASK'
  | 'BAD_DATA'
  | 'KEEP_ELIGIBLE'
  | 'CONFIRM_HARD'
  | 'NEEDS_MORE_INFO';

export interface ReviewOpportunity {
  jobId: string;
  company: string;
  title: string;
  status?: string;
}

export interface ReviewItem {
  id: string;
  type: ReviewQuestionType;
  status: ReviewStatus;
  title: string;
  question: string;
  summary: string;
  skillKey?: string;
  requirement?: string;
  evidenceExcerpt?: string;
  evidenceStatus?: 'not_started' | 'incomplete' | 'ready';
  promotionId?: string;
  promotionStatus?: EvidencePromotionStatus;
  affectedOpportunities: ReviewOpportunity[];
  /** Implements FR-289: surface the recorded answer so completed cards stay correctable. */
  answer?: ReviewAnswer;
  createdAt: string;
}

export interface EvidenceDetails {
  context?: unknown;
  activity?: unknown;
  timeframe?: unknown;
  scope?: unknown;
  outcome?: unknown;
}

type ReviewRow = {
  id: string;
  review_key: string;
  question_type: ReviewQuestionType;
  skill_key: string | null;
  status: ReviewStatus;
  title: string;
  question: string;
  summary: string;
  requirement: string | null;
  evidence_excerpt: string | null;
  opportunity_key: string;
  opportunity_company: string;
  opportunity_title: string;
  opportunity_status: string | null;
  answer: ReviewAnswer | null;
  answer_details_json: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

type SkillMemoryRow = {
  skill_key: string;
  display_name: string;
  decision: string;
  evidence_level: number;
  details_json: string | null;
};

type EvidencePromotionRow = {
  id: string;
  skill_key: string;
  status: EvidencePromotionStatus;
};

const SKILL_ANSWERS = new Set<ReviewAnswer>([
  'CONFIRMED_USE',
  'NOT_PRESENT',
  'UNSURE_NO_REASK',
  'BAD_DATA',
]);

const HARD_GATE_ANSWERS = new Set<ReviewAnswer>([
  'KEEP_ELIGIBLE',
  'CONFIRM_HARD',
  'NEEDS_MORE_INFO',
]);

function clean(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

// Implements FR-283: keep Python Stage 0, the API, and the harness on one key format.
export function canonicalSkillKey(value: string): string {
  return clean(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function detailsObject(input: unknown): EvidenceDetails {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return {};
  return input as EvidenceDetails;
}

function detailText(details: EvidenceDetails, key: keyof EvidenceDetails): string {
  return clean(details[key]);
}

function hasMinimumEvidence(details: EvidenceDetails): boolean {
  return Boolean(
    detailText(details, 'context') &&
      detailText(details, 'activity') &&
      detailText(details, 'timeframe'),
  );
}

function parseDetails(value: string | null): EvidenceDetails {
  if (!value) return {};
  try {
    return detailsObject(JSON.parse(value));
  } catch {
    return {};
  }
}

function mapGroup(
  rows: ReviewRow[],
  memory: SkillMemoryRow | undefined,
  promotion: EvidencePromotionRow | undefined,
): ReviewItem {
  const first = rows[0];
  const status: ReviewStatus = rows.some(row => row.status === 'open') ? 'open' : 'completed';
  const details = memory ? parseDetails(memory.details_json) : {};
  const hasDetails = hasMinimumEvidence(details);
  const evidenceStatus =
    memory?.decision === 'VERIFIED_EVIDENCE' || promotion?.status === 'VERIFIED'
      ? 'ready'
      : hasDetails
        ? 'incomplete'
        : memory?.decision === 'CONFIRMED_USE'
          ? 'incomplete'
          : 'not_started';

  return {
    id: first.review_key,
    type: first.question_type,
    status,
    title: first.title,
    question: first.question,
    summary: first.summary,
    skillKey: first.skill_key || undefined,
    requirement: first.requirement || undefined,
    evidenceExcerpt: first.evidence_excerpt || undefined,
    evidenceStatus,
    promotionId: promotion?.id,
    promotionStatus: promotion?.status,
    answer: rows.map(row => row.answer).find((value): value is ReviewAnswer => Boolean(value)),
    affectedOpportunities: rows.map(row => ({
      jobId: row.opportunity_key,
      company: row.opportunity_company,
      title: row.opportunity_title,
      status: row.opportunity_status || undefined,
    })),
    createdAt: first.created_at,
  };
}

function groupRows(
  rows: ReviewRow[],
  memories: SkillMemoryRow[],
  promotionBySkill: Map<string, EvidencePromotionRow>,
): ReviewItem[] {
  const memoryBySkill = new Map(memories.map(memory => [memory.skill_key, memory]));
  const groups = new Map<string, ReviewRow[]>();
  for (const row of rows) {
    const existing = groups.get(row.review_key) ?? [];
    existing.push(row);
    groups.set(row.review_key, existing);
  }
  return [...groups.values()]
    .map(group => mapGroup(
      group,
      group[0].skill_key ? memoryBySkill.get(group[0].skill_key) : undefined,
      group[0].skill_key ? promotionBySkill.get(group[0].skill_key) : undefined,
    ))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function listReviewItems(
  status: ReviewStatus | 'all' = 'all',
  database: Database.Database = db,
): ReviewItem[] {
  const clauses: string[] = [];
  const params: unknown[] = [];
  if (status !== 'all') {
    clauses.push('status = ?');
    params.push(status);
  }
  const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
  const rows = database.prepare(`
    SELECT id, review_key, question_type, skill_key, status, title, question,
           summary, requirement, evidence_excerpt, opportunity_key,
           opportunity_company, opportunity_title, opportunity_status, answer,
           answer_details_json, created_at, updated_at, resolved_at
    FROM pending_skill_confirmations
    ${where}
    ORDER BY created_at DESC
  `).all(...params) as ReviewRow[];
  const memories = database.prepare(`
    SELECT skill_key, display_name, decision, evidence_level, details_json
    FROM skill_memory
  `).all() as SkillMemoryRow[];
  const promotions = database.prepare(`
    SELECT id, skill_key, status
    FROM evidence_promotion_proposals
    WHERE status IN ('PENDING_SOURCE_UPDATE', 'VERIFIED')
    ORDER BY updated_at DESC
  `).all() as EvidencePromotionRow[];
  const promotionBySkill = new Map<string, EvidencePromotionRow>();
  for (const promotion of promotions) {
    if (!promotionBySkill.has(promotion.skill_key)) promotionBySkill.set(promotion.skill_key, promotion);
  }
  return groupRows(rows, memories, promotionBySkill);
}

export function createSkillConfirmation(
  input: {
    skillKey: string;
    title: string;
    question: string;
    summary: string;
    requirement?: string;
    evidenceExcerpt?: string;
    opportunityKey: string;
    opportunityCompany: string;
    opportunityTitle: string;
    opportunityStatus?: string;
  },
  database: Database.Database = db,
): { created: boolean; reviewKey: string } {
  const skillKey = canonicalSkillKey(input.skillKey);
  if (!skillKey) throw new Error('skillKey is required');
  const opportunityKey = clean(input.opportunityKey);
  if (!opportunityKey) throw new Error('opportunityKey is required');
  const reviewKey = `skill:${skillKey}`;
  const existing = database.prepare(`
    SELECT id
    FROM pending_skill_confirmations
    WHERE review_key = ? AND opportunity_key = ? AND question_type = 'skill_presence'
      AND status = 'open'
  `).get(reviewKey, opportunityKey) as { id: string } | undefined;
  if (existing) return { created: false, reviewKey };

  const now = new Date().toISOString();
  database.prepare(`
    INSERT INTO pending_skill_confirmations (
      id, review_key, question_type, skill_key, status, title, question, summary,
      requirement, evidence_excerpt, opportunity_key, opportunity_company,
      opportunity_title, opportunity_status, created_at, updated_at
    ) VALUES (?, ?, 'skill_presence', ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    randomUUID(),
    reviewKey,
    skillKey,
    clean(input.title) || skillKey,
    clean(input.question) || `Have you used ${skillKey} in your work?`,
    clean(input.summary) || 'Applyr needs your input before this opportunity can continue.',
    clean(input.requirement) || null,
    clean(input.evidenceExcerpt) || null,
    opportunityKey,
    clean(input.opportunityCompany) || 'Unknown company',
    clean(input.opportunityTitle) || 'Untitled opportunity',
    clean(input.opportunityStatus) || null,
    now,
    now,
  );
  return { created: true, reviewKey };
}

export function createHardGateReview(
  input: {
    itemKey: string;
    requirement: string;
    evidenceExcerpt?: string;
    opportunityKey: string;
    opportunityCompany: string;
    opportunityTitle: string;
  },
  database: Database.Database = db,
): { created: boolean; reviewKey: string } {
  const opportunityKey = clean(input.opportunityKey);
  const itemKey = clean(input.itemKey);
  if (!itemKey) throw new Error('itemKey is required');
  if (!opportunityKey) throw new Error('opportunityKey is required');
  const reviewKey = `hard:${opportunityKey}:${itemKey}`;
  const existing = database.prepare(`
    SELECT id
    FROM pending_skill_confirmations
    WHERE review_key = ? AND status = 'open' AND question_type = 'hard_gate_review'
  `).get(reviewKey) as { id: string } | undefined;
  if (existing) return { created: false, reviewKey };

  const now = new Date().toISOString();
  database.prepare(`
    INSERT INTO pending_skill_confirmations (
      id, review_key, question_type, status, title, question, summary,
      requirement, evidence_excerpt, opportunity_key, opportunity_company,
      opportunity_title, created_at, updated_at
    ) VALUES (?, ?, 'hard_gate_review', 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    randomUUID(),
    reviewKey,
    'Review a possible hard requirement',
    'Should this requirement disqualify the opportunity?',
    'Applyr will not disqualify this opportunity without your explicit decision.',
    clean(input.requirement) || null,
    clean(input.evidenceExcerpt) || null,
    opportunityKey,
    clean(input.opportunityCompany) || 'Unknown company',
    clean(input.opportunityTitle) || 'Untitled opportunity',
    now,
    now,
  );
  return { created: true, reviewKey };
}

function createEvidenceEnrichment(
  row: ReviewRow,
  database: Database.Database,
): void {
  if (!row.skill_key) return;
  const reviewKey = `skill:${row.skill_key}:evidence`;
  const existing = database.prepare(`
    SELECT id FROM pending_skill_confirmations
    WHERE review_key = ? AND opportunity_key = ? AND status = 'open'
  `).get(reviewKey, row.opportunity_key) as { id: string } | undefined;
  if (existing) return;
  const now = new Date().toISOString();
  database.prepare(`
    INSERT INTO pending_skill_confirmations (
      id, review_key, question_type, skill_key, status, title, question, summary,
      requirement, evidence_excerpt, opportunity_key, opportunity_company,
      opportunity_title, opportunity_status, created_at, updated_at
    ) VALUES (?, ?, 'evidence_enrichment', ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    randomUUID(),
    reviewKey,
    row.skill_key,
    row.title,
    `Add details about your ${row.title} experience.`,
    'Optional: add where, what, and when so stronger job requirements can be evaluated accurately.',
    row.requirement,
    row.evidence_excerpt,
    row.opportunity_key,
    row.opportunity_company,
    row.opportunity_title,
    row.opportunity_status,
    now,
    now,
  );
}

function upsertSkillMemory(
  skillKey: string,
  displayName: string,
  decision: 'CONFIRMED_USE' | 'NOT_PRESENT' | 'UNSURE_NO_REASK' | 'VERIFIED_EVIDENCE' | 'BAD_DATA',
  details: EvidenceDetails,
  database: Database.Database,
): void {
  const now = new Date().toISOString();
  const evidenceLevel = decision === 'VERIFIED_EVIDENCE' ? 2 : decision === 'CONFIRMED_USE' ? 1 : 0;
  database.prepare(`
    INSERT INTO skill_memory (
      skill_key, display_name, decision, evidence_level, details_json, source, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, 'user_confirmation', ?, ?)
    ON CONFLICT(skill_key) DO UPDATE SET
      display_name = excluded.display_name,
      decision = excluded.decision,
      evidence_level = excluded.evidence_level,
      details_json = excluded.details_json,
      updated_at = excluded.updated_at
  `).run(
    skillKey,
    displayName,
    decision,
    evidenceLevel,
    Object.keys(details).length ? JSON.stringify(details) : null,
    now,
    now,
  );
}

export function answerReviewItem(
  reviewKey: string,
  answer: ReviewAnswer,
  rawDetails: unknown,
  promoteToVerifiedEvidence: boolean,
  database: Database.Database = db,
): { ok: true; status: ReviewStatus; promotionId?: string } | { ok: false; error: string; notFound?: boolean } {
  const rows = database.prepare(`
    SELECT id, review_key, question_type, skill_key, status, title, question, summary,
           requirement, evidence_excerpt, opportunity_key, opportunity_company,
           opportunity_title, opportunity_status, answer, answer_details_json,
           created_at, updated_at, resolved_at
    FROM pending_skill_confirmations
    WHERE review_key = ?
  `).all(reviewKey) as ReviewRow[];
  if (!rows.length) return { ok: false, error: 'Review item not found', notFound: true };

  const isSkill = rows[0].question_type !== 'hard_gate_review';
  const validAnswer = isSkill ? SKILL_ANSWERS.has(answer) : HARD_GATE_ANSWERS.has(answer);
  if (!validAnswer) {
    return { ok: false, error: isSkill ? 'Invalid skill answer' : 'Invalid hard-gate answer' };
  }

  const details = detailsObject(rawDetails);
  if (promoteToVerifiedEvidence && (!isSkill || answer !== 'CONFIRMED_USE' || !hasMinimumEvidence(details))) {
    return { ok: false, error: 'Verified evidence requires a Yes answer plus context, activity, and timeframe' };
  }

  const now = new Date().toISOString();
  const serializedDetails = Object.keys(details).length ? JSON.stringify(details) : null;
  let promotionId: string | undefined;
  const completed = answer !== 'NEEDS_MORE_INFO';
  const nextStatus: ReviewStatus = completed ? 'completed' : 'open';
  const resolvedAt = completed ? now : null;
  // Implements FR-284 / DATA-003: an attestation can create only a pending proposal.
  let existingPromotion: { id: string; status: EvidencePromotionStatus } | undefined;
  if (promoteToVerifiedEvidence && isSkill && rows[0].skill_key) {
    existingPromotion = database.prepare(`
      SELECT id, status
      FROM evidence_promotion_proposals
      WHERE skill_key = ? AND status IN ('PENDING_SOURCE_UPDATE', 'VERIFIED')
      ORDER BY updated_at DESC
      LIMIT 1
    `).get(rows[0].skill_key) as { id: string; status: EvidencePromotionStatus } | undefined;
  }
  const update = database.prepare(`
    UPDATE pending_skill_confirmations
    SET status = ?, answer = ?, answer_details_json = ?, updated_at = ?, resolved_at = ?
    WHERE review_key = ?
  `);
  update.run(nextStatus, answer, serializedDetails, now, resolvedAt, reviewKey);
  database.prepare(`
    INSERT INTO review_answer_history (
      id, review_key, question_type, answer, details_json, answered_at
    ) VALUES (?, ?, ?, ?, ?, ?)
  `).run(randomUUID(), reviewKey, rows[0].question_type, answer, serializedDetails, now);

  if (isSkill && rows[0].skill_key) {
    const skillKey = rows[0].skill_key;
    // Implements FR-287: BAD_DATA records that the extracted candidate was not a
    // real skill/tool so the same candidate is never queued again.
    const decision = existingPromotion?.status === 'VERIFIED'
      ? 'VERIFIED_EVIDENCE'
      : answer as 'CONFIRMED_USE' | 'NOT_PRESENT' | 'UNSURE_NO_REASK' | 'BAD_DATA';
    upsertSkillMemory(skillKey, rows[0].title, decision, details, database);
    if (promoteToVerifiedEvidence) {
      promotionId = existingPromotion?.id ?? randomUUID();
      if (!existingPromotion) {
        database.prepare(`
          INSERT INTO evidence_promotion_proposals (
            id, skill_key, review_key, details_json, created_at, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?)
        `).run(
          promotionId,
          skillKey,
          reviewKey,
          serializedDetails ?? '{}',
          now,
          now,
        );
      }
    }
    if (answer === 'CONFIRMED_USE' && !promoteToVerifiedEvidence) {
      for (const row of rows) createEvidenceEnrichment(row, database);
    }
    if (answer === 'NOT_PRESENT' || answer === 'UNSURE_NO_REASK' || answer === 'BAD_DATA') {
      database.prepare(`
        UPDATE pending_skill_confirmations
        SET status = 'completed', answer = ?, updated_at = ?, resolved_at = ?
        WHERE skill_key = ? AND question_type = 'evidence_enrichment' AND status = 'open'
      `).run(answer, now, now, skillKey);
    }
  }

  return { ok: true, status: nextStatus, promotionId };
}

export function verifyEvidencePromotion(
  promotionId: string,
  sourceText: string,
  database: Database.Database = db,
): { ok: true; status: 'verified' } | { ok: false; error: string; notFound?: boolean } {
  // Implements FR-284 / DATA-003: promote only after local source verification.
  const proposal = database.prepare(`
    SELECT id, skill_key, details_json, status
    FROM evidence_promotion_proposals
    WHERE id = ?
  `).get(promotionId) as {
    id: string;
    skill_key: string;
    details_json: string;
    status: EvidencePromotionStatus;
  } | undefined;
  if (!proposal) return { ok: false, error: 'Evidence promotion proposal not found', notFound: true };
  if (proposal.status === 'VERIFIED') return { ok: true, status: 'verified' };
  if (proposal.status !== 'PENDING_SOURCE_UPDATE') {
    return { ok: false, error: 'Evidence promotion proposal is not pending' };
  }
  let details: EvidenceDetails;
  try {
    details = detailsObject(JSON.parse(proposal.details_json));
  } catch {
    return { ok: false, error: 'Evidence promotion details are invalid' };
  }
  if (!hasMinimumEvidence(details)) {
    return { ok: false, error: 'Evidence promotion requires context, activity, and timeframe' };
  }
  const required = ['context', 'activity', 'timeframe'] as const;
  if (!required.every(field => detailText(details, field).toLocaleLowerCase() &&
      sourceText.toLocaleLowerCase().includes(detailText(details, field).toLocaleLowerCase()))) {
    return { ok: false, error: 'The reviewed evidence is not present in workExperience.md' };
  }
  const now = new Date().toISOString();
  const sourceDigest = createHash('sha256').update(sourceText, 'utf8').digest('hex');
  const transaction = database.transaction(() => {
    database.prepare(`
      UPDATE evidence_promotion_proposals
      SET status = 'VERIFIED', source_digest = ?, updated_at = ?, verified_at = ?
      WHERE id = ?
    `).run(sourceDigest, now, now, promotionId);
    database.prepare(`
      UPDATE skill_memory
      SET decision = 'VERIFIED_EVIDENCE', evidence_level = 2,
          details_json = ?, updated_at = ?
      WHERE skill_key = ?
    `).run(proposal.details_json, now, proposal.skill_key);
  });
  transaction();
  return { ok: true, status: 'verified' };
}
