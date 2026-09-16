import fs from 'fs';
import os from 'os';
import path from 'path';
import { afterEach, describe, expect, it } from 'vitest';
import {
  RunSubmissionServiceError,
  runSubmissionCommand,
  type RunSubmissionRoots,
} from '../../server/services/runSubmissionRunner.js';

const tempRoots: string[] = [];

function createRoots(): RunSubmissionRoots {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'applyr-run-submission-'));
  tempRoots.push(root);
  const roots = {
    pendingReview: path.join(root, 'pending_review'),
    submissions: path.join(root, 'submissions'),
    skippedArchive: path.join(root, 'skipped'),
  };
  for (const value of Object.values(roots)) fs.mkdirSync(value, { recursive: true });
  return roots;
}

function createFolder(roots: RunSubmissionRoots, scope: 'pending-review' | 'submissions', slug: string): string {
  const folder = path.join(scope === 'pending-review' ? roots.pendingReview : roots.submissions, slug);
  fs.mkdirSync(folder, { recursive: true });
  fs.writeFileSync(path.join(folder, 'Original_JD.txt'), 'Synthetic fixture');
  return folder;
}

function writeStatus(folder: string): void {
  fs.mkdirSync(path.join(folder, 'stage_receipts'), { recursive: true });
  fs.writeFileSync(
    path.join(folder, 'workflow_state.json'),
    JSON.stringify({
      slug: 'fixture',
      mode: 'production',
      status: 'WAITING_FOR_INPUT',
      active_stage: 'stage0',
      updated_at: '2026-09-16T12:00:00Z',
      private_note: 'candidate-private',
      stages: {
        stage0: {
          status: 'WAITING_FOR_INPUT',
          integrity: 'CLEAN',
          receipt_id: 'secret-hash',
        },
        stage1: { status: 'LOCKED', integrity: 'CLEAN', receipt_id: null },
      },
    }),
  );
  fs.writeFileSync(
    path.join(folder, 'stage_receipts', 'stage0.json'),
    JSON.stringify({
      stage: 'stage0',
      status: 'WAITING_FOR_INPUT',
      integrity: 'CLEAN',
      receipt_id: 'secret-receipt',
      input_hashes: { 'Original_JD.txt': 'secret-input-hash' },
      checks: { private_check: 'candidate-private' },
      result: {
        pause_kind: 'cost_authorization',
        attempted_operation: 'evidence_classification',
        authorization_mode: 'unknown',
        model_call_occurred: false,
        cost_known: false,
        cost_confidence: 'unknown',
        next_paths: ['import_cascade_json', 'certify_zero_charge', 'paid_allowlist_budget'],
        ineligible_providers: [{ provider: 'private-provider', reason: 'private-reason' }],
        opportunity_key: 'private-opportunity',
      },
    }),
  );
}

afterEach(() => {
  for (const root of tempRoots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe('runSubmissionCommand', () => {
  it.each([
    ['start', []],
    ['resume', ['--resume']],
    ['finalize', ['--finalize']],
  ] as const)('runs %s with array arguments and no environment override', async (command, flags) => {
    const roots = createRoots();
    const folder = createFolder(roots, command === 'start' ? 'pending-review' : 'submissions', 'fixture');
    if (command !== 'start') writeStatus(folder);
    const calls: Array<{ args: string[]; options: unknown }> = [];

    const result = await runSubmissionCommand(
      { command, scope: command === 'start' ? 'pending-review' : 'submissions', slug: 'fixture' },
      {
        roots,
        scriptPath: path.join('scripts', 'run_submission.py'),
        execute: async (args, options) => {
          calls.push({ args, options });
          writeStatus(folder);
          return { code: 0, stdout: 'private output', stderr: 'private error' };
        },
      },
    );

    expect(calls).toEqual([{
      args: [path.join('scripts', 'run_submission.py'), folder, ...flags],
      options: undefined,
    }]);
    expect(result.workflow.status).toBe('WAITING_FOR_INPUT');
  });

  it('runs status through the process runner and returns an allowlisted projection', async () => {
    const roots = createRoots();
    const folder = createFolder(roots, 'submissions', 'fixture');
    writeStatus(folder);

    const result = await runSubmissionCommand(
      { command: 'status', scope: 'submissions', slug: 'fixture' },
      {
        roots,
        execute: async () => ({ code: 0, stdout: 'candidate-private', stderr: 'secret' }),
      },
    );

    expect(result.workflow).toEqual({
      present: true,
      status: 'WAITING_FOR_INPUT',
      mode: 'production',
      activeStage: 'stage0',
      updatedAt: '2026-09-16T12:00:00Z',
      stages: {
        stage0: { status: 'WAITING_FOR_INPUT', integrity: 'CLEAN' },
        stage1: { status: 'LOCKED', integrity: 'CLEAN' },
      },
      receipts: [{
        stage: 'stage0',
        status: 'WAITING_FOR_INPUT',
        integrity: 'CLEAN',
        pause: {
          kind: 'cost_authorization',
          attemptedOperation: 'evidence_classification',
          authorizationMode: 'unknown',
          modelCallOccurred: false,
          costKnown: false,
          costConfidence: 'unknown',
          nextPaths: ['import_cascade_json', 'certify_zero_charge', 'paid_allowlist_budget'],
        },
      }],
    });
    expect(JSON.stringify(result)).not.toContain('candidate-private');
    expect(JSON.stringify(result)).not.toContain('secret');
    expect(JSON.stringify(result)).not.toContain('private-provider');
    expect(JSON.stringify(result)).not.toContain(folder);
  });

  it('rejects overlapping mutating commands for the same slug', async () => {
    const roots = createRoots();
    const folder = createFolder(roots, 'submissions', 'fixture');
    writeStatus(folder);
    let release: (() => void) | undefined;
    const blocked = new Promise<void>(resolve => { release = resolve; });
    const first = runSubmissionCommand(
      { command: 'resume', scope: 'submissions', slug: 'fixture' },
      {
        roots,
        execute: async () => {
          await blocked;
          return { code: 0, stdout: '', stderr: '' };
        },
      },
    );
    await Promise.resolve();

    await expect(runSubmissionCommand(
      { command: 'finalize', scope: 'submissions', slug: 'fixture' },
      { roots, execute: async () => ({ code: 0, stdout: '', stderr: '' }) },
    )).rejects.toMatchObject({ statusCode: 409 });

    release?.();
    await first;
  });

  it('allows the same slug in different workflow roots to run independently', async () => {
    const roots = createRoots();
    const pending = createFolder(roots, 'pending-review', 'fixture');
    const submitted = createFolder(roots, 'submissions', 'fixture');
    writeStatus(submitted);
    let release: (() => void) | undefined;
    const blocked = new Promise<void>(resolve => { release = resolve; });
    const first = runSubmissionCommand(
      { command: 'resume', scope: 'submissions', slug: 'fixture' },
      {
        roots,
        execute: async () => {
          await blocked;
          return { code: 0, stdout: '', stderr: '' };
        },
      },
    );
    await Promise.resolve();

    const second = await runSubmissionCommand(
      { command: 'start', scope: 'pending-review', slug: 'fixture' },
      {
        roots,
        execute: async () => {
          writeStatus(pending);
          return { code: 0, stdout: '', stderr: '' };
        },
      },
    );

    expect(second.scope).toBe('pending-review');
    release?.();
    await first;
  });

  it('fails closed on traversal, missing folders, and malformed state', async () => {
    const roots = createRoots();
    await expect(runSubmissionCommand(
      { command: 'status', scope: 'submissions', slug: '../private' },
      { roots, execute: async () => ({ code: 0, stdout: '', stderr: '' }) },
    )).rejects.toMatchObject({ statusCode: 400 });
    await expect(runSubmissionCommand(
      { command: 'status', scope: 'submissions', slug: 'missing' },
      { roots, execute: async () => ({ code: 0, stdout: '', stderr: '' }) },
    )).rejects.toMatchObject({ statusCode: 404 });

    const folder = createFolder(roots, 'submissions', 'broken');
    fs.writeFileSync(path.join(folder, 'workflow_state.json'), '{not-json');
    await expect(runSubmissionCommand(
      { command: 'status', scope: 'submissions', slug: 'broken' },
      { roots, execute: async () => ({ code: 0, stdout: '', stderr: '' }) },
    )).rejects.toBeInstanceOf(RunSubmissionServiceError);
  });

  it('keeps start and resume semantics distinct and hides process output on failure', async () => {
    const roots = createRoots();
    const started = createFolder(roots, 'submissions', 'started');
    writeStatus(started);
    await expect(runSubmissionCommand(
      { command: 'start', scope: 'submissions', slug: 'started' },
      { roots, execute: async () => ({ code: 0, stdout: '', stderr: '' }) },
    )).rejects.toMatchObject({ statusCode: 409 });

    createFolder(roots, 'submissions', 'fresh');
    await expect(runSubmissionCommand(
      { command: 'resume', scope: 'submissions', slug: 'fresh' },
      {
        roots,
        execute: async () => ({
          code: 7,
          stdout: 'candidate-private-output',
          stderr: 'secret-provider-error',
        }),
      },
    )).rejects.toMatchObject({
      statusCode: 409,
      message: 'Workflow has not started. Use start first.',
    });

    const failed = createFolder(roots, 'submissions', 'failed');
    writeStatus(failed);
    await expect(runSubmissionCommand(
      { command: 'resume', scope: 'submissions', slug: 'failed' },
      {
        roots,
        execute: async () => ({
          code: 7,
          stdout: 'candidate-private-output',
          stderr: 'secret-provider-error',
        }),
      },
    )).rejects.toMatchObject({
      statusCode: 422,
      message: 'Submission workflow command failed.',
    });
  });

  it('returns structured terminal pauses even when the CLI uses a nonzero status code', async () => {
    const roots = createRoots();
    const folder = createFolder(roots, 'submissions', 'skipped');
    writeStatus(folder);
    const state = JSON.parse(
      fs.readFileSync(path.join(folder, 'workflow_state.json'), 'utf8'),
    ) as Record<string, unknown>;
    state.status = 'SKIPPED';
    fs.writeFileSync(path.join(folder, 'workflow_state.json'), JSON.stringify(state));

    const response = await runSubmissionCommand(
      { command: 'resume', scope: 'submissions', slug: 'skipped' },
      {
        roots,
        execute: async () => ({
          code: 2,
          stdout: 'Stage 0 Skip',
          stderr: '',
        }),
      },
    );

    expect(response.workflow.status).toBe('SKIPPED');
  });
});
