import express from 'express';
import http from 'http';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  RunSubmissionServiceError,
  type RunSubmissionCommandResult,
} from '../../server/services/runSubmissionRunner.js';
import { createRunSubmissionRouter } from '../../server/routes/runSubmission.js';

const servers: http.Server[] = [];

const result: RunSubmissionCommandResult = {
  command: 'status',
  scope: 'submissions',
  slug: 'fixture',
  workflow: {
    present: true,
    status: 'WAITING_FOR_INPUT',
    mode: 'production',
    activeStage: 'stage0',
    updatedAt: null,
    stages: { stage0: { status: 'WAITING_FOR_INPUT', integrity: 'CLEAN' } },
    receipts: [],
  },
};

async function startServer(
  service: Parameters<typeof createRunSubmissionRouter>[0],
): Promise<string> {
  const app = express();
  app.use(express.json());
  app.use(createRunSubmissionRouter(service));
  const server = http.createServer(app);
  servers.push(server);
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => resolve());
  });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Test server did not bind');
  return `http://127.0.0.1:${address.port}`;
}

afterEach(async () => {
  for (const server of servers.splice(0)) {
    await new Promise<void>(resolve => server.close(() => resolve()));
  }
  delete process.env.APPLYR_API_TOKEN;
});

describe('run-submission operator routes', () => {
  it('fails closed when no operator token is configured', async () => {
    const service = vi.fn(async () => result);
    const baseUrl = await startServer(service);
    const response = await fetch(
      `${baseUrl}/api/run-submission/submissions/fixture/status`,
      { method: 'POST' },
    );

    expect(response.status).toBe(503);
    expect(service).not.toHaveBeenCalled();
  });

  it('requires the configured token for status and mutating commands', async () => {
    process.env.APPLYR_API_TOKEN = 'test-token';
    const service = vi.fn(async () => result);
    const baseUrl = await startServer(service);

    const status = await fetch(`${baseUrl}/api/run-submission/submissions/fixture/status`, {
      method: 'POST',
    });
    const start = await fetch(`${baseUrl}/api/run-submission/pending-review/fixture/start`, {
      method: 'POST',
    });

    expect(status.status).toBe(401);
    expect(start.status).toBe(401);
    expect(service).not.toHaveBeenCalled();
  });

  it.each(['start', 'resume', 'status', 'finalize'] as const)(
    'dispatches the authenticated %s command',
    async command => {
      process.env.APPLYR_API_TOKEN = 'test-token';
      const service = vi.fn(async request => ({ ...result, ...request }));
      const baseUrl = await startServer(service);
      const response = await fetch(
        `${baseUrl}/api/run-submission/submissions/fixture/${command}`,
        { method: 'POST', headers: { 'X-Applyr-Token': 'test-token' } },
      );

      expect(response.status).toBe(200);
      expect(service).toHaveBeenCalledWith({
        command,
        scope: 'submissions',
        slug: 'fixture',
      });
    },
  );

  it('returns bounded service errors without process details', async () => {
    process.env.APPLYR_API_TOKEN = 'test-token';
    const service = vi.fn(async () => {
      throw new RunSubmissionServiceError(409, 'Submission workflow is already running.');
    });
    const baseUrl = await startServer(service);
    const response = await fetch(
      `${baseUrl}/api/run-submission/submissions/fixture/resume`,
      { method: 'POST', headers: { 'X-Applyr-Token': 'test-token' } },
    );

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({
      error: 'Submission workflow is already running.',
    });
  });
});
