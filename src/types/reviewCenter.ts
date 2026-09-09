export type ReviewItemType = 'skill_presence' | 'evidence_enrichment' | 'hard_gate_review';

export type ReviewItemStatus = 'open' | 'completed';

export type EvidencePromotionStatus = 'PENDING_SOURCE_UPDATE' | 'VERIFIED' | 'REJECTED';

export type SkillReviewAnswer = 'CONFIRMED_USE' | 'NOT_PRESENT' | 'UNSURE_NO_REASK' | 'BAD_DATA';

export type HardGateReviewAnswer = 'KEEP_ELIGIBLE' | 'CONFIRM_HARD' | 'NEEDS_MORE_INFO';

export type ReviewAnswer = SkillReviewAnswer | HardGateReviewAnswer;

export interface AffectedOpportunity {
  jobId: string;
  company: string;
  title: string;
  status?: string;
}

export interface EvidenceDetails {
  context: string;
  activity: string;
  timeframe: string;
  scope: string;
  outcome: string;
}

export interface ReviewItem {
  id: string;
  type: ReviewItemType;
  status: ReviewItemStatus;
  title: string;
  question: string;
  summary: string;
  skillKey?: string;
  requirement?: string;
  evidenceExcerpt?: string;
  evidenceStatus?: 'not_started' | 'incomplete' | 'ready';
  promotionId?: string;
  promotionStatus?: EvidencePromotionStatus;
  affectedOpportunities: AffectedOpportunity[];
  /** The recorded answer on a completed item; drives correction UX (FR-289). */
  answer?: ReviewAnswer;
  createdAt?: string;
}

export interface ReviewAnswerPayload {
  answer: ReviewAnswer;
  details?: EvidenceDetails;
  promoteToVerifiedEvidence?: boolean;
}
