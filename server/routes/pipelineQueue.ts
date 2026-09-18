import { Router } from 'express';
import type Database from 'better-sqlite3';
import { db } from '../db.js';
import { requireApiToken } from '../middleware.js';
import {
  STUCK_STALE_MINUTES,
  activeLeases,
  quarantineRows,
  queueCounts,
  stuckItems,
} from '../repository/pipelineQueueRepository.js';

export function createPipelineQueueRouter(database: Database.Database = db) {
  const router = Router();
  router.use(requireApiToken);

  router.get('/api/pipeline-queue/stats', (_req, res) => {
    try {
      return res.json({
        counts: queueCounts(database),
        leases: activeLeases(database),
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

  return router;
}

const pipelineQueueRouter = createPipelineQueueRouter();
export default pipelineQueueRouter;
