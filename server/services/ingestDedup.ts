import { randomUUID, createHash } from 'crypto';
import type BetterSqlite3 from 'better-sqlite3';
import type { RawJobPayload } from '../../shared/types/connectors.js';

export interface IngestDedupService {
  checkUrlExists(url: string): string | null;
  insertRawPayload(sourceId: string, job: RawJobPayload, httpStatus?: number): string;
}

export function createIngestDedupService(db: BetterSqlite3.Database): IngestDedupService {
  const checkStmt = db.prepare<[string], { external_job_id: string }>(
    'SELECT external_job_id FROM job_ingest_raw WHERE request_url = ? LIMIT 1',
  );

  const insertStmt = db.prepare<
    [string, string, string, string, string, string, number, string]
  >(
    `INSERT INTO job_ingest_raw
       (id, source_id, fetched_at, external_job_id, payload_json, payload_hash, http_status, request_url)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
  );

  function checkUrlExists(url: string): string | null {
    const row = checkStmt.get(url);
    return row?.external_job_id ?? null;
  }

  function insertRawPayload(sourceId: string, job: RawJobPayload, httpStatus = 200): string {
    const id = randomUUID();
    const payloadJson = JSON.stringify(job.raw_data);
    const payloadHash = createHash('sha256').update(payloadJson).digest('hex');
    insertStmt.run(
      id,
      sourceId,
      new Date().toISOString(),
      job.external_job_id,
      payloadJson,
      payloadHash,
      httpStatus,
      job.url,
    );
    return id;
  }

  return { checkUrlExists, insertRawPayload };
}
