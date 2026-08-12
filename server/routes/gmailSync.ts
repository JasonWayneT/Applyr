// CR-072 — manual "check inbox now" trigger, added at Jason's request alongside the 10-minute
// background interval (Epic 3). Awaits and returns the real summary rather than fire-and-forget, since
// the whole point of a manual check is immediate feedback on what it found.
import { Router } from 'express';
import { requireApiToken } from '../middleware.js';
import { db } from '../db.js';
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

// Feeds the Notifications panel — surfaces real (non-dry-run) confirmation/rejection detections from
// either trigger path (manual "Check Gmail Now" or the 10-minute background scheduler), since both write
// through the same runGmailSync() and land in activity_log under source='GmailSync'. Dry-run entries use
// source='GmailSyncDryRun' and are excluded by construction, not by filtering.
router.get('/api/gmail-sync/notifications', (_req, res) => {
  try {
    const rows = db
      .prepare(
        `SELECT id, timestamp, message, meta FROM activity_log
         WHERE source = 'GmailSync' AND meta IS NOT NULL
         ORDER BY timestamp DESC LIMIT 20`,
      )
      .all() as { id: number; timestamp: string; message: string; meta: string | null }[];

    const notifications = rows
      .map((row) => {
        let meta: Record<string, any> = {};
        try {
          meta = JSON.parse(row.meta ?? '{}');
        } catch {
          meta = {};
        }
        if (meta.event !== 'gmail_sync_confirmation' && meta.event !== 'gmail_sync_rejection') return null;
        return {
          id: row.id,
          timestamp: row.timestamp,
          category: meta.event === 'gmail_sync_rejection' ? 'rejection' : 'confirmation',
          job_id: meta.job_id ?? null,
          company: meta.company ?? null,
          subject: meta.subject ?? null,
          message: row.message,
        };
      })
      .filter(Boolean);

    res.json(notifications);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch Gmail sync notifications' });
  }
});

export default router;
