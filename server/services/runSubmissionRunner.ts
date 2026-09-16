import fs from 'fs';
import path from 'path';
import {
  pythonScriptPath,
  runBuffered,
} from '../pipeline/processRunner.js';
import {
  SKIPPED_ARCHIVE_DIR,
  SUBMISSION_DIR,
} from '../shared.js';

const PENDING_REVIEW_DIR = path.join(SUBMISSION_DIR, '..', 'pending_review');
const STAGES = ['stage0', 'stage1', 'stage2', 'stage3'] as const;
const STAGE_NAMES = new Set<string>(STAGES);
const STAGE2_SUBPHASES = ['truth', 'ats', 'hm', 'mech', 'policy'] as const;
const MUTATING_COMMANDS = new Set<RunSubmissionCommand>(['start', 'resume', 'finalize']);
const SLUG_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const activeMutations = new Set<string>();
const WORKFLOW_STATUSES = new Set([
  'NOT_STARTED',
  'IN_PROGRESS',
  'WAITING_FOR_INPUT',
  'WAITING_FOR_LLM',
  'NEEDS_DISPOSITION',
  'SKIPPED',
  'COMPLETE',
  'COMPLETE_WITH_OVERRIDE',
  'PRACTICE_COMPLETE',
  'STALE',
  'FAILED',
]);
const STAGE_STATUSES = new Set([
  'READY',
  'LOCKED',
  'RUNNING',
  'IN_PROGRESS',
  'WAITING_FOR_INPUT',
  'WAITING_FOR_LLM',
  'NEEDS_DISPOSITION',
  'SKIPPED',
  'COMPLETE',
  'STALE',
  'FAILED',
  'OVERRIDDEN',
]);
const INTEGRITY_VALUES = new Set(['CLEAN', 'STALE', 'OVERRIDDEN']);
const MODES = new Set(['production', 'practice']);
const PAUSE_KINDS = new Set(['cost_authorization', 'review_center']);
const ATTEMPTED_OPERATIONS = new Set(['evidence_classification']);
const AUTHORIZATION_MODES = new Set([
  'unknown',
  'free_only',
  'paid_with_budget',
  'offline',
  'manual_paste',
]);
const COST_CONFIDENCE_VALUES = new Set(['unknown', 'zero', 'estimated', 'confirmed']);
const NEXT_PATH_VALUES = new Set([
  'import_cascade_json',
  'certify_zero_charge',
  'paid_allowlist_budget',
]);
const EXPECTED_NONZERO_STATUSES = new Set([
  'SKIPPED',
  'NEEDS_DISPOSITION',
  'STALE',
]);
const UTC_TIMESTAMP_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

export type RunSubmissionCommand = 'start' | 'resume' | 'status' | 'finalize';
export type RunSubmissionScope = 'pending-review' | 'submissions';

export interface RunSubmissionRoots {
  pendingReview: string;
  submissions: string;
  skippedArchive: string;
}

export interface RunSubmissionRequest {
  command: RunSubmissionCommand;
  scope: RunSubmissionScope;
  slug: string;
}

export interface WorkflowStageStatus {
  status: string | null;
  integrity: string | null;
  subphases?: Record<string, WorkflowStageStatus>;
}

export interface WorkflowPauseStatus {
  kind: string | null;
  attemptedOperation: string | null;
  authorizationMode: string | null;
  modelCallOccurred: boolean | null;
  costKnown: boolean | null;
  costConfidence: string | null;
  nextPaths: string[];
  pendingCount?: number;
}

export interface WorkflowReceiptStatus extends WorkflowStageStatus {
  stage: string;
  pause?: WorkflowPauseStatus;
}

export interface WorkflowStatus {
  present: boolean;
  status: string | null;
  mode: string | null;
  activeStage: string | null;
  updatedAt: string | null;
  stages: Record<string, WorkflowStageStatus>;
  receipts: WorkflowReceiptStatus[];
}

export interface RunSubmissionCommandResult {
  command: RunSubmissionCommand;
  scope: RunSubmissionScope;
  slug: string;
  workflow: WorkflowStatus;
}

interface ProcessResult {
  code: number;
  stdout: string;
  stderr: string;
}

interface RunSubmissionDependencies {
  roots?: RunSubmissionRoots;
  scriptPath?: string;
  execute?: (
    args: string[],
    options?: { cwd?: string; env?: Record<string, string>; stdin?: string },
  ) => Promise<ProcessResult>;
}

export class RunSubmissionServiceError extends Error {
  constructor(
    public readonly statusCode: number,
    message: string,
  ) {
    super(message);
    this.name = 'RunSubmissionServiceError';
  }
}

const DEFAULT_ROOTS: RunSubmissionRoots = {
  pendingReview: PENDING_REVIEW_DIR,
  submissions: SUBMISSION_DIR,
  skippedArchive: SKIPPED_ARCHIVE_DIR,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function enumOrNull(value: unknown, allowed: ReadonlySet<string>): string | null {
  return typeof value === 'string' && allowed.has(value) ? value : null;
}

function booleanOrNull(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function readJsonObject(filePath: string, label: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (!isRecord(parsed)) {
      throw new RunSubmissionServiceError(500, `${label} is not a JSON object.`);
    }
    return parsed;
  } catch (error) {
    if (isRecord(error) && 'code' in error && error.code === 'ENOENT') {
      return null;
    }
    if (error instanceof RunSubmissionServiceError) throw error;
    throw new RunSubmissionServiceError(500, `Unable to read ${label}.`);
  }
}

function rootForScope(scope: RunSubmissionScope, roots: RunSubmissionRoots): string {
  return scope === 'pending-review' ? roots.pendingReview : roots.submissions;
}

function resolveFolder(
  scope: RunSubmissionScope,
  slug: string,
  roots: RunSubmissionRoots,
): string {
  if (!SLUG_RE.test(slug)) {
    throw new RunSubmissionServiceError(400, 'Invalid submission slug.');
  }
  const root = rootForScope(scope, roots);
  const folder = path.join(root, slug);
  let realRoot: string;
  let realFolder: string;
  try {
    realRoot = fs.realpathSync(root);
    realFolder = fs.realpathSync(folder);
  } catch {
    throw new RunSubmissionServiceError(404, 'Submission folder not found.');
  }
  const relative = path.relative(realRoot, realFolder);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new RunSubmissionServiceError(400, 'Invalid submission folder.');
  }
  if (!fs.statSync(realFolder).isDirectory()) {
    throw new RunSubmissionServiceError(404, 'Submission folder not found.');
  }
  return realFolder;
}

function stageStatus(value: unknown): WorkflowStageStatus {
  const row = isRecord(value) ? value : {};
  const subphases: Record<string, WorkflowStageStatus> = {};
  if (isRecord(row.subphases)) {
    for (const subphase of STAGE2_SUBPHASES) {
      if (subphase in row.subphases) {
        subphases[subphase] = stageStatus(row.subphases[subphase]);
      }
    }
  }
  return {
    status: enumOrNull(row.status, STAGE_STATUSES),
    integrity: enumOrNull(row.integrity, INTEGRITY_VALUES),
    ...(Object.keys(subphases).length === 0 ? {} : { subphases }),
  };
}

function pauseStatus(result: Record<string, unknown>): WorkflowPauseStatus | undefined {
  if (!('pause_kind' in result)) return undefined;
  const rawNextPaths = Array.isArray(result.next_paths) ? result.next_paths : [];
  const nextPaths = rawNextPaths.filter(
    (value): value is string => typeof value === 'string' && NEXT_PATH_VALUES.has(value),
  );
  const pending = Array.isArray(result.pending) ? result.pending.length : undefined;
  return {
    kind: enumOrNull(result.pause_kind, PAUSE_KINDS),
    attemptedOperation: enumOrNull(result.attempted_operation, ATTEMPTED_OPERATIONS),
    authorizationMode: enumOrNull(result.authorization_mode, AUTHORIZATION_MODES),
    modelCallOccurred: booleanOrNull(result.model_call_occurred),
    costKnown: booleanOrNull(result.cost_known),
    costConfidence: enumOrNull(result.cost_confidence, COST_CONFIDENCE_VALUES),
    nextPaths,
    ...(pending === undefined ? {} : { pendingCount: pending }),
  };
}

function readWorkflowStatus(folder: string): WorkflowStatus {
  const state = readJsonObject(path.join(folder, 'workflow_state.json'), 'workflow state');
  const stages: Record<string, WorkflowStageStatus> = {};
  if (state && isRecord(state.stages)) {
    for (const stage of STAGES) {
      if (stage in state.stages) stages[stage] = stageStatus(state.stages[stage]);
    }
  }

  const receipts: WorkflowReceiptStatus[] = [];
  for (const stage of STAGES) {
    const receipt = readJsonObject(
      path.join(folder, 'stage_receipts', `${stage}.json`),
      `${stage} receipt`,
    );
    if (!receipt) continue;
    const result = isRecord(receipt.result) ? receipt.result : {};
    const pause = pauseStatus(result);
    receipts.push({
      stage,
      ...stageStatus(receipt),
      ...(pause ? { pause } : {}),
    });
  }

  return {
    present: state !== null,
    status: enumOrNull(state?.status, WORKFLOW_STATUSES),
    mode: enumOrNull(state?.mode, MODES),
    activeStage: enumOrNull(state?.active_stage, STAGE_NAMES),
    updatedAt: typeof state?.updated_at === 'string' && UTC_TIMESTAMP_RE.test(state.updated_at)
      ? state.updated_at
      : null,
    stages,
    receipts,
  };
}

function findFolderAfterRun(
  originalFolder: string,
  slug: string,
  roots: RunSubmissionRoots,
): string {
  if (fs.existsSync(originalFolder)) return originalFolder;
  for (const root of [roots.pendingReview, roots.submissions, roots.skippedArchive]) {
    const candidate = path.join(root, slug);
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new RunSubmissionServiceError(500, 'Submission folder was not found after the command.');
}

function commandArgs(
  command: RunSubmissionCommand,
  scriptPath: string,
  folder: string,
): string[] {
  const flags: Record<RunSubmissionCommand, string[]> = {
    start: [],
    resume: ['--resume'],
    status: ['--status'],
    finalize: ['--finalize'],
  };
  return [scriptPath, folder, ...flags[command]];
}

/**
 * Invoke the authoritative submission CLI and return its private-data-safe status projection.
 * Implements FR-316 / AC-413 while preserving FR-164 / AC-170 and FR-167 / AC-173.
 */
export async function runSubmissionCommand(
  request: RunSubmissionRequest,
  dependencies: RunSubmissionDependencies = {},
): Promise<RunSubmissionCommandResult> {
  const roots = dependencies.roots ?? DEFAULT_ROOTS;
  const mutating = MUTATING_COMMANDS.has(request.command);
  const folder = resolveFolder(request.scope, request.slug, roots);
  const lockKey = folder.toLowerCase();
  if (mutating && activeMutations.has(lockKey)) {
    throw new RunSubmissionServiceError(409, 'Submission workflow is already running.');
  }
  if (mutating) activeMutations.add(lockKey);

  try {
    const before = readWorkflowStatus(folder);
    if (request.command === 'start' && before.present) {
      throw new RunSubmissionServiceError(409, 'Workflow has already started. Use resume instead.');
    }
    if (
      (request.command === 'resume' || request.command === 'finalize')
      && !before.present
    ) {
      throw new RunSubmissionServiceError(409, 'Workflow has not started. Use start first.');
    }

    const execute = dependencies.execute ?? runBuffered;
    const processResult = await execute(commandArgs(
      request.command,
      dependencies.scriptPath ?? pythonScriptPath('run_submission.py'),
      folder,
    ));
    const resultFolder = findFolderAfterRun(folder, request.slug, roots);
    const workflow = readWorkflowStatus(resultFolder);
    if (
      processResult.code !== 0
      && !EXPECTED_NONZERO_STATUSES.has(workflow.status ?? '')
      && !(request.command === 'status' && !workflow.present)
    ) {
      throw new RunSubmissionServiceError(422, 'Submission workflow command failed.');
    }
    return {
      command: request.command,
      scope: request.scope,
      slug: request.slug,
      workflow,
    };
  } finally {
    if (mutating) activeMutations.delete(lockKey);
  }
}
