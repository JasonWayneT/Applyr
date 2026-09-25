// CR-106 — feeds the Notifications panel with real provider-cascade events (a task's default LLM
// provider was rate-limited/quota-exhausted and either cascaded to the next configured provider or
// got disabled for 24h), the same read-only pattern gmailSync.ts's own notifications route already
// uses for Gmail-sourced events. A separate route/file rather than folding into gmailSync.ts because
// this isn't Gmail-specific — scripts/utils.py's Python-side callers write into the same activity_log
// table under source='LLM_Call' with meta.event='llm_provider_cascade' (see that file's
// _log_provider_notification), so this route reads across both languages' writes with one query.
import { Router } from 'express';
import type Database from 'better-sqlite3';
import { db } from '../db.js';

const router = Router();

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

export interface Stage0EvidenceUsage {
  runs: number;
  completedRuns: number;
  waitingRuns: number;
  failedRuns: number;
  batches: number;
  providerCalls: number;
  fallbacks: number;
  pendingConfirmations: number;
}

export function readStage0EvidenceUsage(database: Database.Database = db): Stage0EvidenceUsage {
  const runs = database
    .prepare('SELECT status, metadata_json FROM stage0_runs ORDER BY updated_at DESC LIMIT 500')
    .all() as { status: string; metadata_json: string | null }[];
  const usage: Stage0EvidenceUsage = {
    runs: runs.length,
    completedRuns: runs.filter(row => row.status === 'COMPLETE').length,
    waitingRuns: runs.filter(row => row.status === 'WAITING_FOR_INPUT').length,
    failedRuns: runs.filter(row => row.status === 'FAILED').length,
    batches: 0,
    providerCalls: 0,
    fallbacks: 0,
    pendingConfirmations: (
      database.prepare("SELECT count(*) AS count FROM pending_skill_confirmations WHERE status = 'open'").get() as { count: number }
    ).count,
  };
  for (const row of runs) {
    if (!row.metadata_json) continue;
    try {
      const metadata = JSON.parse(row.metadata_json) as Record<string, unknown>;
      usage.batches += typeof metadata.stage0_cascade_batches === 'number' ? metadata.stage0_cascade_batches : 0;
      usage.providerCalls += typeof metadata.stage0_cascade_provider_calls === 'number' ? metadata.stage0_cascade_provider_calls : 0;
      usage.fallbacks += typeof metadata.stage0_cascade_fallbacks === 'number' ? metadata.stage0_cascade_fallbacks : 0;
    } catch {
      // Ignore malformed legacy metadata. The endpoint remains aggregate-only.
    }
  }
  return usage;
}

// Implements FR-284 / OPS-012: expose aggregate Stage 0 cascade telemetry
// without returning prompts, responses, credentials, or candidate profile text.
router.get('/api/llm-usage/stage0-evidence', (_req, res) => {
  try {
    return res.json(readStage0EvidenceUsage());
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: 'Failed to fetch Stage 0 usage' });
  }
});

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
        let meta: Record<string, unknown> = {};
        try {
          meta = recordValue(JSON.parse(row.meta ?? '{}'));
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
