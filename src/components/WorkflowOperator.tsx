import React, { useState } from 'react';
import {
  COST_AUTHORIZATION_GUIDANCE,
  REVIEW_CENTER_PAUSE_GUIDANCE,
  isCostAuthorizationPause,
  isReviewCenterPause,
  runWorkflowCommand,
  workflowCommandAvailability,
} from '../lib/workflowOperator';
import type {
  WorkflowCommand,
  WorkflowCommandResultView,
  WorkflowScope,
  WorkflowStageName,
  WorkflowStageView,
} from '../types/workflowOperator';

const STAGES: Array<{ id: WorkflowStageName; label: string; helper: string }> = [
  { id: 'stage0', label: 'Stage 0', helper: 'Fit and evidence' },
  { id: 'stage1', label: 'Stage 1', helper: 'Authoring' },
  { id: 'stage2', label: 'Stage 2', helper: 'Review and verify' },
];
const SLUG_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

function statusTone(status: string | null | undefined): string {
  if (status === 'COMPLETE' || status === 'OVERRIDDEN') {
    return 'bg-success-container text-on-success-container';
  }
  if (
    status === 'WAITING_FOR_INPUT'
    || status === 'WAITING_FOR_LLM'
    || status === 'NEEDS_DISPOSITION'
  ) {
    return 'bg-warning-container text-on-warning-container';
  }
  if (status === 'FAILED' || status === 'STALE') {
    return 'bg-error-container text-on-error-container';
  }
  return 'bg-surface-container-highest text-on-surface-variant';
}

function displayStatus(stage: WorkflowStageView | undefined): string {
  return stage?.status?.replace(/_/g, ' ') ?? 'Not available';
}

function StageCard({
  label,
  helper,
  stage,
}: {
  label: string;
  helper: string;
  stage?: WorkflowStageView;
}) {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-3 outlined-surface min-w-0">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-bold text-on-surface">{label}</p>
          <p className="text-[10px] text-on-surface-variant mt-1">{helper}</p>
        </div>
        <span className={`badge whitespace-nowrap ${statusTone(stage?.status)}`}>
          {displayStatus(stage)}
        </span>
      </div>
      {stage?.integrity && (
        <p className="text-[10px] text-on-surface-variant mt-3">
          Integrity: {stage.integrity.toLowerCase()}
        </p>
      )}
    </div>
  );
}

export function CostAuthorizationNotice() {
  return (
    <div
      role="alert"
      className="bg-warning-container text-on-warning-container rounded-xl p-4 flex items-start gap-3"
    >
      <span className="material-symbols-outlined text-lg mt-1">paid</span>
      <div>
        <p className="text-sm font-bold">Stage 0 needs cost authorization</p>
        <p className="text-xs leading-relaxed mt-1">{COST_AUTHORIZATION_GUIDANCE}</p>
      </div>
    </div>
  );
}

export function ReviewCenterPauseNotice() {
  return (
    <div
      role="status"
      className="bg-warning-container text-on-warning-container rounded-xl p-4 flex items-start gap-3"
    >
      <span className="material-symbols-outlined text-lg mt-1">fact_check</span>
      <div>
        <p className="text-sm font-bold">Waiting on Review Center</p>
        <p className="text-xs leading-relaxed mt-1">{REVIEW_CENTER_PAUSE_GUIDANCE}</p>
      </div>
    </div>
  );
}

export default function WorkflowOperator() {
  // Implements FR-316 / AC-413: this UI calls only the authenticated backend
  // operator. Workflow authority remains in run_submission.py and its receipts.
  const [scope, setScope] = useState<WorkflowScope>('pending-review');
  const [slug, setSlug] = useState('');
  const [result, setResult] = useState<WorkflowCommandResultView | null>(null);
  const [busyCommand, setBusyCommand] = useState<WorkflowCommand | null>(null);
  const [error, setError] = useState<string | null>(null);

  const normalizedSlug = slug.trim();
  const slugValid = SLUG_PATTERN.test(normalizedSlug);
  const { canStatus, canStart, canResume, canFinalize, primaryCommand } = workflowCommandAvailability({
    slugValid,
    busy: busyCommand !== null,
    scope,
    slug: normalizedSlug,
    result,
  });

  const clearLoadedStatus = () => {
    setResult(null);
    setError(null);
  };

  const execute = async (command: WorkflowCommand) => {
    if (!slugValid || busyCommand) return;
    setBusyCommand(command);
    setError(null);
    try {
      setResult(await runWorkflowCommand(scope, normalizedSlug, command));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Workflow command failed.');
    } finally {
      setBusyCommand(null);
    }
  };

  const commandClass = (command: WorkflowCommand) => (
    `${command === primaryCommand ? 'btn-primary' : 'btn-secondary'} min-h-10 px-4 text-xs disabled:opacity-50`
  );

  return (
    <section className="bg-surface-container-low rounded-2xl p-4 outlined-surface" aria-labelledby="workflow-operator-heading">
      <div className="flex flex-col xl:flex-row xl:items-end gap-4">
        <div className="xl:w-56 shrink-0">
          <p className="text-[10px] uppercase tracking-widest font-bold text-primary">Workflow operator</p>
          <h2 id="workflow-operator-heading" className="text-lg font-headline font-extrabold text-on-surface mt-1">
            Run submission
          </h2>
          <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
            Operate one folder through the canonical workflow.
          </p>
        </div>

        <label className="xl:w-44 shrink-0">
          <span className="block text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1.5">
            Folder
          </span>
          <select
            value={scope}
            onChange={event => {
              setScope(event.target.value as WorkflowScope);
              clearLoadedStatus();
            }}
            className="input-applyr w-full min-h-10"
            disabled={busyCommand !== null}
          >
            <option value="pending-review">Pending review</option>
            <option value="submissions">Submissions</option>
          </select>
        </label>

        <label className="min-w-0 flex-1">
          <span className="block text-[10px] uppercase tracking-widest font-bold text-on-surface-variant mb-1.5">
            Folder slug
          </span>
          <input
            value={slug}
            onChange={event => {
              setSlug(event.target.value);
              clearLoadedStatus();
            }}
            placeholder="company_role"
            className="input-applyr w-full min-h-10"
            spellCheck={false}
            autoCapitalize="none"
            disabled={busyCommand !== null}
          />
        </label>

        <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => { void execute('status'); }}
            disabled={!canStatus}
            className={commandClass('status')}
          >
            {busyCommand === 'status' ? 'Loading...' : 'Load status'}
          </button>
          <button
            type="button"
            onClick={() => { void execute('start'); }}
            disabled={!canStart}
            className={commandClass('start')}
          >
            {busyCommand === 'start' ? 'Starting...' : 'Start'}
          </button>
          <button
            type="button"
            onClick={() => { void execute('resume'); }}
            disabled={!canResume}
            className={commandClass('resume')}
          >
            {busyCommand === 'resume' ? 'Resuming...' : 'Resume'}
          </button>
          <button
            type="button"
            onClick={() => { void execute('finalize'); }}
            disabled={!canFinalize}
            className={commandClass('finalize')}
          >
            {busyCommand === 'finalize' ? 'Finalizing...' : 'Finalize'}
          </button>
        </div>
      </div>

      {normalizedSlug && !slugValid && (
        <p className="text-xs text-error mt-3">
          Use letters, numbers, hyphens, or underscores. The slug must start with a letter or number.
        </p>
      )}

      {error && (
        <div role="alert" className="bg-error-container text-on-error-container rounded-xl px-4 py-3 mt-4 flex items-center gap-3">
          <span className="material-symbols-outlined text-base">error</span>
          <p className="text-xs flex-1">{error}</p>
        </div>
      )}

      {result && (
        <div className="mt-4 space-y-4" aria-live="polite">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {STAGES.map(stage => (
              <StageCard
                key={stage.id}
                label={stage.label}
                helper={stage.helper}
                stage={result.workflow.stages[stage.id]}
              />
            ))}
          </div>

          {isCostAuthorizationPause(result) && <CostAuthorizationNotice />}
          {isReviewCenterPause(result) && <ReviewCenterPauseNotice />}

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-on-surface-variant">
            <span>
              Workflow: {(result.workflow.status ?? (result.workflow.present ? 'UNKNOWN' : 'NOT STARTED'))
                .replace(/_/g, ' ')}
            </span>
            {result.workflow.activeStage && (
              <span>Active: {result.workflow.activeStage.replace('stage', 'Stage ')}</span>
            )}
            {result.workflow.updatedAt && (
              <span>Updated: {new Date(result.workflow.updatedAt).toLocaleString()}</span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
