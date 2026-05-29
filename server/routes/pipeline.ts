import { Router } from 'express';
import path from 'path';
import { spawn } from 'child_process';
import { db, logActivity } from '../db.js';
import { SCRIPTS_DIR, PROJECT_ROOT } from '../shared.js';
import { runScoutSync } from '../scout.js';
import {
  attachClientAbort,
  buildSpawnEnv,
  isPipelineBusy,
  requireApiToken,
  releasePipeline,
  tryAcquirePipeline,
} from '../middleware.js';

const router = Router();

router.use(requireApiToken);

type PipelineResult = {
  score?: number;
  passed?: boolean;
  company?: string;
  title?: string;
  url?: string;
  summary?: string;
  exitCode?: number;
};

function parsePipelineResultLine(line: string): PipelineResult | null {
  try {
    const parsed = JSON.parse(line) as PipelineResult;
    if ('score' in parsed || ('passed' in parsed && 'summary' in parsed)) {
      return parsed;
    }
  } catch {
    /* not json */
  }
  return null;
}

// ---------------------------------------------------------------------------
// Evaluate — single-JD fit scoring + asset drafting via SSE stream
// ---------------------------------------------------------------------------

router.post('/api/evaluate', (req, res) => {
  const { company, jd, url } = req.body;
  if (!company || !jd) return res.status(400).json({ error: 'company and jd are required' });

  const label = `Generating tailored assets for ${company}`;
  if (!tryAcquirePipeline(label)) {
    return res.status(409).json({ error: 'Pipeline is already running. Try again when sync/evaluate completes.' });
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const send = (event: string, data: object) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  send('stage', { id: 'gate', status: 'running' });

  const proc = spawn('python', [path.join(SCRIPTS_DIR, 'batch_pipeline.py'), '--company', company, '--url', url || '', '--mode', 'single'], {
    cwd: PROJECT_ROOT,
    shell: false,
    env: buildSpawnEnv(),
  });

  proc.stdin.write(jd);
  proc.stdin.end();

  let buffer = '';
  let lastResult: PipelineResult | null = null;

  proc.stdout.on('data', (chunk: Buffer) => {
    buffer += chunk.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      const resultLine = parsePipelineResultLine(line.trim());
      if (resultLine) lastResult = resultLine;
      try { send('stage', JSON.parse(line)); }
      catch { send('log', { message: line.trim() }); }
    }
  });

  proc.stderr.on('data', (chunk: Buffer) => {
    send('log', { level: 'error', message: chunk.toString().trim() });
  });

  attachClientAbort(req, res, proc, () => {
    logActivity('WARN', 'Pipeline', `Evaluation for "${company}" aborted by client disconnect`);
    releasePipeline('Evaluation cancelled');
  });

  proc.on('close', (code: number) => {
    const passed = lastResult?.passed ?? code === 0;
    send('done', {
      exitCode: code,
      passed,
      score: lastResult?.score ?? 0,
      company: lastResult?.company ?? company,
      title: lastResult?.title ?? 'Product Manager',
      url: lastResult?.url ?? url ?? '',
      summary: lastResult?.summary ?? '',
    });
    res.end();
    logActivity(code === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Evaluation for "${company}" exited with code ${code}`);
    releasePipeline(`Completed asset generation for ${company}`);
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
