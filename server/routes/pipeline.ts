import { Router } from 'express';
import { db, logActivity } from '../db.js';
import { runScoutSync } from '../scout.js';
import { spawnPython, pythonScriptPath } from '../pipeline/processRunner.js';
import {
  attachClientAbort,
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

  let buffer = '';
  let lastResult: PipelineResult | null = null;

  const proc = spawnPython(
    [pythonScriptPath('batch_pipeline.py'), '--company', company, '--url', url || '', '--mode', 'single'],
    {
      stdin: jd,
      onStdout: (chunk) => {
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          const resultLine = parsePipelineResultLine(line.trim());
          if (resultLine) lastResult = resultLine;
          try { send('stage', JSON.parse(line)); }
          catch { send('log', { message: line.trim() }); }
        }
      },
      onStderr: (chunk) => {
        send('log', { level: 'error', message: chunk.trim() });
      },
      onClose: (code) => {
        const exitCode = code ?? 1;
        const passed = lastResult?.passed ?? exitCode === 0;
        send('done', {
          exitCode,
          passed,
          score: lastResult?.score ?? 0,
          company: lastResult?.company ?? company,
          title: lastResult?.title ?? 'Product Manager',
          url: lastResult?.url ?? url ?? '',
          summary: lastResult?.summary ?? '',
        });
        res.end();
        logActivity(exitCode === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Evaluation for "${company}" exited with code ${exitCode}`);
        releasePipeline(`Completed asset generation for ${company}`);
      },
    },
  );

  attachClientAbort(req, res, proc, () => {
    logActivity('WARN', 'Pipeline', `Evaluation for "${company}" aborted by client disconnect`);
    releasePipeline('Evaluation cancelled');
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
