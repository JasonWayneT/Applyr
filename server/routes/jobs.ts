import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { randomUUID } from 'crypto';
import AdmZip from 'adm-zip';
import { db, logActivity, syncJobFts, deleteJobFts } from '../db.js';
import {
  resolveCompanyFolder,
  SUBMISSION_DIR, ARCHIVE_DIR, SCRIPTS_DIR, PROJECT_ROOT,
  ALLOWED_JOB_FIELDS,
} from '../shared.js';
import {
  archiveActiveSubmission,
  restoreArchivedSubmission,
  jobHasPdfAssets,
  reconcileActiveSubmissionFolders,
} from '../submissionFolders.js';
import {
  formatSkillGapOutput,
  isSafeHttpUrl,
  isValidJobId,
  requireApiToken,
  runPythonScript,
  buildSpawnEnv,
  tryAcquirePipeline,
  releasePipeline,
} from '../middleware.js';

const router = Router();

router.use(requireApiToken);

const ACTIVE_STATUSES = new Set(['Backlog', 'Drafted']);

function jobBaseDir(status: string): string {
  return ACTIVE_STATUSES.has(status) ? SUBMISSION_DIR : ARCHIVE_DIR;
}

// ---------------------------------------------------------------------------
// Collection
// ---------------------------------------------------------------------------

router.get('/api/jobs', (req, res) => {
  try {
    const search = req.query.search as string;
    let jobs;
    if (search) {
      jobs = db.prepare(`
        SELECT jobs.* 
        FROM jobs 
        JOIN jobs_fts ON jobs.rowid = jobs_fts.rowid
        WHERE jobs_fts MATCH ? 
        ORDER BY rank
      `).all(`"${search}"*`) as any[];
    } else {
      jobs = db.prepare('SELECT * FROM jobs ORDER BY created_at DESC').all() as any[];
    }
    const enriched = jobs.map(job => ({
      ...job,
      has_assets: jobHasPdfAssets(job.company, job.status),
    }));
    res.json(enriched);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to fetch jobs' });
  }
});

router.post('/api/jobs', (req, res) => {
  try {
    const { id, company, title, url, score, summary, status } = req.body;
    if (!company || !title) return res.status(400).json({ error: 'company and title are required' });
    if (url && !isSafeHttpUrl(url)) return res.status(400).json({ error: 'url must be http or https' });
    const jobId = id && isValidJobId(id) ? id : randomUUID();
    db.prepare(`
      INSERT INTO jobs (id, company, title, url, score, status, summary, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    `).run(jobId, company, title, url || null, score || null, status || 'Drafted', summary || null);
    const row = db.prepare('SELECT rowid FROM jobs WHERE id = ?').get(jobId) as { rowid: number };
    if (row?.rowid) syncJobFts(row.rowid);
    logActivity('INFO', 'System', `Manually added job "${company}" to drafted.`);
    res.json({ success: true, id: jobId });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to add job' });
  }
});

router.post('/api/jobs/reconcile-submissions', (_req, res) => {
  try {
    const result = reconcileActiveSubmissionFolders();
    logActivity(
      'INFO',
      'System',
      `Reconciled submissions/: archived=${result.archived.length}, removed=${result.removed.length}`,
    );
    res.json({ success: true, ...result });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to reconcile submission folders' });
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
    if (!isValidJobId(id)) return res.status(400).json({ error: 'Invalid job id' });
    let { status } = req.body;

    const job = db.prepare('SELECT company, status, rowid FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    // Normalize scout dismissals to Closed + rejection metadata (CR-025)
    const rejectionType = req.body.rejection_type as string | undefined;
    const rejectionStage = req.body.rejection_stage as string | undefined;
    const outcomeNotes = req.body.outcome_notes as string | undefined;
    if (status === 'Rejected' && rejectionType) {
      status = 'Closed';
    }

    const activePath  = resolveCompanyFolder(job.company, SUBMISSION_DIR);
    const archivePath = resolveCompanyFolder(job.company, ARCHIVE_DIR);

    if (status === 'No Longer Available') {
      const fullJob = db.prepare('SELECT company, title, url FROM jobs WHERE id = ?').get(id) as any;
      if (fullJob?.url) {
        db.prepare('INSERT OR IGNORE INTO stale_jobs (url, company, title) VALUES (?, ?, ?)').run(fullJob.url, fullJob.company, fullJob.title);
      }
      if (fs.existsSync(activePath))  fs.rmSync(activePath,  { recursive: true, force: true });
      if (fs.existsSync(archivePath)) fs.rmSync(archivePath, { recursive: true, force: true });
      deleteJobFts(job.rowid);
      db.prepare('DELETE FROM jobs WHERE id = ?').run(id);
      logActivity('INFO', 'System', `Job "${job.company}" marked No Longer Available and completely deleted.`);
      return res.json({ success: true, deleted: true });
    }

    const isNowArchived = !ACTIVE_STATUSES.has(status);
    const wasArchived   = !ACTIVE_STATUSES.has(job.status);

    if (isNowArchived && !wasArchived) archiveActiveSubmission(job.company);
    if (!isNowArchived && wasArchived) restoreArchivedSubmission(job.company);

    const isClosed = status === 'Closed';
    db.prepare(`
      UPDATE jobs
      SET status          = ?,
          rejection_stage = COALESCE(?, rejection_stage),
          rejection_type  = COALESCE(?, rejection_type),
          outcome_notes   = COALESCE(?, outcome_notes)
      WHERE id = ?
    `).run(
      status,
      isClosed ? (rejectionStage || job.status) : null,
      isClosed ? rejectionType : null,
      isClosed ? outcomeNotes : null,
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
    if (keys.some(k => ['company', 'title', 'summary', 'url'].includes(k))) {
      const row = db.prepare('SELECT rowid FROM jobs WHERE id = ?').get(id) as { rowid: number } | undefined;
      if (row?.rowid) syncJobFts(row.rowid);
    }
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

router.get('/api/jobs/:id/skill-gap', async (req, res) => {
  try {
    const { id } = req.params;
    if (!isValidJobId(id)) return res.status(400).json({ success: false, error: 'Invalid job id' });

    const scriptPath = path.join(SCRIPTS_DIR, 'skill_gap.py');
    const dbPath = path.join(PROJECT_ROOT, 'jobagent.sqlite');
    const { code, stdout, stderr } = await runPythonScript([scriptPath, dbPath, id]);

    if (code !== 0) {
      console.error(stderr);
      return res.status(500).json({ success: false, error: 'Failed to analyze skill gap' });
    }

    try {
      const parsed = JSON.parse(stdout.trim());
      const formatted = formatSkillGapOutput(parsed);
      if (!formatted.success) {
        return res.status(404).json(formatted);
      }
      res.json({ success: true, output: formatted.output });
    } catch {
      res.status(500).json({ success: false, error: 'Invalid JSON returned from skill-gap script' });
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ success: false, error: 'Server error' });
  }
});

router.put('/api/jobs/:id/files/:filename', async (req, res) => {
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

    if (safeFilename.endsWith('.md') && (safeFilename === 'Resume.md' || safeFilename === 'CoverLetter.md')) {
      const manifestPath = path.join(folder, 'draft_manifest.json');
      if (fs.existsSync(manifestPath)) {
        try {
          const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
          if (manifest.verification_passed !== true) {
            return res.status(400).json({
              error: 'PDF export blocked: draft_manifest verification_passed is not true.',
            });
          }
        } catch {
          return res.status(400).json({ error: 'Invalid draft_manifest.json' });
        }
      }
    }

    fs.writeFileSync(filePath, text, 'utf8');

    if (safeFilename.endsWith('.md')) {
      const pdfPath       = path.join(folder, safeFilename.replace('.md', '.pdf'));
      const guardScript   = path.join(SCRIPTS_DIR, 'style_compliance_guard.py');
      const compileScript = path.join(SCRIPTS_DIR, 'compile_single.py');
      const guard = await runPythonScript([guardScript, filePath]);
      if (guard.code !== 0) {
        logActivity('ERROR', 'System', `Style guard failed for "${job.company}": ${guard.stderr}`);
        return res.status(500).json({ error: 'Document saved but validation failed' });
      }
      const compiled = await runPythonScript([compileScript, filePath, pdfPath]);
      if (compiled.code !== 0) {
        logActivity('ERROR', 'System', `PDF compile failed for "${job.company}": ${compiled.stderr}`);
        return res.status(500).json({ error: 'Document saved but PDF compilation failed' });
      }
      logActivity('INFO', 'System', `Successfully validated and compiled PDF for "${job.company}"`);
      return res.json({ success: true, compiled: true });
    }

    res.json({ success: true, compiled: false });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to save file' });
  }
});

// ---------------------------------------------------------------------------
// AI rewrite
// ---------------------------------------------------------------------------

router.post('/api/jobs/:id/ai-rewrite', async (req, res) => {
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

    const { code, stdout, stderr } = await runPythonScript([
      path.join(SCRIPTS_DIR, 'ai_rewrite.py'),
      instrFile,
      textFile,
    ]);

    try {
      if (fs.existsSync(instrFile)) fs.unlinkSync(instrFile);
      if (fs.existsSync(textFile))  fs.unlinkSync(textFile);
    } catch (cleanErr) { console.error('Failed to clean up temp files:', cleanErr); }

    if (code !== 0) {
      console.error(`AI rewrite error: ${stderr}`);
      return res.status(500).json({ error: 'AI rewrite execution failed' });
    }
    res.json({ text: stdout.trim() });
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
    const job = db.prepare('SELECT company, url, score, status FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const label = `Drafting assets for ${job.company}`;
    if (!tryAcquirePipeline(label)) {
      return res.status(409).json({ error: 'Pipeline is already running. Try again when sync/evaluate completes.' });
    }

    const draftOnly =
      job.score != null &&
      job.score >= 72 &&
      ['Needs Retry', 'Backlog', 'Drafted'].includes(job.status);

    logActivity(
      'INFO',
      'Pipeline',
      `Manual asset generation for "${job.company}"${draftOnly ? ' [draft-only]' : ''}`,
    );

    const procArgs = [
      path.join(SCRIPTS_DIR, 'batch_pipeline.py'),
      '--mode', 'single',
      '--company', job.company,
      '--url', job.url || '',
      '--job-id', id,
    ];
    if (draftOnly) procArgs.push('--draft-only');

    const proc = spawn('python', procArgs, {
      cwd: PROJECT_ROOT,
      shell: false,
      env: buildSpawnEnv(),
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
      releasePipeline(`Completed asset generation for ${job.company}`);
    });

    res.json({ success: true, message: `Drafting started for ${job.company}` });
  } catch {
    res.status(500).json({ error: 'Failed to start drafting' });
  }
});

router.post('/api/jobs/rerank', async (req, res) => {
  try {
    const { query, threshold } = req.body;
    if (!query || typeof query !== 'string') return res.status(400).json({ error: 'Query is required' });

    logActivity('INFO', 'System', `Reranking backlog for query: "${query}"`);
    const scriptPath = path.join(SCRIPTS_DIR, 'rerank_backlog.py');
    const args = [scriptPath, '--query', query];
    if (threshold !== undefined && threshold !== null) {
      args.push('--threshold', String(threshold));
    }

    const { code, stdout, stderr } = await runPythonScript(args);
    if (code !== 0) {
      console.error(`Rerank error: ${stderr}`);
      return res.status(500).json({ error: 'Failed to rerank backlog' });
    }
    res.json({ success: true, output: stdout.trim() });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Server error during rerank' });
  }
});

export default router;
