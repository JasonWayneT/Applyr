import { Router } from 'express';
import { db } from '../db.js';
import { requireApiToken } from '../middleware.js';
import { buildDefaultConnectors, runConnectorOrchestration } from '../services/scoutOrchestrator.js';

const router = Router();

router.get('/api/sources', (_req, res) => {
  const sources = db.prepare('SELECT * FROM sources ORDER BY name').all();
  res.json(sources);
});

router.post('/api/sources/:id/sync', requireApiToken, (req, res) => {
  const { id } = req.params;

  const source = db.prepare('SELECT id FROM sources WHERE id = ?').get(id) as { id: string } | undefined;
  if (!source) {
    res.status(404).json({ error: 'Source not found' });
    return;
  }

  const connector = buildDefaultConnectors().find((c) => c.sourceId === id);
  if (!connector) {
    res.status(404).json({ error: 'Connector not available for this source' });
    return;
  }

  void runConnectorOrchestration([connector]);

  res.json({ id, started: true });
});

export default router;
