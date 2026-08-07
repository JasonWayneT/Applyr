// CR-072 — manual "check inbox now" trigger, added at Jason's request alongside the 10-minute
// background interval (Epic 3). Awaits and returns the real summary rather than fire-and-forget, since
// the whole point of a manual check is immediate feedback on what it found.
import { Router } from 'express';
import { requireApiToken } from '../middleware.js';
import { runGmailSync } from '../services/gmailSyncOrchestrator.js';

const router = Router();

router.post('/api/gmail-sync/run', requireApiToken, async (_req, res) => {
  try {
    const summary = await runGmailSync();
    res.json(summary);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Gmail sync failed', message: (err as Error).message });
  }
});

export default router;
