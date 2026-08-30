// CR-106 — feeds the Notifications panel with real provider-cascade events (a task's default LLM
// provider was rate-limited/quota-exhausted and either cascaded to the next configured provider or
// got disabled for 24h), the same read-only pattern gmailSync.ts's own notifications route already
// uses for Gmail-sourced events. A separate route/file rather than folding into gmailSync.ts because
// this isn't Gmail-specific — scripts/utils.py's Python-side callers write into the same activity_log
// table under source='LLM_Call' with meta.event='llm_provider_cascade' (see that file's
// _log_provider_notification), so this route reads across both languages' writes with one query.
import { Router } from 'express';
import { db } from '../db.js';

const router = Router();

router.get('/api/llm-usage/notifications', (_req, res) => {
  try {
    const rows = db
      .prepare(
        `SELECT id, timestamp, message, meta FROM activity_log
         WHERE source = 'LLM_Call' AND meta IS NOT NULL
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
        if (meta.event !== 'llm_provider_cascade') return null;
        return {
          id: row.id,
          timestamp: row.timestamp,
          provider: meta.provider ?? null,
          reason: meta.reason ?? null,
          message: row.message,
        };
      })
      .filter(Boolean);

    res.json(notifications);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch LLM usage notifications' });
  }
});

export default router;
