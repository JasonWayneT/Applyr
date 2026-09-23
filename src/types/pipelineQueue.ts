export const STUCK_STALE_MINUTES = 120;

export interface PipelineQueueCounts {
  queued: number;
  leased: number;
  in_progress: number;
  paused: number;
  ready_to_finalize: number;
  done: number;
  quarantined: number;
}

export interface PipelineLease {
  slug: string;
  company: string;
  lockedBy: string;
  leaseExpiresAt: string | null;
  leaseAgeMinutes: number;
}

export interface PipelineWaitingItem {
  slug: string;
  company: string;
  reason: string;
}

export interface PipelineStuckItem {
  slug: string;
  company: string;
  status: string;
  lockedBy: string | null;
  leaseExpiresAt: string | null;
  reason: 'expired_lease' | 'stale_receipt';
  ageMinutes: number;
}

export interface PipelineQuarantineRow {
  id: number;
  sourceFile: string;
  lineNumber: number | null;
  errorCode: string;
  quarantineReason: string;
}

export interface PipelineDecisionItem {
  slug: string;
  company: string;
  state: 'Continuing' | 'Skipped' | 'Running' | 'Failed';
  reason: string;
  canRetry: boolean;
}

export interface PipelineQueueStats {
  counts: PipelineQueueCounts;
  leases: PipelineLease[];
  waiting: PipelineWaitingItem[];
  decisions: PipelineDecisionItem[];
  stuck: PipelineStuckItem[];
}

export interface PipelineUploadResult {
  queued: number;
  duplicate: number;
  quarantined: number;
}
