import { apiFetch } from './api';
import type {
  EvidencePromotionStatus,
  ReviewItem,
  ReviewItemStatus,
  ReviewItemType,
  ReviewItemType as ItemType,
} from '../types/reviewCenter';

export interface ReviewQueueResponse {
  available: boolean;
  items: ReviewItem[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function stringValue(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function normalizeType(value: unknown): ReviewItemType {
  if (value === 'hard_gate_review' || value === 'evidence_enrichment') return value;
  return 'skill_presence';
}

function normalizeStatus(value: unknown): ReviewItemStatus {
  return value === 'completed' ? 'completed' : 'open';
}

function normalizePromotionStatus(value: unknown): EvidencePromotionStatus | undefined {
  return value === 'PENDING_SOURCE_UPDATE' || value === 'VERIFIED' || value === 'REJECTED'
    ? value
    : undefined;
}

function normalizeAffectedOpportunities(value: unknown): ReviewItem['affectedOpportunities'] {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((opportunity, index) => ({
    jobId: stringValue(opportunity.jobId ?? opportunity.job_id, `unknown-${index}`),
    company: stringValue(opportunity.company, 'Unknown company'),
    title: stringValue(opportunity.title, 'Untitled opportunity'),
    status: stringValue(opportunity.status) || undefined,
  }));
}

const REVIEW_ANSWERS = new Set([
  'CONFIRMED_USE',
  'NOT_PRESENT',
  'UNSURE_NO_REASK',
  'BAD_DATA',
  'KEEP_ELIGIBLE',
  'CONFIRM_HARD',
  'NEEDS_MORE_INFO',
]);

function normalizeAnswer(value: unknown): ReviewItem['answer'] {
  return typeof value === 'string' && REVIEW_ANSWERS.has(value)
    ? (value as ReviewItem['answer'])
    : undefined;
}

function normalizeItem(value: unknown, index: number): ReviewItem | null {
  if (!isRecord(value)) return null;
  const id = stringValue(value.id, `review-${index}`);
  const title = stringValue(value.title || value.skillKey || value.skill_key);
  if (!title) return null;

  return {
    id,
    type: normalizeType(value.type || value.question_type),
    status: normalizeStatus(value.status),
    title,
    question: stringValue(value.question, `Review the evidence for ${title}.`),
    summary: stringValue(value.summary, 'Applyr needs your input before this opportunity can continue.'),
    skillKey: stringValue(value.skillKey || value.skill_key) || undefined,
    requirement: stringValue(value.requirement) || undefined,
    evidenceExcerpt: stringValue(value.evidenceExcerpt || value.evidence_excerpt) || undefined,
    decisionBasis: stringValue(value.decisionBasis || value.decision_basis) || undefined,
    uncertainty: stringValue(value.uncertainty) || undefined,
    evidenceStatus:
      value.evidenceStatus === 'ready' || value.evidenceStatus === 'incomplete'
        ? value.evidenceStatus
        : 'not_started',
    promotionId: stringValue(value.promotionId || value.promotion_id) || undefined,
    promotionStatus: normalizePromotionStatus(value.promotionStatus || value.promotion_status),
    affectedOpportunities: normalizeAffectedOpportunities(
      value.affectedOpportunities || value.affected_opportunities,
    ),
    answer: normalizeAnswer(value.answer),
    createdAt: stringValue(value.createdAt || value.created_at) || undefined,
  };
}

export function normalizeReviewItems(payload: unknown): ReviewItem[] {
  const rows = Array.isArray(payload)
    ? payload
    : isRecord(payload) && Array.isArray(payload.items)
      ? payload.items
      : [];
  return rows.map(normalizeItem).filter((item): item is ReviewItem => item !== null);
}

export function hasMinimumEvidence(details: Partial<{
  context: string;
  activity: string;
  timeframe: string;
}>): boolean {
  return Boolean(details.context?.trim() && details.activity?.trim() && details.timeframe?.trim());
}

export async function fetchReviewQueue(): Promise<ReviewQueueResponse> {
  // Implements FR-285: the UI reads the shared durable confirmation service boundary.
  const response = await apiFetch('/api/review-center/items');
  if (response.status === 404) return { available: false, items: [] };
  if (!response.ok) {
    throw new Error(`Review Center could not load (${response.status}).`);
  }
  return { available: true, items: normalizeReviewItems(await response.json()) };
}

export async function answerReviewItem(
  itemId: string,
  payload: import('../types/reviewCenter').ReviewAnswerPayload,
): Promise<void> {
  const response = await apiFetch(`/api/review-center/items/${encodeURIComponent(itemId)}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Review answer could not be saved (${response.status}).`);
  }
}

export async function verifyEvidencePromotion(promotionId: string): Promise<void> {
  const response = await apiFetch(`/api/review-center/promotions/${encodeURIComponent(promotionId)}/verify`, {
    method: 'POST',
  });
  if (!response.ok) {
    let message = `Evidence promotion could not be verified (${response.status}).`;
    try {
      const body = await response.json() as { error?: string };
      if (body.error) message = body.error;
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }
    throw new Error(message);
  }
}

export function isSkillReviewType(type: ItemType): boolean {
  return type === 'skill_presence' || type === 'evidence_enrichment';
}

// Implements FR-285: Stage 0 uses the company folder slug as its durable opportunity key.
export function companyOpportunityKey(company: string): string {
  return company
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
}
