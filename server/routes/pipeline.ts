import { Router } from 'express';
import path from 'path';
import { spawn } from 'child_process';
import { db, logActivity } from '../db.js';
import { buildPythonEnv, SCRIPTS_DIR, PROJECT_ROOT } from '../shared.js';
import { runScoutSync } from '../scout.js';

const router = Router();

// ---------------------------------------------------------------------------
// Evaluate — single-JD fit scoring + asset drafting via SSE stream
// ---------------------------------------------------------------------------

router.post('/api/evaluate', (req, res) => {
  const { company, jd, url } = req.body;
  if (!company || !jd) return res.status(400).json({ error: 'company and jd are required' });

  db.prepare(`UPDATE system_status SET status = 'drafting', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Generating tailored assets for ${company}`);

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const send = (event: string, data: object) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  send('stage', { id: 'gate', status: 'running' });

  const proc = spawn('python', [path.join(SCRIPTS_DIR, 'batch_pipeline.py'), '--company', company, '--url', url || '', '--mode', 'single'], {
    cwd: PROJECT_ROOT,
    env: { ...process.env, ...buildPythonEnv() },
  });

  proc.stdin.write(jd);
  proc.stdin.end();

  let buffer = '';
  proc.stdout.on('data', (chunk: Buffer) => {
    buffer += chunk.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      try { send('stage', JSON.parse(line)); }
      catch { send('log', { message: line.trim() }); }
    }
  });

  proc.stderr.on('data', (chunk: Buffer) => {
    send('log', { level: 'error', message: chunk.toString().trim() });
  });

  proc.on('close', (code: number) => {
    send('done', { exitCode: code, passed: code === 0 });
    res.end();
    logActivity(code === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Evaluation for "${company}" exited with code ${code}`);
    db.prepare(`UPDATE system_status SET status = 'completed', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Completed asset generation for ${company}`);
  });
});

// ---------------------------------------------------------------------------
// Sync — triggers full scout → backfill → scrape → evaluate pipeline
// ---------------------------------------------------------------------------

router.post('/api/sync', (_req, res) => {
  runScoutSync();
  res.json({ message: 'Sync started' });
});

export default router;
