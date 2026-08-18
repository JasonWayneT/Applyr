import { Router } from 'express';
import { db, logActivity } from '../../db.js';
import {
  jobHasPdfAssets,
  reconcileActiveSubmissionFolders,
  reconcileDraftedJobsWithAssets,
  reconcileOrphanSubmissionFolders,
} from '../../submissionFolders.js';
import { isSafeHttpUrl, isValidJobId } from '../../middleware.js';
import { insertJob, patchJob } from '../../repository/jobRepository.js';
import {
  APPLICATION_FUNNEL_STATUSES,
  deriveStatusForInterviewDateChange,
  isValidInterviewDateTime,
} from '../../../shared/domain/jobPipeline.js';
import { applyJobStatusUpdate } from '../../services/jobStatusService.js';

const router = Router();

router.get('/api/jobs', (req, res) => {
  try {
    reconcileDraftedJobsWithAssets();
    reconcileOrphanSubmissionFolders();
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
    const funnelList = APPLICATION_FUNNEL_STATUSES.map((s) => `'${s}'`).join(', ');

    const everApplied = db.prepare(
      `SELECT COUNT(*) as count FROM jobs WHERE
         status IN (${funnelList})
         OR (status = 'Closed' AND rejection_stage IN (${funnelList}))`,
    ).get() as { count: number };

    const activeInFunnel = db.prepare(
      `SELECT COUNT(*) as count FROM jobs WHERE status IN (${funnelList})`,
    ).get() as { count: number };

    const closedAfterApply = db.prepare(
      `SELECT COUNT(*) as count FROM jobs
       WHERE status = 'Closed' AND rejection_stage IN (${funnelList})`,
    ).get() as { count: number };

    const byStage = db.prepare(
      `SELECT rejection_stage, COUNT(*) as count FROM jobs
       WHERE status = 'Closed' AND rejection_stage IN (${funnelList})
       GROUP BY rejection_stage`,
    ).all() as { rejection_stage: string; count: number }[];

    const byType = db.prepare(
      `SELECT rejection_type, COUNT(*) as count FROM jobs
       WHERE status = 'Closed' AND rejection_stage IN (${funnelList})
         AND rejection_type IS NOT NULL AND rejection_type != ''
       GROUP BY rejection_type`,
    ).all() as { rejection_type: string; count: number }[];

    const activeByStatus = db.prepare(
      `SELECT status, COUNT(*) as count FROM jobs
       WHERE status IN (${funnelList})
       GROUP BY status`,
    ).all() as { status: string; count: number }[];

    const preApplyClosed = db.prepare(
      `SELECT COUNT(*) as count FROM jobs
       WHERE status = 'Closed'
         AND (rejection_stage IS NULL OR rejection_stage NOT IN (${funnelList}))`,
    ).get() as { count: number };

    const stageOrder = new Map<string, number>(APPLICATION_FUNNEL_STATUSES.map((s, i) => [s, i]));
    byStage.sort(
      (a, b) =>
        (stageOrder.get(a.rejection_stage) ?? 99) - (stageOrder.get(b.rejection_stage) ?? 99),
    );
    byType.sort((a, b) => b.count - a.count);
    activeByStatus.sort(
      (a, b) =>
        (stageOrder.get(a.status) ?? 99) - (stageOrder.get(b.status) ?? 99),
    );

    res.json({
      outcomes: {
        everApplied: everApplied.count,
        activeInFunnel: activeInFunnel.count,
        closedAfterApply: closedAfterApply.count,
        byStage,
        byType,
        activeByStatus,
      },
      notes: {
        preApplyClosed: preApplyClosed.count,
        funnelStages: [...APPLICATION_FUNNEL_STATUSES],
      },
    });
  } catch {
    res.status(500).json({ error: 'Failed to fetch stats' });
  }
});

router.patch('/api/jobs/:id/status', (req, res) => {
  try {
    const { id } = req.params;
    const result = applyJobStatusUpdate(id, req.body);

    switch (result.kind) {
      case 'invalid_id':
        return res.status(400).json({ error: 'Invalid job id' });
      case 'not_found':
        return res.status(404).json({ error: 'Job not found' });
      case 'missing_interview_date':
        return res.status(400).json({ error: result.message });
      case 'deleted':
        return res.json({ success: true, deleted: true });
      case 'updated':
        return res.json({ success: true, status: result.status });
    }
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job status' });
  }
});

router.patch('/api/jobs/:id', (req, res) => {
  try {
    const { id } = req.params;
    const updates = { ...req.body };
    const validKeys = Object.keys(updates).filter(k => k !== 'id');
    if (validKeys.length === 0) return res.status(400).json({ error: 'No valid fields to update' });

    // Setting/changing interview_date through this generic route bypasses
    // applyJobStatusUpdate's side effects (folder archive/restore, status_changed_at,
    // rubric logging). If the caller didn't also pass an explicit status, derive the
    // forward-only auto-advance here and route just that piece through the shared
    // status-transition path so it gets those side effects too.
    if (
      typeof updates.interview_date === 'string' &&
      isValidInterviewDateTime(updates.interview_date) &&
      updates.status === undefined
    ) {
      const current = db.prepare('SELECT status FROM jobs WHERE id = ?').get(id) as { status: string } | undefined;
      const derivedStatus = current ? deriveStatusForInterviewDateChange(current.status) : null;
      if (derivedStatus) {
        applyJobStatusUpdate(id, { status: derivedStatus, interview_date: updates.interview_date });
        delete updates.interview_date;
      }
    }

    if (Object.keys(updates).filter(k => k !== 'id').length > 0) {
      patchJob(id, updates);
    }
    res.json({ success: true });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Failed to update job details' });
  }
});

export default router;
