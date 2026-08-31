import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { db } from '../db.js';
import { PROJECT_ROOT } from '../shared.js';
import { requireApiToken, isSafeHttpUrl } from '../middleware.js';

const router = Router();

// Apply token auth to mutating routes only (GET routes remain open, same as
// every other router — requireApiToken is a no-op for GET/HEAD/OPTIONS).
router.use(requireApiToken);

router.get('/api/system-status', (_req, res) => {
  try {
    const status = db.prepare('SELECT * FROM system_status WHERE id = ?').get('global');
    res.json(status || { status: 'idle', current_item: 'No active pipeline run' });
  } catch {
    res.status(500).json({ error: 'Failed to fetch system status' });
  }
});

router.post('/api/system-status', (req, res) => {
  try {
    const { status, current_item, items_completed, items_total } = req.body;
    db.prepare(`
      UPDATE system_status
      SET status           = COALESCE(?, status),
          current_item     = COALESCE(?, current_item),
          items_completed  = COALESCE(?, items_completed),
          items_total      = COALESCE(?, items_total),
          updated_at       = CURRENT_TIMESTAMP
      WHERE id = 'global'
    `).run(status || null, current_item || null, items_completed ?? null, items_total ?? null);
    res.json({ success: true });
  } catch {
    res.status(500).json({ error: 'Failed to update system status' });
  }
});

/**
 * Real fit-score bands for the UI (CR-093 evidence-scale engine), read from
 * data/fit_rubric_calibration.json -- the single source of truth for these numbers
 * (scripts/evidence_scale.py's load_score_bands() reads the same file). Added
 * 2026-08-20 to replace hardcoded 72/80/60 literals in SyncActivityView/TodayView/
 * AllJobsView that referenced the old, deleted fit-scoring system and were never
 * updated when CR-093 replaced it.
 */
router.get('/api/fit-thresholds', (_req, res) => {
  try {
    const calibrationPath = path.join(PROJECT_ROOT, 'data/fit_rubric_calibration.json');
    if (!fs.existsSync(calibrationPath)) {
      return res.json({ skip_floor: 40, tier1_floor: 65 });
    }
    const calibration = JSON.parse(fs.readFileSync(calibrationPath, 'utf-8'));
    const bands = calibration.score_bands || {};
    res.json({
      skip_floor: typeof bands.skip_floor === 'number' ? bands.skip_floor : 40,
      tier1_floor: typeof bands.tier1_floor === 'number' ? bands.tier1_floor : 65,
    });
  } catch {
    res.status(500).json({ error: 'Failed to fetch fit thresholds' });
  }
});

router.get('/api/ats-pipeline', (_req, res) => {
  try {
    const pipelinePath = path.join(PROJECT_ROOT, 'data/ats-pipeline.md');
    if (!fs.existsSync(pipelinePath)) return res.json({ jobs: [] });
    const content = fs.readFileSync(pipelinePath, 'utf-8');
    const jobs = content
      .split('\n')
      .filter(l => l.startsWith('- [ ]'))
      .map(l => {
        const parts = l.replace('- [ ]', '').trim().split('|').map(s => s.trim());
        return { url: parts[0] || '', company: parts[1] || 'Unknown', title: parts[2] || 'Product Role' };
      });
    res.json({ jobs });
  } catch {
    res.status(500).json({ error: 'Failed to fetch ATS pipeline' });
  }
});

router.get('/api/logs', (req, res) => {
  try {
    const q = req.query.q as string;
    if (q) {
      const logs = db.prepare(
        'SELECT * FROM activity_log WHERE message LIKE ? OR source LIKE ? ORDER BY timestamp DESC LIMIT 50'
      ).all(`%${q}%`, `%${q}%`);
      return res.json(logs);
    }
    const logs = db.prepare('SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 100').all();
    res.json(logs);
  } catch {
    res.status(500).json({ error: 'Failed to fetch logs' });
  }
});

router.post('/api/stream/local-model', (req, res) => {
  // Implements Server-Sent Events (SSE) for Local Model Streaming
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
  });
  
  const { prompt } = req.body;
  if (!prompt) {
    res.write('event: error\ndata: {"error":"Prompt required"}\n\n');
    return res.end();
  }
  
  const settingsRow = db.prepare("SELECT value FROM profiles WHERE key = 'llm_settings'").get() as { value: string } | undefined;
  const settings = settingsRow ? JSON.parse(settingsRow.value) : {};
  const baseUrl = settings.localUrl || 'http://localhost:11434';
  
  if (!isSafeHttpUrl(baseUrl)) {
    res.write(`event: error\ndata: ${JSON.stringify({ error: 'Configured local model URL must be http or https' })}\n\n`);
    return res.end();
  }
  
  fetch(`${baseUrl}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: settings.localFallbackModel || 'phi3.5:3.8b-mini-instruct-q8_0',
      prompt: prompt,
      stream: true
    })
  }).then(async (response) => {
    if (!response.body) throw new Error("No body");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      res.write(`data: ${JSON.stringify({ chunk })}\n\n`);
    }
    res.write('event: end\ndata: {}\n\n');
    res.end();
  }).catch(err => {
    res.write(`event: error\ndata: ${JSON.stringify({ error: err.message })}\n\n`);
    res.end();
  });
});

export default router;
