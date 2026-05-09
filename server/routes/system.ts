import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { db } from '../db.js';
import { PROJECT_ROOT } from '../shared.js';

const router = Router();

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

router.get('/api/ats-pipeline', (_req, res) => {
  try {
    const pipelinePath = path.join(PROJECT_ROOT, 'career-ops-main/data/pipeline.md');
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

export default router;
