import { afterEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import WorkflowOperator, {
  CostAuthorizationNotice,
  ReviewCenterPauseNotice,
} from '../components/WorkflowOperator';
import {
  COST_AUTHORIZATION_GUIDANCE,
  isCostAuthorizationPause,
  isReviewCenterPause,
  normalizeWorkflowResult,
  runWorkflowCommand,
  workflowCommandAvailability,
} from './workflowOperator';
import type { WorkflowCommandResultView } from '../types/workflowOperator';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('CR-112 workflow operator client', () => {
  it('normalizes only supported Stage 0, Stage 1, and Stage 2 status fields', () => {
    // Implements FR-316 / AC-413: keep the browser on the projected status contract.
    const result = normalizeWorkflowResult({
      command: 'status',
      scope: 'submissions',
      slug: 'fixture',
      privateField: 'do-not-render',
      workflow: {
        present: true,
        status: 'WAITING_FOR_INPUT',
        mode: 'production',
        activeStage: 'stage0',
        updatedAt: '2026-09-16T12:00:00Z',
        stages: {
          stage0: { status: 'WAITING_FOR_INPUT', integrity: 'CLEAN', secret: 'hidden' },
          stage1: { status: 'LOCKED', integrity: 'CLEAN' },
          stage2: {
            status: 'LOCKED',
            integrity: 'CLEAN',
            subphases: { truth: { status: 'READY', integrity: 'CLEAN' } },
          },
          stage3: { status: 'LOCKED', integrity: 'CLEAN' },
        },
        receipts: [{
          stage: 'stage0',
          status: 'WAITING_FOR_INPUT',
          integrity: 'CLEAN',
          pause: {
            kind: 'cost_authorization',
            modelCallOccurred: false,
            costKnown: false,
            nextPaths: [
              'import_cascade_json',
              'certify_zero_charge',
              'paid_allowlist_budget',
              'unexpected_path',
            ],
            providerReason: 'hidden',
          },
        }],
      },
    });

    expect(result).toEqual({
      command: 'status',
      scope: 'submissions',
      slug: 'fixture',
      workflow: {
        present: true,
        status: 'WAITING_FOR_INPUT',
        mode: 'production',
        activeStage: 'stage0',
        updatedAt: '2026-09-16T12:00:00Z',
        stages: {
          stage0: { status: 'WAITING_FOR_INPUT', integrity: 'CLEAN' },
          stage1: { status: 'LOCKED', integrity: 'CLEAN' },
          stage2: {
            status: 'LOCKED',
            integrity: 'CLEAN',
            subphases: { truth: { status: 'READY', integrity: 'CLEAN' } },
          },
        },
        receipts: [{
          stage: 'stage0',
          status: 'WAITING_FOR_INPUT',
          integrity: 'CLEAN',
          pause: {
            kind: 'cost_authorization',
            modelCallOccurred: false,
            costKnown: false,
            nextPaths: [
              'import_cascade_json',
              'certify_zero_charge',
              'paid_allowlist_budget',
            ],
          },
        }],
      },
    });
    expect(JSON.stringify(result)).not.toContain('hidden');
    expect(JSON.stringify(result)).not.toContain('stage3');
  });

  it('uses the authenticated API boundary for every workflow command', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      workflow: { present: false, stages: {}, receipts: [] },
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    for (const command of ['status', 'start', 'resume', 'finalize'] as const) {
      await runWorkflowCommand('pending-review', 'Acme Role', command);
    }

    expect(fetchMock.mock.calls.map(call => [call[0], call[1]?.method])).toEqual([
      ['/api/run-submission/pending-review/Acme%20Role/status', 'POST'],
      ['/api/run-submission/pending-review/Acme%20Role/start', 'POST'],
      ['/api/run-submission/pending-review/Acme%20Role/resume', 'POST'],
      ['/api/run-submission/pending-review/Acme%20Role/finalize', 'POST'],
    ]);
  });

  it('surfaces the bounded backend error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(
      JSON.stringify({ error: 'Workflow has not started. Use start first.' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(runWorkflowCommand('submissions', 'fixture', 'resume'))
      .rejects.toThrow('Workflow has not started. Use start first.');
  });

  it('contains the complete Stage 0 cost-authorization guidance', () => {
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('No model API call occurred');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('no API cost was incurred');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('Stage 0 is incomplete');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('import cascade JSON');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('certify a zero-charge provider');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('authorize paid use');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('before you resume');

    const markup = renderToStaticMarkup(React.createElement(CostAuthorizationNotice));
    expect(markup).toContain('No model API call occurred');
    expect(markup).toContain('no API cost was incurred');
    expect(markup).toContain('Stage 0 is incomplete');
    expect(markup).toContain('Do not paste authoring_prompt.md');
    expect(COST_AUTHORIZATION_GUIDANCE).toContain('Do not paste authoring_prompt.md');
  });

  it('renders the compact operator controls without filesystem or Python calls', () => {
    const markup = renderToStaticMarkup(React.createElement(WorkflowOperator));
    expect(markup).toContain('Run submission');
    expect(markup).toContain('Pending review');
    expect(markup).toContain('Submissions');
    expect(markup).toContain('Start');
    expect(markup).toContain('Resume');
    expect(markup).toContain('Finalize');
    expect(markup).toContain('Load status');
    expect(markup.match(/<button[^>]*\sdisabled(?:="[^"]*")?[^>]*>/g)?.length).toBe(4);
    expect(markup).not.toContain('python');
    expect(markup).not.toContain('workflow_state.json');
  });

  it('recognizes Stage 0 cost pauses and Review Center pauses', () => {
    const costPause = normalizeWorkflowResult({
      command: 'status',
      scope: 'pending-review',
      slug: 'fixture',
      workflow: {
        present: true,
        receipts: [{ stage: 'stage0', pause: { kind: 'cost_authorization', nextPaths: [] } }],
      },
    });
    const reviewPause = normalizeWorkflowResult({
      command: 'status',
      scope: 'submissions',
      slug: 'fixture',
      workflow: {
        present: true,
        receipts: [{ stage: 'stage0', pause: { kind: 'review_center', nextPaths: [] } }],
      },
    });
    expect(isCostAuthorizationPause(costPause)).toBe(true);
    expect(isReviewCenterPause(costPause)).toBe(false);
    expect(isReviewCenterPause(reviewPause)).toBe(true);
    expect(isCostAuthorizationPause(reviewPause)).toBe(false);

    const reviewMarkup = renderToStaticMarkup(React.createElement(ReviewCenterPauseNotice));
    expect(reviewMarkup).toContain('Resolve them in the queue below');
  });

  it('enables Start before a workflow exists and Finalize only after Stage 2 on submissions', () => {
    const idle = workflowCommandAvailability({
      slugValid: true,
      busy: false,
      scope: 'pending-review',
      slug: 'fixture',
      result: null,
    });
    expect(idle).toMatchObject({
      canStatus: true,
      canStart: true,
      canResume: false,
      canFinalize: false,
      primaryCommand: 'start',
    });

    const inProgress: WorkflowCommandResultView = {
      command: 'status',
      scope: 'submissions',
      slug: 'fixture',
      workflow: {
        present: true,
        status: 'WAITING_FOR_INPUT',
        mode: 'production',
        activeStage: 'stage0',
        updatedAt: null,
        stages: {
          stage0: { status: 'WAITING_FOR_INPUT', integrity: 'CLEAN' },
          stage1: { status: 'LOCKED', integrity: 'CLEAN' },
          stage2: { status: 'LOCKED', integrity: 'CLEAN' },
        },
        receipts: [],
      },
    };
    expect(workflowCommandAvailability({
      slugValid: true,
      busy: false,
      scope: 'submissions',
      slug: 'fixture',
      result: inProgress,
    })).toMatchObject({
      canStart: false,
      canResume: true,
      canFinalize: false,
      primaryCommand: 'resume',
    });

    const readyToFinalize: WorkflowCommandResultView = {
      ...inProgress,
      workflow: {
        ...inProgress.workflow,
        status: 'IN_PROGRESS',
        stages: {
          ...inProgress.workflow.stages,
          stage2: { status: 'COMPLETE', integrity: 'CLEAN' },
        },
      },
    };
    expect(workflowCommandAvailability({
      slugValid: true,
      busy: false,
      scope: 'submissions',
      slug: 'fixture',
      result: readyToFinalize,
    }).primaryCommand).toBe('finalize');
    expect(workflowCommandAvailability({
      slugValid: true,
      busy: false,
      scope: 'pending-review',
      slug: 'fixture',
      result: { ...readyToFinalize, scope: 'pending-review' },
    }).canFinalize).toBe(false);
  });
});
