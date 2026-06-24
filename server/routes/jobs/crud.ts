import { Router } from 'express';
import fs from 'fs';
import path from 'path';
import { db, logActivity } from '../../db.js';
import { resolveCompanyFolder, SUBMISSION_DIR, ARCHIVE_DIR } from '../../shared.js';
import { ACTIVE_STATUSES } from '../../domain/jobStatus.js';
import {
  archiveActiveSubmission,
  restoreArchivedSubmission,
  jobHasPdfAssets,
  reconcileActiveSubmissionFolders,
} from '../../submissionFolders.js';
import { isSafeHttpUrl, isValidJobId, runPythonScript } from '../../middleware.js';
import { pythonScriptPath } from '../../pipeline/processRunner.js';
import { insertJob, patchJob, deleteJobRecord } from '../../repository/jobRepository.js';
import {
  statusRequiresInterviewDateTime,
  isValidInterviewDateTime,
} from '../../../shared/domain/jobPipeline.js';

const router = Router();

/** Read rubric_score from draft_manifest.json for a company folder (FR-210).
 *  Checks active submissions first, then archive (safe if folder already moved).
 *  Returns null silently if the manifest is missing or malformed.
 */
function readManifestRubricScore(company: string): Record<string, any> | null {
  for (const baseDir of [SUBMISSION_DIR, ARCHIVE_DIR]) {
    try {
      const folder = resolveCompanyFolder(company, baseDir);
      const manifestPath = path.join(folder, 'draft_manifest.json');
      if (fs.existsSync(manifestPath)) {
        const raw = fs.readFileSync(manifestPath, 'utf-8');
        const manifest = JSON.parse(raw);
        return manifest?.rubric_score ?? null;
      }
    } catch {
      // manifest missing or unreadable — continue to next base dir
    }
  }
  return null;
}

router.get('/api/jobs', (req, res) => {
  try {
    const search = req.query.search as string;
    let jobs: any[];
    if (search) {
      jobs = db.prepare(`
        SELECT jobs.*, js.score_total, js.score_breakdown_json, js.reason_summary
        FROM jobs 
        JOIN jobs_fts ON jobs.rowid = jobs_fts.rowid
        LEFT JOIN job_scores js ON jobs.id = js.job_id AND js.is_latest = 1
        WHERE jobs_fts MATCH ? 
        ORDER BY rank
      `).all(`"${search}"*`) as any[];
    } else {
      jobs = db.prepare(`
        SELECT jobs.*, js.score_total, js.score_breakdown_json, js.reason_summary
        FROM jobs 
        LEFT JOIN job_scores js ON jobs.id = js.job_id AND js.is_latest = 1
        ORDER BY jobs.created_at DESC
      `).all() as any[];
    }

    const enriched = jobs.map(job => {
      // Find sources through cluster deduplication tables
      const links = db.prepare(`
        SELECT s.name 
        FROM job_source_links sl
        JOIN job_clusters c ON sl.cluster_id = c.id
        JOIN sources s ON sl.source_id = s.id
        WHERE c.canonical_job_id = ?
      `).all(job.id) as { name: string }[];

      // Fallback to source_site if no links found
      const sources = links.length > 0 ? links.map(l => l.name) : (job.source_site ? [job.source_site] : []);

      return {
        ...job,
        sources,
        has_assets: jobHasPdfAssets(job.company, job.status),
      };
    });
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
    const jobId = id && isValidJobId(id) ? id : undefined;
    const newId = insertJob({ id: jobId, company, title, url: url || null, score: score || null, status: status || 'Drafted', summary: summary || null });
    logActivity('INFO', 'System', `Manually added job "${company}" to drafted.`);
    res.json({ success: true, id: newId });
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

    const job = db.prepare('SELECT company, status, interview_date, rowid FROM jobs WHERE id = ?').get(id) as any;
    if (!job) return res.status(404).json({ error: 'Job not found' });

    const rejectionType = req.body.rejection_type as string | undefined;
    const rejectionStage = req.body.rejection_stage as string | undefined;
    const outcomeNotes = req.body.outcome_notes as string | undefined;
    const interviewDateFromBody = req.body.interview_date as string | undefined;

    if (status === 'Rejected' && rejectionType) {
      status = 'Closed';
    }

    if (statusRequiresInterviewDateTime(status)) {
      const resolved =
        (interviewDateFromBody && String(interviewDateFromBody).trim()) ||
        (job.interview_date && String(job.interview_date).trim()) ||
        '';
      if (!isValidInterviewDateTime(resolved)) {
        return res.status(400).json({
          error:
            'interview_date is required when moving to Recruiter Screen or Core Interviews. Set date and time first.',
        });
      }
    }

    // FR-210: read rubric score before archive moves the folder
    const OUTCOME_STATUSES = new Set(['Closed', 'Screener', 'Interview', 'Offer']);
    const rubricScore = OUTCOME_STATUSES.has(status) ? readManifestRubricScore(job.company) : null;

    const activePath  = resolveCompanyFolder(job.company, SUBMISSION_DIR);
    const archivePath = resolveCompanyFolder(job.company, ARCHIVE_DIR);

    if (status === 'No Longer Available') {
      const fullJob = db.prepare('SELECT company, title, url FROM jobs WHERE id = ?').get(id) as any;
      if (fs.existsSync(activePath))  fs.rmSync(activePath,  { recursive: true, force: true });
      if (fs.existsSync(archivePath)) fs.rmSync(archivePath, { recursive: true, force: true });
      deleteJobRecord(id, fullJob?.url, fullJob?.company ?? job.company, fullJob?.title ?? '');
      logActivity('INFO', 'System', `Job "${job.company}" marked No Longer Available and completely deleted.`);
      return res.json({ success: true, deleted: true });
    }

    const isNowArchived = !ACTIVE_STATUSES.has(status);
    const wasArchived   = !ACTIVE_STATUSES.has(job.status);

    if (isNowArchived && !wasArchived) archiveActiveSubmission(job.company);
    if (!isNowArchived && wasArchived) restoreArchivedSubmission(job.company);

    const isClosed = status === 'Closed';
    const interviewDateToPersist =
      statusRequiresInterviewDateTime(status)
        ? (interviewDateFromBody && String(interviewDateFromBody).trim()) ||
          (job.interview_date && String(job.interview_date).trim()) ||
          null
        : interviewDateFromBody !== undefined
          ? interviewDateFromBody || null
          : undefined;

    db.prepare(`
      UPDATE jobs
      SET status          = ?,
          rejection_stage = COALESCE(?, rejection_stage),
          rejection_type  = COALESCE(?, rejection_type),
          outcome_notes   = COALESCE(?, outcome_notes),
          interview_date  = CASE WHEN ? IS NOT NULL THEN ? ELSE interview_date END
      WHERE id = ?
    `).run(
      status,
      isClosed ? (rejectionStage || job.status) : null,
      isClosed ? rejectionType : null,
      isClosed ? outcomeNotes : null,
      interviewDateToPersist === undefined ? null : interviewDateToPersist,
      interviewDateToPersist === undefined ? null : interviewDateToPersist,
      id,
    );
    logActivity('INFO', 'System', `Job "${job.company}" status changed to ${status}`);

    // FR-210: log rubric score alongside outcome for calibration
    if (rubricScore !== null) {
      logActivity('INFO', 'RubricLog', `Outcome recorded for "${job.company}": ${status}`, {
        event: 'outcome_rubric_log',
        job_id: id,
        company: job.company,
        outcome: status,
        rejection_stage: isClosed ? (rejectionStage || job.status) : null,
        rejection_type: isClosed ? (rejectionType || null) : null,
        rubric_overall: rubricScore.overall ?? null,
        rubric_summary_score: rubricScore.summary?.score ?? null,
        rubric_experience_score: rubricScore.experience?.score ?? null,
        rubric_threshold_flag: rubricScore.threshold_flag ?? null,
      });
    }

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
    const validKeys = Object.keys(updates).filter(k => k !== 'id');
    if (validKeys.length === 0) return res.status(400).json({ error: 'No valid fields to update' });
    patchJob(id, updates);
    res.json({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job details' });
  }
});

export default router;
