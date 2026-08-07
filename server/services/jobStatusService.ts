// Extracted from server/routes/jobs/crud.ts's PATCH /api/jobs/:id/status handler (CR-072 Story 2.0 /
// OQ-3) so both the HTTP route and the Gmail sync service (CR-072 Epic 2) share one status-transition
// path — a job closed by an incoming email must get the exact same folder-archive/rubric-log/applied_at
// side effects a UI-triggered close gets, not a reduced direct-DB-write version of them.
import fs from 'fs';
import path from 'path';
import { db, logActivity } from '../db.js';
import { resolveCompanyFolder, SUBMISSION_DIR, ARCHIVE_DIR } from '../shared.js';
import { ACTIVE_STATUSES } from '../domain/jobStatus.js';
import { archiveActiveSubmission, restoreArchivedSubmission } from '../submissionFolders.js';
import { deleteJobRecord } from '../repository/jobRepository.js';
import { isValidJobId } from '../middleware.js';
import {
  statusRequiresInterviewDateTime,
  isValidInterviewDateTime,
  APPLICATION_FUNNEL_SET,
  PRE_APPLY_STATUSES,
} from '../../shared/domain/jobPipeline.js';

export interface JobStatusUpdateInput {
  status: string;
  rejection_type?: string;
  rejection_stage?: string;
  outcome_notes?: string;
  interview_date?: string;
  applied_at?: string;
}

export type JobStatusUpdateResult =
  | { kind: 'invalid_id' }
  | { kind: 'not_found' }
  | { kind: 'missing_interview_date'; message: string }
  | { kind: 'deleted' }
  | { kind: 'updated'; status: string };

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

/**
 * Same status-transition logic the PATCH /api/jobs/:id/status route runs: folder archive/restore on
 * funnel-stage crossings, rubric-score logging on outcome statuses, applied_at stamping/clearing, and the
 * activity log entry. Callers (the HTTP route, or CR-072's Gmail sync service) translate the discriminated
 * result into whatever response shape they need — this function has no req/res, no HTTP awareness.
 */
export function applyJobStatusUpdate(id: string, input: JobStatusUpdateInput): JobStatusUpdateResult {
  if (!isValidJobId(id)) return { kind: 'invalid_id' };

  const job = db.prepare('SELECT company, status, interview_date, applied_at, rowid FROM jobs WHERE id = ?').get(id) as any;
  if (!job) return { kind: 'not_found' };

  let status = input.status;
  const rejectionType = input.rejection_type;
  const rejectionStage = input.rejection_stage;
  const outcomeNotes = input.outcome_notes;
  const interviewDateFromBody = input.interview_date;
  const appliedAtFromBody = input.applied_at;

  if (status === 'Rejected' && rejectionType) {
    status = 'Closed';
  }

  if (statusRequiresInterviewDateTime(status)) {
    const resolved =
      (interviewDateFromBody && String(interviewDateFromBody).trim()) ||
      (job.interview_date && String(job.interview_date).trim()) ||
      '';
    if (!isValidInterviewDateTime(resolved)) {
      return {
        kind: 'missing_interview_date',
        message:
          'interview_date is required when moving to Recruiter Screen or Core Interviews. Set date and time first.',
      };
    }
  }

  // FR-210: read rubric score before archive moves the folder
  const OUTCOME_STATUSES = new Set(['Closed', 'Screener', 'Interview', 'Offer']);
  const rubricScore = OUTCOME_STATUSES.has(status) ? readManifestRubricScore(job.company) : null;

  const activePath = resolveCompanyFolder(job.company, SUBMISSION_DIR);
  const archivePath = resolveCompanyFolder(job.company, ARCHIVE_DIR);

  if (status === 'No Longer Available') {
    const fullJob = db.prepare('SELECT company, title, url FROM jobs WHERE id = ?').get(id) as any;
    if (fs.existsSync(activePath)) fs.rmSync(activePath, { recursive: true, force: true });
    if (fs.existsSync(archivePath)) fs.rmSync(archivePath, { recursive: true, force: true });
    deleteJobRecord(id, fullJob?.url, fullJob?.company ?? job.company, fullJob?.title ?? '');
    logActivity('INFO', 'System', `Job "${job.company}" marked No Longer Available and completely deleted.`);
    return { kind: 'deleted' };
  }

  const isNowArchived = !ACTIVE_STATUSES.has(status);
  const wasArchived = !ACTIVE_STATUSES.has(job.status);

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

  // applied_at: stamp on first entry to Applied+; clear if returned to pre-apply; allow body override
  let appliedAtSql = 'applied_at';
  let appliedAtBind: string | null | undefined = undefined;
  if (appliedAtFromBody !== undefined) {
    const trimmed = String(appliedAtFromBody).trim();
    appliedAtSql = '?';
    appliedAtBind = trimmed || null;
  } else if (PRE_APPLY_STATUSES.has(status)) {
    appliedAtSql = 'NULL';
    appliedAtBind = undefined;
  } else if (APPLICATION_FUNNEL_SET.has(status) && !job.applied_at) {
    appliedAtSql = 'CURRENT_TIMESTAMP';
    appliedAtBind = undefined;
  }

  // status_changed_at (migration 015): only stamped when status actually changes, not on every
  // call to this function -- an unrelated field update (e.g. outcome_notes) that happens to pass
  // the same status through must not reset the reapply time-gate's elapsed-time clock. Feeds
  // generate-submission/SKILL.md Stage 0's rejection-cooldown check (2026-08-05 planning doc).
  const statusActuallyChanged = status !== job.status;

  const updateSql = `
    UPDATE jobs
    SET status            = ?,
        rejection_stage   = COALESCE(?, rejection_stage),
        rejection_type    = COALESCE(?, rejection_type),
        outcome_notes     = COALESCE(?, outcome_notes),
        interview_date    = CASE WHEN ? IS NOT NULL THEN ? ELSE interview_date END,
        applied_at        = ${appliedAtSql === '?' ? '?' : appliedAtSql},
        status_changed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE status_changed_at END
    WHERE id = ?
  `;

  const params: unknown[] = [
    status,
    isClosed ? (rejectionStage || job.status) : null,
    isClosed ? rejectionType : null,
    isClosed ? outcomeNotes : null,
    interviewDateToPersist === undefined ? null : interviewDateToPersist,
    interviewDateToPersist === undefined ? null : interviewDateToPersist,
  ];
  if (appliedAtSql === '?') params.push(appliedAtBind);
  params.push(statusActuallyChanged ? 1 : 0); // better-sqlite3 has no native boolean bind
  params.push(id);

  db.prepare(updateSql).run(...params);
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

  return { kind: 'updated', status };
}
