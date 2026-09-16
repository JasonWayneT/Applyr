export type WorkflowCommand = 'start' | 'resume' | 'status' | 'finalize';
export type WorkflowScope = 'pending-review' | 'submissions';
export type WorkflowStageName = 'stage0' | 'stage1' | 'stage2';

export interface WorkflowStageView {
  status: string | null;
  integrity: string | null;
  subphases?: Record<string, WorkflowStageView>;
}

export interface WorkflowPauseView {
  kind?: 'cost_authorization' | 'review_center';
  attemptedOperation?: 'evidence_classification';
  authorizationMode?: 'unknown' | 'free_only' | 'paid_with_budget' | 'offline' | 'manual_paste';
  modelCallOccurred?: boolean;
  costKnown?: boolean;
  costConfidence?: 'unknown' | 'zero' | 'estimated' | 'confirmed';
  nextPaths: Array<'import_cascade_json' | 'certify_zero_charge' | 'paid_allowlist_budget'>;
  pendingCount?: number;
}

export interface WorkflowReceiptView extends WorkflowStageView {
  stage: WorkflowStageName;
  pause?: WorkflowPauseView;
}

export interface WorkflowStatusView {
  present: boolean;
  status: string | null;
  mode: 'production' | 'practice' | null;
  activeStage: WorkflowStageName | null;
  updatedAt: string | null;
  stages: Partial<Record<WorkflowStageName, WorkflowStageView>>;
  receipts: WorkflowReceiptView[];
}

export interface WorkflowCommandResultView {
  command: WorkflowCommand;
  scope: WorkflowScope;
  slug: string;
  workflow: WorkflowStatusView;
}
