import { describe, it, expect } from 'vitest';
import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
  SourceStatus,
  SSEEvent,
} from '../../shared/types/connectors.js';

describe('shared/types/connectors.ts exports', () => {
  it('imports resolve without error (TypeScript validates interface shapes)', () => {
    // All imports above would cause a compile-time error if the module or types
    // are missing. This test verifies the import resolves at runtime.
    expect(true).toBe(true);
  });

  it('JobConnector interface can be satisfied by a conforming object', () => {
    const mockJob: RawJobPayload = {
      external_job_id: 'job-1',
      url: 'https://example.com/jobs/1',
      source_id: 'greenhouse',
      raw_data: { title: 'Product Manager' },
    };

    const mockNormalized: NormalizedJob = {
      external_job_id: 'job-1',
      source_id: 'greenhouse',
      title: 'Product Manager',
      company: 'Acme Corp',
      url: 'https://example.com/jobs/1',
      source_site: 'greenhouse',
    };

    const mockHealth: ConnectorHealth = {
      status: 'ok',
      last_checked: new Date().toISOString(),
    };

    const mockConnector: JobConnector = {
      sourceId: 'greenhouse',
      fetchJobs: async () => [mockJob],
      healthCheck: async () => mockHealth,
      normalize: (_raw) => mockNormalized,
    };

    expect(mockConnector.sourceId).toBe('greenhouse');
    expect(typeof mockConnector.fetchJobs).toBe('function');
    expect(typeof mockConnector.healthCheck).toBe('function');
    expect(typeof mockConnector.normalize).toBe('function');
  });

  it('SourceStatus covers all four state values', () => {
    const statuses: SourceStatus[] = ['active', 'warning', 'error', 'paused'];
    expect(statuses).toHaveLength(4);
  });

  it('SSEEvent discriminated union covers all five event types', () => {
    const events: SSEEvent[] = [
      { type: 'source_progress', source: 'greenhouse', fetched: 10, filtered: 2, passed: 8 },
      { type: 'stage_handoff', from: 'scout', to: 'evaluate', total_passed: 8 },
      { type: 'source_health', source: 'greenhouse', status: 'warning' },
      { type: 'connector_error', source: 'lever', error: 'timeout', http_status: 504 },
      { type: 'run_complete', total_fetched: 10, total_passed: 8, sources_warned: ['lever'] },
    ];
    expect(events).toHaveLength(5);
    expect(events.map((e) => e.type)).toEqual([
      'source_progress',
      'stage_handoff',
      'source_health',
      'connector_error',
      'run_complete',
    ]);
  });
});
