import type { Request, Response, NextFunction } from 'express';
import type { ChildProcessWithoutNullStreams } from 'child_process';
import { db } from './db.js';
import { SCRIPTS_DIR } from './shared.js';
import { buildSpawnEnv, runBuffered } from './pipeline/processRunner.js';

export { buildSpawnEnv } from './pipeline/processRunner.js';

const BUSY_STATUSES = new Set(['drafting', 'scout_running', 'evaluate_running']);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Optional API token — when APPLYR_API_TOKEN is set, require X-Applyr-Token on mutating routes only (CR-025). */
export function requireApiToken(req: Request, res: Response, next: NextFunction) {
  const token = process.env.APPLYR_API_TOKEN;
  if (!token) return next();
  if (req.method === 'GET' || req.method === 'HEAD' || req.method === 'OPTIONS') return next();
  const header = req.headers['x-applyr-token'];
  if (typeof header === 'string' && header === token) return next();
  return res.status(401).json({ error: 'Unauthorized' });
}

export function isValidJobId(id: string): boolean {
  if (!id || id.length > 128) return false;
  if (id.includes('..') || id.includes('/') || id.includes('\\')) return false;
  if (UUID_RE.test(id)) return true;
  return /^[a-zA-Z0-9_-]+$/.test(id);
}

export function isSafeHttpUrl(url: string | null | undefined): boolean {
  if (!url) return true;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export function isPipelineBusy(): boolean {
  const row = db.prepare(`SELECT status FROM system_status WHERE id = 'global'`).get() as
    | { status: string }
    | undefined;
  return BUSY_STATUSES.has(row?.status ?? '');
}

export function tryAcquirePipeline(currentItem: string): boolean {
  if (isPipelineBusy()) return false;
  const result = db.prepare(`
    UPDATE system_status
    SET status = 'drafting', current_item = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = 'global' AND status NOT IN ('drafting', 'scout_running', 'evaluate_running')
  `).run(currentItem);
  return result.changes > 0;
}

export function releasePipeline(message: string) {
  db.prepare(`
    UPDATE system_status
    SET status = 'completed', current_item = ?, updated_at = CURRENT_TIMESTAMP
    WHERE id = 'global'
  `).run(message);
}

export function runPythonScript(
  args: string[],
  options: { cwd?: string; env?: Record<string, string>; stdin?: string } = {},
): Promise<{ code: number; stdout: string; stderr: string }> {
  return runBuffered(args, options);
}

export function attachClientAbort(
  req: Request,
  res: Response,
  proc: ChildProcessWithoutNullStreams,
  onAbort?: () => void,
) {
  req.on('close', () => {
    if (!res.writableEnded && !proc.killed) {
      proc.kill('SIGTERM');
      onAbort?.();
    }
  });
}

export function formatSkillGapOutput(raw: unknown): { success: boolean; output?: string; error?: string } {
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && 'error' in raw) {
    return { success: false, error: String((raw as { error: string }).error) };
  }
  if (Array.isArray(raw)) {
    const lines = raw.map((item) => {
      if (item && typeof item === 'object' && 'gap' in item) {
        const gap = String((item as { gap: string }).gap);
        const strategy = 'strategy' in item ? String((item as { strategy: string }).strategy) : '';
        return strategy ? `• ${gap}: ${strategy}` : `• ${gap}`;
      }
      return `• ${String(item)}`;
    });
    return { success: true, output: lines.join('\n') };
  }
  if (typeof raw === 'string') {
    return { success: true, output: raw };
  }
  return { success: false, error: 'Unexpected skill-gap response format' };
}

export const PYTHON_SCRIPTS_DIR = SCRIPTS_DIR;
