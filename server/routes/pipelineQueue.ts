import express, { Router } from 'express';
import type Database from 'better-sqlite3';
import { db } from '../db.js';
import { requireApiToken } from '../middleware.js';
import {
  STUCK_STALE_MINUTES,
  activeLeases,
  decisionItems,
  quarantineRows,
  queueCounts,
  stuckItems,
  waitingItems,
} from '../repository/pipelineQueueRepository.js';
import {
  CSV_INBOX_DIR,
  PIPELINE_DB_PATH,
  UPLOAD_MAX_BYTES,
  isCsvUpload,
  runInboxIngest,
  writeCsvUpload,
  type IngestCounts,
} from '../services/pipelineQueueUpload.js';
import { pythonScriptPath, runBuffered } from '../pipeline/processRunner.js';

export type PipelineQueueRouterDeps = {
  inboxDir?: string;
  dbPath?: string;
  ingest?: (inboxDir: string, dbPath: string) => Promise<IngestCounts>;
  writeUpload?: (buffer: Buffer, inboxDir: string) => string;
  maxBytes?: number;
};

function clientUploadName(header: string | string[] | undefined): string | undefined {
  return typeof header === 'string' ? header : undefined;
}

export function createPipelineQueueRouter(
  database: Database.Database = db,
  deps: PipelineQueueRouterDeps = {},
) {
  const router = Router();
  router.use(requireApiToken);

  router.get('/api/pipeline-queue/stats', (_req, res) => {
    try {
      return res.json({
        counts: queueCounts(database),
        leases: activeLeases(database),
        waiting: waitingItems(database),
        decisions: decisionItems(database),
        stuck: stuckItems(STUCK_STALE_MINUTES, database),
      });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: 'Failed to fetch pipeline queue stats' });
    }
  });

  router.get('/api/pipeline-queue/quarantine', (_req, res) => {
    try {
      return res.json({ items: quarantineRows(database) });
    } catch (err) {
      console.error(err);
      return res.status(500).json({ error: 'Failed to fetch pipeline quarantine' });
    }
  });

  router.post('/api/pipeline-queue/:slug/redo', async (req, res) => {
    const slug = String(req.params.slug || '');
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(slug)) {
      return res.status(400).json({ error: 'Invalid slug' });
    }
    try {
      const result = await runBuffered([
        pythonScriptPath('pipeline_queue.py'),
        'redo-one',
        slug,
      ]);
      if (result.code !== 0) {
        return res.status(400).json({ error: result.stderr.trim() || 'Could not retry this job' });
      }
      return res.json({ ok: true });
    } catch {
      return res.status(500).json({ error: 'Could not retry this job' });
    }
  });

  const maxBytes = deps.maxBytes ?? UPLOAD_MAX_BYTES;
  const inboxDir = deps.inboxDir ?? CSV_INBOX_DIR;
  const dbPath = deps.dbPath ?? PIPELINE_DB_PATH;
  const ingest = deps.ingest ?? runInboxIngest;
  const writeUpload = deps.writeUpload ?? writeCsvUpload;

  router.post(
    '/api/pipeline-queue/upload',
    express.raw({ type: () => true, limit: maxBytes }),
    async (req, res) => {
      const body = req.body;
      if (!Buffer.isBuffer(body) || body.length === 0) {
        return res.status(400).json({ error: 'CSV body required' });
      }
      if (body.length > maxBytes) {
        return res.status(413).json({ error: 'CSV too large' });
      }
      const contentType = req.headers['content-type'];
      if (typeof contentType === 'string' && contentType.toLowerCase().includes('multipart/')) {
        return res.status(415).json({ error: 'CSV only' });
      }
      const clientName = clientUploadName(req.headers['x-applyr-upload-name']);
      if (!isCsvUpload(contentType, clientName)) {
        return res.status(415).json({ error: 'CSV only' });
      }
      try {
        writeUpload(body, inboxDir);
        const counts = await ingest(inboxDir, dbPath);
        return res.json({
          queued: counts.queued,
          duplicate: counts.duplicate,
          quarantined: counts.quarantined,
        });
      } catch {
        console.error('pipeline-queue upload failed');
        return res.status(500).json({ error: 'Upload failed' });
      }
    },
  );

  router.use((err: unknown, _req: express.Request, res: express.Response, next: express.NextFunction) => {
    const status = typeof err === 'object' && err !== null && 'status' in err
      ? Number((err as { status?: number }).status)
      : 0;
    const type = typeof err === 'object' && err !== null && 'type' in err
      ? String((err as { type?: string }).type)
      : '';
    if (status === 413 || type === 'entity.too.large') {
      return res.status(413).json({ error: 'CSV too large' });
    }
    return next(err);
  });

  return router;
}

const pipelineQueueRouter = createPipelineQueueRouter();
export default pipelineQueueRouter;
