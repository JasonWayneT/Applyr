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

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// API: Serve live gate config so frontend stays in sync with backend
app.get('/api/config', (_req, res) => {
  res.json({ titleBlocklist: TITLE_BLOCKLIST, industryBlocklist: INDUSTRY_BLOCKLIST_DEFAULT });
});

// API: Get recent activity logs
app.get('/api/logs', (req, res) => {
  try {
    const logs = db.prepare('SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 100').all();
    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch logs' });
  }
});

// API: Get jobs
app.get('/api/jobs', (req, res) => {
  try {
    const jobs = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC').all();
    res.json(jobs);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch jobs' });
  }
});

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORK_EXPERIENCE_PATH = path.join(__dirname, '../data/workExperience.md');

// API: Get Profile
app.get('/api/profile/:key', (req, res) => {
  try {
    const row = db.prepare('SELECT value FROM profiles WHERE key = ?').get(req.params.key) as any;
    res.json(row ? JSON.parse(row.value) : {});
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch profile' });
  }
});

// API: Update Profile
app.post('/api/profile/:key', (req, res) => {
  try {
    const value = JSON.stringify(req.body);
    db.prepare('INSERT OR REPLACE INTO profiles (key, value) VALUES (?, ?)').run(req.params.key, value);
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to update profile' });
  }
});

// API: Get Master Experience (Markdown)
app.get('/api/experience', (req, res) => {
  try {
    if (!fs.existsSync(WORK_EXPERIENCE_PATH)) {
      return res.json({ content: '# Work Experience\n\nNo data found.' });
    }
    const content = fs.readFileSync(WORK_EXPERIENCE_PATH, 'utf-8');
    res.json({ content });
  } catch (err) {
    res.status(500).json({ error: 'Failed to read experience file' });
  }
});

// API: Update Master Experience (Markdown)
app.post('/api/experience', (req, res) => {
  try {
    const { content } = req.body;
    fs.writeFileSync(WORK_EXPERIENCE_PATH, content, 'utf-8');
    logActivity('INFO', 'System', 'Master Experience (workExperience.md) updated by user.');
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: 'Failed to save experience file' });
  }
});

// API: Trigger sync
app.post('/api/sync', async (req, res) => {
  // Run in background
  runScoutSync();
  res.json({ message: 'Sync started' });
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
  logActivity('INFO', 'Server', 'System initialized. Ready for syncing.');
});
