import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { db, logActivity } from './db.js';
import { runScoutSync } from './scout.js';
import { TITLE_BLOCKLIST, INDUSTRY_BLOCKLIST_DEFAULT } from './config.js';

dotenv.config();

// __dirname must be declared first — all path constants depend on it
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORK_EXPERIENCE_PATH = path.join(__dirname, '../data/workExperience.md');
const SUBMISSION_DIR = path.join(__dirname, '../submissions');
const ARCHIVE_DIR = path.join(__dirname, '../archive/submissions');

// Ensure archive dir exists on boot
if (!fs.existsSync(ARCHIVE_DIR)) {
  fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
}

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
app.get('/api/config', (_req, res) => {
  res.json({ titleBlocklist: TITLE_BLOCKLIST, industryBlocklist: INDUSTRY_BLOCKLIST_DEFAULT });
});

// ---------------------------------------------------------------------------
// Activity logs
// ---------------------------------------------------------------------------
app.get('/api/logs', (_req, res) => {
  try {
    const logs = db.prepare('SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 100').all();
    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch logs' });
  }
});

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------
app.get('/api/jobs', (_req, res) => {
  try {
    const jobs = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC').all();
    res.json(jobs);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch jobs' });
  }
});

// API: Update Job Status + physically move submission folder
app.patch('/api/jobs/:id/status', (req, res) => {
  try {
    const { id } = req.params;
    const { status } = req.body;

    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const companySlug = job.company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const activePath = path.join(SUBMISSION_DIR, companySlug);
    const archivePath = path.join(ARCHIVE_DIR, companySlug);

    // Only "Backlog" is considered active workspace — everything else is archived
    const isNowArchived = status !== 'Backlog';
    const wasArchived = job.status !== 'Backlog';

    if (isNowArchived && !wasArchived && fs.existsSync(activePath)) {
      fs.renameSync(activePath, archivePath);
    } else if (!isNowArchived && wasArchived && fs.existsSync(archivePath)) {
      fs.renameSync(archivePath, activePath);
    }

    db.prepare('UPDATE jobs SET status = ? WHERE id = ?').run(status, id);
    logActivity('INFO', 'System', `Job "${job.company}" status changed to ${status}`);

    res.json({ success: true, status });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job status' });
  }
});

// API: List files for a job (from submissions or archive)
app.get('/api/jobs/:id/files', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const companySlug = job.company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const folderPath = job.status === 'Backlog'
      ? path.join(SUBMISSION_DIR, companySlug)
      : path.join(ARCHIVE_DIR, companySlug);

    if (!fs.existsSync(folderPath)) return res.json({ files: [] });

    const files = fs.readdirSync(folderPath)
      .filter(f => ['.pdf', '.md', '.txt', '.json'].some(ext => f.endsWith(ext)))
      .map(f => ({ name: f, path: folderPath }));

    res.json({ files });
  } catch (err) {
    res.status(500).json({ error: 'Failed to list files' });
  }
});

// API: Download/serve a file for a job
app.get('/api/jobs/:id/files/:filename', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const companySlug = job.company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const folder = job.status === 'Backlog' ? SUBMISSION_DIR : ARCHIVE_DIR;
    const filePath = path.join(folder, companySlug, req.params.filename);

    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });

    res.sendFile(filePath);
  } catch (err) {
    res.status(500).json({ error: 'Failed to serve file' });
  }
});

// ---------------------------------------------------------------------------
// Pipeline: Run drafting engine for a single JD
// ---------------------------------------------------------------------------
app.post('/api/evaluate', (req, res) => {
  const { company, jd, url } = req.body;
  if (!company || !jd) return res.status(400).json({ error: 'company and jd are required' });

  // Set up SSE stream
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.flushHeaders();

  const send = (event: string, data: object) => {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  };

  const { spawn } = require('child_process');
  const scriptPath = path.join(__dirname, '../scripts/batch_pipeline.py');

  send('stage', { id: 'gate', status: 'running' });

  const proc = spawn('python', [scriptPath, '--company', company, '--url', url || '', '--mode', 'single'], {
    cwd: path.join(__dirname, '..'),
    env: { ...process.env }
  });

  let buffer = '';
  proc.stdout.on('data', (chunk: Buffer) => {
    buffer += chunk.toString();
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const parsed = JSON.parse(line);
        send('stage', parsed);
      } catch {
        // raw log line — forward as info
        send('log', { message: line.trim() });
      }
    }
  });

  proc.stderr.on('data', (chunk: Buffer) => {
    send('log', { level: 'error', message: chunk.toString().trim() });
  });

  proc.on('close', (code: number) => {
    send('done', { exitCode: code, passed: code === 0 });
    res.end();
    logActivity(code === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Evaluation for "${company}" exited with code ${code}`);
  });
});

// ---------------------------------------------------------------------------
// Profile
// ---------------------------------------------------------------------------
app.get('/api/profile/:key', (req, res) => {
  try {
    const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(req.params.key) as any;
    res.json(row ? JSON.parse(row.value) : {});
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

app.post('/api/profile/:key', (req, res) => {
  try {
    const value = JSON.stringify(req.body);
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(req.params.key, value);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to update profile' });
  }
});

// ---------------------------------------------------------------------------
// Work Experience
// ---------------------------------------------------------------------------
app.get('/api/experience', (_req, res) => {
  try {
    if (!fs.existsSync(WORK_EXPERIENCE_PATH)) {
      return res.json({ content: '# Work Experience\n\nNo data found.' });
    }
    res.json({ content: fs.readFileSync(WORK_EXPERIENCE_PATH, 'utf-8') });
  } catch (err) {
    res.status(500).json({ error: 'Failed to read experience file' });
  }
});

app.post('/api/experience', (req, res) => {
  try {
    const { content } = req.body;
    fs.writeFileSync(WORK_EXPERIENCE_PATH, content, 'utf-8');
    logActivity('INFO', 'System', 'workExperience.md updated by user.');
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to save experience file' });
  }
});

// ---------------------------------------------------------------------------
// Scout
// ---------------------------------------------------------------------------
app.post('/api/sync', (_req, res) => {
  runScoutSync();
  res.json({ message: 'Sync started' });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`\n${'='.repeat(48)}`);
  console.log(`  JobAgent Server  →  http://localhost:${PORT}`);
  console.log(`${'='.repeat(48)}\n`);
  logActivity('INFO', 'Server', 'System initialized. Ready for syncing.');
});
