import type { Request, Response, NextFunction } from 'express';
import { spawn, type ChildProcessWithoutNullStreams } from 'child_process';
import path from 'path';
import { db } from './db.js';
import { PROJECT_ROOT, SCRIPTS_DIR, buildPythonEnv } from './shared.js';

const SECRET_ENV_KEYS = new Set([
  'GEMINI_API_KEY',
  'GOOGLE_API_KEY',
  'ANTHROPIC_API_KEY',
  'PERPLEXITY_API_KEY',
  'OPENAI_API_KEY',
  'ADZUNA_APP_KEY',
  'ADZUNA_APP_ID',
]);

const BUSY_STATUSES = new Set(['drafting', 'scout_running']);

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/** Optional API token — when APPLYR_API_TOKEN is set, require X-Applyr-Token on mutating routes. */
export function requireApiToken(req: Request, res: Response, next: NextFunction) {
  const token = process.env.APPLYR_API_TOKEN;
  if (!token) return next();
  const header = req.headers['x-applyr-token'];
  if (typeof header === 'string' && header === token) return next();
  return res.status(401).json({ error: 'Unauthorized' });
}

export function isValidJobId(id: string): boolean {
  return UUID_RE.test(id);
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
    WHERE id = 'global' AND status NOT IN ('drafting', 'scout_running')
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

export function buildSpawnEnv(extra: Record<string, string> = {}): Record<string, string> {
  const env: Record<string, string> = { ...buildPythonEnv(), ...extra };
  for (const [key, value] of Object.entries(process.env)) {
    if (value === undefined || SECRET_ENV_KEYS.has(key)) continue;
    if (key.startsWith('npm_') || key.startsWith('NODE_')) continue;
    env[key] = value;
  }
  return env;
}

export function runPythonScript(
  args: string[],
  options: { cwd?: string; env?: Record<string, string>; stdin?: string } = {},
): Promise<{ code: number; stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn('python', args, {
      cwd: options.cwd ?? PROJECT_ROOT,
      shell: false,
      env: options.env ?? buildSpawnEnv(),
    });

    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (chunk: Buffer) => { stdout += chunk.toString(); });
    proc.stderr.on('data', (chunk: Buffer) => { stderr += chunk.toString(); });
    if (options.stdin !== undefined) {
      proc.stdin.write(options.stdin);
    }
    proc.stdin.end();

    proc.on('error', reject);
    proc.on('close', (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
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
