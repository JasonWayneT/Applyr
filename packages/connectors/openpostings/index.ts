import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import type { ChildProcess } from 'child_process';
import type {
  JobConnector,
  RawJobPayload,
  NormalizedJob,
  ConnectorHealth,
} from '../../../shared/types/connectors.js';

const DEFAULT_DIR = path.resolve('OpenPostings-extracted/OpenPostings-main');
const DEFAULT_PORT = 8787;
const DEFAULT_SEARCH_TERMS = ['product manager'];
const JOB_CAP = 60;
const STARTUP_TIMEOUT_MS = 20_000;
const SYNC_TIMEOUT_MS = 120_000;

interface OpenPostingsConfig {
  openPostingsDir?: string;
  port?: number;
  searchTerms?: string[];
}

function startServer(dir: string, port: number): Promise<ChildProcess> {
  return new Promise((resolve, reject) => {
    const proc = spawn('node', ['server/index.js'], {
      cwd: dir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, PORT: String(port) },
    });

    const timeout = setTimeout(
      () => reject(new Error('OpenPostings server did not start within timeout')),
      STARTUP_TIMEOUT_MS,
    );

    proc.stdout?.on('data', (chunk: Buffer) => {
      const line = chunk.toString();
      if (line.includes(String(port)) || line.includes('listening')) {
        clearTimeout(timeout);
        resolve(proc);
      }
    });

    proc.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}

async function waitForHealth(port: number): Promise<void> {
  for (let i = 0; i < 12; i++) {
    try {
      const res = await fetch(`http://localhost:${port}/health`);
      if (res.ok) return;
    } catch {
      /* not ready yet */
    }
    await new Promise((r) => setTimeout(r, 1_500));
  }
  throw new Error('OpenPostings health check timed out');
}

export function createOpenPostingsConnector(config?: OpenPostingsConfig): JobConnector {
  const openPostingsDir = config?.openPostingsDir ?? DEFAULT_DIR;
  const port = config?.port ?? DEFAULT_PORT;
  const searchTerms = config?.searchTerms ?? DEFAULT_SEARCH_TERMS;

  return {
    sourceId: 'openpostings',

    async fetchJobs(): Promise<RawJobPayload[]> {
      if (!fs.existsSync(openPostingsDir)) {
        return [];
      }

      const results: RawJobPayload[] = [];
      let proc: ChildProcess | null = null;

      try {
        proc = await startServer(openPostingsDir, port);
        await waitForHealth(port);

        fetch(`http://localhost:${port}/sync/ats`, { method: 'POST' }).catch(() => {});

        const deadline = Date.now() + SYNC_TIMEOUT_MS;
        while (Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 10_000));
          try {
            const s = (await (await fetch(`http://localhost:${port}/sync/status`)).json()) as {
              running?: boolean;
            };
            if (!s.running) break;
          } catch {
            break;
          }
        }

        for (const term of searchTerms) {
          if (results.length >= JOB_CAP) break;
          try {
            const url = `http://localhost:${port}/postings?search=${encodeURIComponent(term)}&remote=remote`;
            const res = await fetch(url);
            const data = (await res.json()) as unknown[];
            if (!Array.isArray(data)) continue;

            for (const p of data as Record<string, unknown>[]) {
              if (results.length >= JOB_CAP) break;
              const jobUrl = String(p['job_posting_url'] ?? '');
              const company = String(p['company_name'] ?? '').trim();
              const title = String(p['position_name'] ?? '').trim();
              if (!company || !title) continue;

              results.push({
                external_job_id: jobUrl || `openpostings:${company}:${title}`,
                url: jobUrl,
                source_id: 'openpostings',
                raw_data: p,
              });
            }
          } catch {
            /* skip failed term */
          }
        }
      } catch {
        /* server failed to start or other error — return empty */
      } finally {
        if (proc) proc.kill();
      }

      return results;
    },

    async healthCheck(): Promise<ConnectorHealth> {
      if (!fs.existsSync(openPostingsDir)) {
        return {
          status: 'error',
          last_checked: new Date().toISOString(),
          latency_ms: 0,
          error: `OpenPostings directory not found: ${openPostingsDir}`,
        };
      }
      return {
        status: 'ok',
        last_checked: new Date().toISOString(),
        latency_ms: 0,
      };
    },

    normalize(raw: RawJobPayload): NormalizedJob {
      const d = raw.raw_data;
      return {
        external_job_id: raw.external_job_id,
        source_id: 'openpostings',
        title: String(d['position_name'] ?? ''),
        company: String(d['company_name'] ?? ''),
        url: raw.url,
        source_site: 'openpostings',
        description: d['description'] ? String(d['description']).trim() || undefined : undefined,
      };
    },
  };
}
