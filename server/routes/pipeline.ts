import { Router } from 'express';
import { runScoutSync } from '../scout.js';
import { requireApiToken } from '../middleware.js';
import { isPipelineBusy } from '../pipelineLock.js';

const router = Router();

router.use(requireApiToken);

// POST /api/evaluate removed (CR-093, 2026-08-19) — the old single-JD fit-
// scoring + drafting route behind the "Find New Jobs" page, spawning
// batch_pipeline.py --mode single (now deleted). Confirmed dead by Jason;
// Find New Jobs itself is being removed in the same pass. The real
// fit-scoring + authoring flow is scripts/run_submission.py, triggered from
// a Claude Code chat session, not this server. See docs/spec/05-change-
// requests/CR-093-evidence-scale-fit-engine.md.

// SSE client list for broadcasting pipeline sync updates
let sseClients: any[] = [];

export function broadcastSyncEvent(event: string, data: object) {
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  sseClients.forEach((client) => client.write(payload));
}

// ---------------------------------------------------------------------------
// Sync SSE Stream endpoint
// ---------------------------------------------------------------------------
router.get('/api/sync/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  sseClients.push(res);

  req.on('close', () => {
    sseClients = sseClients.filter((client) => client !== res);
  });
});

// ---------------------------------------------------------------------------
// Sync — triggers full scout → backfill → scrape → evaluate pipeline
// ---------------------------------------------------------------------------

router.post('/api/sync', (_req, res) => {
  if (isPipelineBusy()) {
    return res.status(409).json({ error: 'Pipeline is already running.' });
  }
  runScoutSync();
  res.json({ message: 'Sync started' });
});

export default router;
