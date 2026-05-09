import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { exec, spawn } from 'child_process';
import { randomUUID } from 'crypto';
import AdmZip from 'adm-zip';
import { db, logActivity } from '../db.js';
import {
  buildPythonEnv, resolveCompanyFolder,
  SUBMISSION_DIR, ARCHIVE_DIR, SCRIPTS_DIR, PROJECT_ROOT,
  ALLOWED_JOB_FIELDS,
} from '../shared.js';

const router = Router();

const ACTIVE_STATUSES = new Set(['Backlog', 'Drafted']);

function jobBaseDir(status: string): string {
  return ACTIVE_STATUSES.has(status) ? SUBMISSION_DIR : ARCHIVE_DIR;
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------

router.get('/api/jobs', (_req, res) => {
  try {
    const jobs = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC').all() as any[];
    const enriched = jobs.map(job => {
      let has_assets = false;
      const folder = resolveCompanyFolder(job.company, SUBMISSION_DIR);
      if (fs.existsSync(folder)) {
        try { has_assets = fs.readdirSync(folder).some(f => f.toLowerCase().endsWith('.pdf')); } catch (_) {}
      }
      return { ...job, has_assets };
    });
    res.json(enriched);
  } catch {
    res.status(500).json({ error: 'Failed to fetch jobs' });
  }
});

router.post('/api/jobs', (req, res) => {
  try {
    const { id, company, title, url, score, summary, status } = req.body;
    if (!company || !title) return res.status(400).json({ error: 'company and title are required' });
    db.prepare(`
      INSERT INTO jobs (id, company, title, url, score, status, summary, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `).run(id || randomUUID(), company, title, url || null, score || null, status || 'Drafted', summary || null);
    logActivity('INFO', 'System', `Manually added job "${company}" to drafted.`);
    res.json({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to add job' });
  }
});

router.get('/api/jobs/stats', (_req, res) => {
  try {
    const total          = db.prepare('SELECT COUNT(*) as count FROM jobs').get() as any;
    const byStatus       = db.prepare('SELECT status, COUNT(*) as count FROM jobs GROUP BY status').all();
    const byRejStage     = db.prepare("SELECT rejection_stage, COUNT(*) as count FROM jobs WHERE status = 'Closed' GROUP BY rejection_stage").all();
    const byRejType      = db.prepare("SELECT rejection_type,  COUNT(*) as count FROM jobs WHERE status = 'Closed' GROUP BY rejection_type").all();
    res.json({ total: total.count, byStatus, byRejectionStage: byRejStage, byRejectionType: byRejType });
  } catch {
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

// ---------------------------------------------------------------------------
// Single job — status transitions and field updates
// ---------------------------------------------------------------------------

router.patch('/api/jobs/:id/status', (req, res) => {
  try {
    const { id } = req.params;
    const { status } = req.body;

    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const slug        = job.company.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
    const activePath  = path.join(SUBMISSION_DIR, slug);
    const archivePath = path.join(ARCHIVE_DIR, slug);

    if (status === 'No Longer Available') {
      const fullJob = db.prepare('SELECT company, title, url FROM jobs WHERE id = ?').get(id) as any;
      if (fullJob?.url) {
        db.prepare('INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)').run(fullJob.url, fullJob.company, fullJob.title);
      }
      if (fs.existsSync(activePath))  fs.rmSync(activePath,  { recursive: true, force: true });
      if (fs.existsSync(archivePath)) fs.rmSync(archivePath, { recursive: true, force: true });
      db.prepare('DELETE FROM jobs WHERE id = ?').run(id);
      logActivity('INFO', 'System', `Job "${job.company}" marked No Longer Available and completely deleted.`);
      return res.json({ success: true, deleted: true });
    }

    const isNowArchived = !ACTIVE_STATUSES.has(status);
    const wasArchived   = !ACTIVE_STATUSES.has(job.status);

    if (isNowArchived  && !wasArchived && fs.existsSync(activePath))  fs.renameSync(activePath,  archivePath);
    if (!isNowArchived && wasArchived  && fs.existsSync(archivePath)) fs.renameSync(archivePath, activePath);

    db.prepare(`
      UPDATE jobs
      SET status          = ?,
          rejection_stage = COALESCE(?, rejection_stage),
          rejection_type  = COALESCE(?, rejection_type),
          outcome_notes   = COALESCE(?, outcome_notes)
      WHERE id = ?
    `).run(
      status,
      status === 'Closed' ? (req.body.rejection_stage || job.status) : null,
      status === 'Closed' ? req.body.rejection_type   : null,
      status === 'Closed' ? req.body.outcome_notes    : null,
      id,
    );
    logActivity('INFO', 'System', `Job "${job.company}" status changed to ${status}`);
    res.json({ success: true, status });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job status' });
  }
});

router.patch('/api/jobs/:id', (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;
    // Build dynamic update — only permit known safe columns (SQL injection prevention)
    const keys = Object.keys(updates).filter(k => k !== 'id' && ALLOWED_JOB_FIELDS.has(k));
    if (keys.length === 0) return res.status(400).json({ error: 'No valid fields to update' });
    const setClause = keys.map(k => `${k} = ?`).join(', ');
    db.prepare(`UPDATE jobs SET ${setClause} WHERE id = ?`).run(...keys.map(k => updates[k]), id);
    res.json({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job details' });
  }
});

// ---------------------------------------------------------------------------
// File access
// ---------------------------------------------------------------------------

router.get('/api/jobs/:id/files', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });
    const folder = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    if (!fs.existsSync(folder)) return res.json({ files: [] });
    const files = fs.readdirSync(folder)
      .filter(f => ['.pdf', '.md', '.txt', '.json'].some(ext => f.endsWith(ext)))
      .map(f => ({ name: f, path: folder }));
    res.json({ files });
  } catch {
    res.status(500).json({ error: 'Failed to list files' });
  }
});

router.get('/api/jobs/:id/files/:filename', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });
    const folder       = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    const safeFilename = path.basename(req.params.filename); // strips path traversal
    const filePath     = path.join(folder, safeFilename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });
    res.sendFile(filePath);
  } catch {
    res.status(500).json({ error: 'Failed to serve file' });
  }
});

router.put('/api/jobs/:id/files/:filename', (req, res) => {
  try {
    const { id, filename } = req.params;
    const { text } = req.body;
    if (text === undefined) return res.status(400).json({ error: 'Text content is required' });

    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const folder       = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    const safeFilename = path.basename(filename);
    const filePath     = path.join(folder, safeFilename);
    if (!fs.existsSync(filePath)) return res.status(404).json({ error: 'File not found' });

    fs.writeFileSync(filePath, text, 'utf8');

    if (safeFilename.endsWith('.md')) {
      const pdfPath      = path.join(folder, safeFilename.replace('.md', '.pdf'));
      const guardScript  = path.join(SCRIPTS_DIR, 'style_compliance_guard.py');
      const compileScript = path.join(SCRIPTS_DIR, 'compile_single.py');
      exec(`python "${guardScript}" "${filePath}" && python "${compileScript}" "${filePath}" "${pdfPath}"`, (_err, _stdout, stderr) => {
        if (_err) {
          logActivity('ERROR', 'System', `Failed to validate and compile PDF for "${job.company}": ${stderr || _err.message}`);
          return res.status(500).json({ error: 'Document saved but validation or compilation failed' });
        }
        logActivity('INFO', 'System', `Successfully validated and compiled PDF for "${job.company}"`);
        res.json({ success: true, compiled: true });
      });
    } else {
      res.json({ success: true, compiled: false });
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to save file' });
  }
});

// ---------------------------------------------------------------------------
// AI rewrite
// ---------------------------------------------------------------------------

router.post('/api/jobs/:id/ai-rewrite', (req, res) => {
  try {
    const { id } = req.params;
    const { instruction, text } = req.body;
    if (!instruction || !text) return res.status(400).json({ error: 'Instruction and text are required' });

    const scratchDir = path.join(PROJECT_ROOT, 'scratch');
    if (!fs.existsSync(scratchDir)) fs.mkdirSync(scratchDir, { recursive: true });

    const instrFile = path.join(scratchDir, `instr_${id}.tmp`);
    const textFile  = path.join(scratchDir, `text_${id}.tmp`);
    fs.writeFileSync(instrFile, instruction, 'utf8');
    fs.writeFileSync(textFile,  text,        'utf8');

    exec(`python "${path.join(SCRIPTS_DIR, 'ai_rewrite.py')}" "${instrFile}" "${textFile}"`, (_err, stdout, stderr) => {
      try {
        if (fs.existsSync(instrFile)) fs.unlinkSync(instrFile);
        if (fs.existsSync(textFile))  fs.unlinkSync(textFile);
      } catch (cleanErr) { console.error('Failed to clean up temp files:', cleanErr); }

      if (_err) {
        console.error(`AI rewrite error: ${stderr || _err.message}`);
        return res.status(500).json({ error: 'AI rewrite execution failed' });
      }
      res.json({ text: stdout.trim() });
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to execute AI rewrite' });
  }
});

// ---------------------------------------------------------------------------
// Download all assets as ZIP
// ---------------------------------------------------------------------------

router.get('/api/jobs/:id/download-all', (req, res) => {
  try {
    const job = db.prepare('SELECT company, status FROM jobs WHERE id = ?').get(req.params.id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });
    const folder = resolveCompanyFolder(job.company, jobBaseDir(job.status));
    if (!fs.existsSync(folder)) return res.status(404).json({ error: 'No files found' });

    const pdfs = fs.readdirSync(folder).filter(f => f.endsWith('.pdf'));
    if (pdfs.length === 0) return res.status(404).json({ error: 'No PDF assets generated yet' });

    const zip           = new AdmZip();
    const zipFolderName = job.company.replace(/[^a-z0-9 ]+/gi, '').trim();
    pdfs.forEach(file => zip.addLocalFile(path.join(folder, file), zipFolderName));

    res.set('Content-Type', 'application/zip');
    res.set('Content-Disposition', `attachment; filename="${path.basename(folder)}_assets.zip"`);
    res.send(zip.toBuffer());
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to create ZIP' });
  }
});

// ---------------------------------------------------------------------------
// Manual draft trigger for an existing job
// ---------------------------------------------------------------------------

router.post('/api/jobs/:id/draft', (req, res) => {
  try {
    const { id } = req.params;
    const job = db.prepare('SELECT company, url FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    db.prepare(`UPDATE system_status SET status = 'drafting', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Generating tailored assets for ${job.company}`);
    logActivity('INFO', 'Pipeline', `Manual asset generation triggered for "${job.company}"`);

    const proc = spawn('python', [path.join(SCRIPTS_DIR, 'batch_pipeline.py'), '--company', job.company, '--url', job.url || '', '--mode', 'single'], {
      cwd: PROJECT_ROOT,
      env: { ...process.env, ...buildPythonEnv() },
    });
    proc.stdin.write('');
    proc.stdin.end();

    proc.stdout.on('data', (data) => {
      const output = data.toString().trim();
      if (!output) return;
      try {
        const parsed = JSON.parse(output);
        if (parsed.summary) logActivity('INFO', 'Pipeline', `[Draft] ${parsed.summary}`);
      } catch { logActivity('INFO', 'Pipeline', `[Draft] ${output}`); }
    });

    proc.stderr.on('data', (data) => {
      const err = data.toString().trim();
      if (err && !err.includes('UserWarning')) logActivity('ERROR', 'Pipeline', `[Draft Error] ${err}`);
    });

    proc.on('close', (code) => {
      logActivity(code === 0 ? 'INFO' : 'ERROR', 'Pipeline', `Draft for "${job.company}" exited with code ${code}`);
      db.prepare(`UPDATE system_status SET status = 'completed', current_item = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 'global'`).run(`Completed asset generation for ${job.company}`);
    });

    res.json({ success: true, message: `Drafting started for ${job.company}` });
  } catch {
    res.status(500).json({ error: 'Failed to start drafting' });
  }
});

export default router;
