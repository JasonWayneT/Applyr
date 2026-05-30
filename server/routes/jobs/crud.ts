import { Router } from 'express';
import fs from 'fs';
import { randomUUID } from 'crypto';
import { db, logActivity, syncJobFts, deleteJobFts } from '../../db.js';
import {
  resolveCompanyFolder,
  SUBMISSION_DIR, ARCHIVE_DIR,
  ALLOWED_JOB_FIELDS,
} from '../../shared.js';
import { ACTIVE_STATUSES } from '../../domain/jobStatus.js';
import {
  archiveActiveSubmission,
  restoreArchivedSubmission,
  jobHasPdfAssets,
  reconcileActiveSubmissionFolders,
} from '../../submissionFolders.js';
import { isSafeHttpUrl, isValidJobId, runPythonScript } from '../../middleware.js';
import { pythonScriptPath } from '../../pipeline/processRunner.js';

const router = Router();

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

// Static path before /:id — Express would treat "rerank" as an id otherwise
router.post('/api/jobs/rerank', async (req, res) => {
  try {
    const { query, threshold } = req.body;
    if (!query || typeof query !== 'string') return res.status(400).json({ error: 'Query is required' });

    logActivity('INFO', 'System', `Reranking backlog for query: "${query}"`);
    const args = [pythonScriptPath('rerank_backlog.py'), '--query', query];
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

router.patch('/api/jobs/:id/status', (req, res) => {
  try {
    const { id } = req.params;
    if (!isValidJobId(id)) return res.status(400).json({ error: 'Invalid job id' });
    let { status } = req.body;

    const job = db.prepare('SELECT company, status, rowid FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

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

export default router;
