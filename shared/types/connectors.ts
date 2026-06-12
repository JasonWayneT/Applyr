export interface JobConnector {
  sourceId: string;
  fetchJobs(since?: string): Promise<RawJobPayload[]>;
  healthCheck(): Promise<ConnectorHealth>;
  normalize(raw: RawJobPayload): NormalizedJob;
}

export interface RawJobPayload {
  external_job_id: string;
  url: string;
  source_id: string;
  raw_data: Record<string, unknown>;
}

export interface NormalizedJob {
  external_job_id: string;
  source_id: string;
  title: string;
  company: string;
  url: string;
  source_site: string;
  location?: string;
  salary_range?: string;
  description?: string;
  posted_at?: string;
}

export interface ConnectorHealth {
  status: 'ok' | 'degraded' | 'error';
  last_checked: string;
  latency_ms?: number;
  error?: string;
}

export type SourceStatus = 'active' | 'warning' | 'error' | 'paused';

export type SSEEvent =
  | { type: 'source_progress'; source: string; fetched: number; filtered: number; passed: number }
  | { type: 'stage_handoff'; from: string; to: string; total_passed: number }
  | { type: 'source_health'; source: string; status: SourceStatus }
  | { type: 'connector_error'; source: string; error: string; http_status?: number }
  | { type: 'run_complete'; total_fetched: number; total_passed: number; sources_warned: string[] };
