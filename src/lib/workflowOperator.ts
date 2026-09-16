import { apiFetch } from './api';
import type {
  WorkflowCommand,
  WorkflowCommandResultView,
  WorkflowPauseView,
  WorkflowReceiptView,
  WorkflowScope,
  WorkflowStageName,
  WorkflowStageView,
} from '../types/workflowOperator';

const COMMANDS = new Set<WorkflowCommand>(['start', 'resume', 'status', 'finalize']);
const SCOPES = new Set<WorkflowScope>(['pending-review', 'submissions']);
const STAGES = new Set<WorkflowStageName>(['stage0', 'stage1', 'stage2']);
const SUBPHASES = new Set(['truth', 'ats', 'hm', 'mech', 'policy']);
const MODES = new Set<NonNullable<WorkflowCommandResultView['workflow']['mode']>>([
  'production',
  'practice',
]);
const PAUSE_KINDS = new Set<NonNullable<WorkflowPauseView['kind']>>([
  'cost_authorization',
  'review_center',
]);
const ATTEMPTED_OPERATIONS = new Set<NonNullable<WorkflowPauseView['attemptedOperation']>>([
  'evidence_classification',
]);
const AUTHORIZATION_MODES = new Set<NonNullable<WorkflowPauseView['authorizationMode']>>([
  'unknown',
  'free_only',
  'paid_with_budget',
  'offline',
  'manual_paste',
]);
const COST_CONFIDENCE = new Set<NonNullable<WorkflowPauseView['costConfidence']>>([
  'unknown',
  'zero',
  'estimated',
  'confirmed',
]);
const NEXT_PATHS = new Set<WorkflowPauseView['nextPaths'][number]>([
  'import_cascade_json',
  'certify_zero_charge',
  'paid_allowlist_budget',
]);
const TERMINAL_STATUSES = new Set([
  'SKIPPED',
  'COMPLETE',
  'COMPLETE_WITH_OVERRIDE',
  'PRACTICE_COMPLETE',
]);

// Implements FR-316 / AC-413: the cost pause must not imply that Stage 0 ran
// or that an advertised free tier is a zero-charge authorization.
export const COST_AUTHORIZATION_GUIDANCE =
  'No model API call occurred, so no API cost was incurred. Stage 0 is incomplete. '
  + 'You must import cascade JSON, certify a zero-charge provider, or authorize paid use before you resume. '
  + 'Do not paste authoring_prompt.md while Stage 0 is incomplete.';

export const REVIEW_CENTER_PAUSE_GUIDANCE =
  'This folder is waiting on Review Center items. Resolve them in the queue below, then Resume.';

export interface WorkflowCommandAvailability {
  canStatus: boolean;
  canStart: boolean;
  canResume: boolean;
  canFinalize: boolean;
  primaryCommand: WorkflowCommand;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function allowedString<T extends string>(value: unknown, allowed: ReadonlySet<T>): T | undefined {
  return typeof value === 'string' && allowed.has(value as T) ? value as T : undefined;
}

function nullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

function stageView(value: unknown): WorkflowStageView {
  const row = isRecord(value) ? value : {};
  const subphases: Record<string, WorkflowStageView> = {};
  if (isRecord(row.subphases)) {
    for (const [name, subphase] of Object.entries(row.subphases)) {
      if (SUBPHASES.has(name)) subphases[name] = stageView(subphase);
    }
  }
  return {
    status: nullableString(row.status),
    integrity: nullableString(row.integrity),
    ...(Object.keys(subphases).length > 0 ? { subphases } : {}),
  };
}

function pauseView(value: unknown): WorkflowPauseView | undefined {
  if (!isRecord(value)) return undefined;
  const kind = allowedString(value.kind, PAUSE_KINDS);
  if (!kind) return undefined;
  const attemptedOperation = allowedString(value.attemptedOperation, ATTEMPTED_OPERATIONS);
  const authorizationMode = allowedString(value.authorizationMode, AUTHORIZATION_MODES);
  const costConfidence = allowedString(value.costConfidence, COST_CONFIDENCE);
  const nextPaths = Array.isArray(value.nextPaths)
    ? value.nextPaths
      .map(path => allowedString(path, NEXT_PATHS))
      .filter((path): path is WorkflowPauseView['nextPaths'][number] => path !== undefined)
    : [];
  return {
    kind,
    ...(attemptedOperation ? { attemptedOperation } : {}),
    ...(authorizationMode ? { authorizationMode } : {}),
    ...(typeof value.modelCallOccurred === 'boolean'
      ? { modelCallOccurred: value.modelCallOccurred }
      : {}),
    ...(typeof value.costKnown === 'boolean' ? { costKnown: value.costKnown } : {}),
    ...(costConfidence ? { costConfidence } : {}),
    nextPaths,
    ...(typeof value.pendingCount === 'number' && Number.isInteger(value.pendingCount)
      ? { pendingCount: value.pendingCount }
      : {}),
  };
}

function receiptView(value: unknown): WorkflowReceiptView | null {
  if (!isRecord(value)) return null;
  const stage = allowedString(value.stage, STAGES);
  if (!stage) return null;
  const pause = pauseView(value.pause);
  return {
    stage,
    ...stageView(value),
    ...(pause ? { pause } : {}),
  };
}

/**
 * Normalize the operator response into the small browser-facing contract.
 * Implements FR-316 / AC-413.
 */
export function normalizeWorkflowResult(payload: unknown): WorkflowCommandResultView {
  const root = isRecord(payload) ? payload : {};
  const rawWorkflow = isRecord(root.workflow) ? root.workflow : {};
  const rawStages = isRecord(rawWorkflow.stages) ? rawWorkflow.stages : {};
  const stages: WorkflowCommandResultView['workflow']['stages'] = {};
  for (const stage of STAGES) {
    if (stage in rawStages) stages[stage] = stageView(rawStages[stage]);
  }
  const receipts = Array.isArray(rawWorkflow.receipts)
    ? rawWorkflow.receipts
      .map(receiptView)
      .filter((receipt): receipt is WorkflowReceiptView => receipt !== null)
    : [];

  return {
    command: allowedString(root.command, COMMANDS) ?? 'status',
    scope: allowedString(root.scope, SCOPES) ?? 'submissions',
    slug: typeof root.slug === 'string' ? root.slug : '',
    workflow: {
      present: rawWorkflow.present === true,
      status: nullableString(rawWorkflow.status),
      mode: allowedString(rawWorkflow.mode, MODES) ?? null,
      activeStage: allowedString(rawWorkflow.activeStage, STAGES) ?? null,
      updatedAt: nullableString(rawWorkflow.updatedAt),
      stages,
      receipts,
    },
  };
}

/**
 * Call one canonical backend workflow command and normalize its response.
 * Implements FR-316 / AC-413.
 */
export async function runWorkflowCommand(
  scope: WorkflowScope,
  slug: string,
  command: WorkflowCommand,
): Promise<WorkflowCommandResultView> {
  const response = await apiFetch(
    `/api/run-submission/${scope}/${encodeURIComponent(slug.trim())}/${command}`,
    { method: 'POST' },
  );
  const payload: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = isRecord(payload) && typeof payload.error === 'string'
      ? payload.error
      : `Workflow command failed (${response.status}).`;
    throw new Error(message);
  }
  const normalized = normalizeWorkflowResult(payload);
  return {
    ...normalized,
    command,
    scope,
    slug: normalized.slug || slug.trim(),
  };
}

export function isCostAuthorizationPause(result: WorkflowCommandResultView | null): boolean {
  return result?.workflow.receipts.some(
    receipt => receipt.stage === 'stage0' && receipt.pause?.kind === 'cost_authorization',
  ) ?? false;
}

export function isReviewCenterPause(result: WorkflowCommandResultView | null): boolean {
  return result?.workflow.receipts.some(
    receipt => receipt.pause?.kind === 'review_center',
  ) ?? false;
}

/**
 * Decide which explicit operator commands are available for the loaded folder.
 * Implements FR-316 / AC-413.
 */
export function workflowCommandAvailability(input: {
  slugValid: boolean;
  busy: boolean;
  scope: WorkflowScope;
  slug: string;
  result: WorkflowCommandResultView | null;
}): WorkflowCommandAvailability {
  const workflow = input.result?.workflow;
  const terminal = TERMINAL_STATUSES.has(workflow?.status ?? '');
  const stage2ReadyToFinalize = workflow?.stages.stage2?.status === 'COMPLETE'
    || workflow?.stages.stage2?.status === 'OVERRIDDEN';
  const targetMatches = input.result?.scope === input.scope && input.result.slug === input.slug;
  const canStatus = input.slugValid && !input.busy;
  const canStart = canStatus && (!targetMatches || !workflow?.present);
  const canResume = canStatus && targetMatches && workflow?.present === true && !terminal;
  const canFinalize = canStatus
    && targetMatches
    && input.scope === 'submissions'
    && stage2ReadyToFinalize
    && !terminal;
  const primaryCommand: WorkflowCommand = canFinalize
    ? 'finalize'
    : canResume
      ? 'resume'
      : canStart
        ? 'start'
        : 'status';
  return { canStatus, canStart, canResume, canFinalize, primaryCommand };
}
